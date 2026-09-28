"""AI gateway — wraps the LiteLLM proxy.

Rotation itself (free tiers first, cooldowns, fallback chains) is LiteLLM's job,
configured in litellm/config.yaml. This wrapper adds: per-task virtual routing,
JSON-schema-validated outputs with one retry, graceful degradation when every
provider is exhausted, token accounting into Postgres, and test-connection pings.
"""
import json
import logging
import re

import httpx

from ..config import settings

log = logging.getLogger("gateway")

# maps provider name -> a deployment model_name from litellm/config.yaml used to test it
PROVIDER_TEST_MODEL = {
    "groq": "judge",
    "openrouter": "judge-fb1",
    "mistral": "judge-fb2",
    "huggingface": "judge-fb3",
    "deepseek": "judge-fb4",
    "openai": "judge-fb5",
}

_PROVIDER_RE = re.compile(r"^(groq|openrouter|mistral|huggingface|deepseek|openai)/")


class GatewayUnavailable(Exception):
    """All providers exhausted / gateway down — caller should defer, not crash."""


def _provider_of(model: str) -> str:
    m = _PROVIDER_RE.match(model or "")
    return m.group(1) if m else (model or "unknown").split("/")[0]


class Gateway:
    def __init__(self):
        self.base = settings.litellm_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {settings.litellm_master_key}"}
        self._down_until = 0.0  # circuit breaker: skip calls while rotation is dry

    async def chat(self, task: str, messages: list[dict], max_tokens: int = 800,
                   temperature: float = 0.1, json_mode: bool = False) -> tuple[str, dict]:
        """Returns (content, usage_meta). Raises GatewayUnavailable when rotation is exhausted."""
        import time
        if time.monotonic() < self._down_until:
            raise GatewayUnavailable("circuit open — rotation was dry recently")
        body = {"model": task, "messages": messages,
                "max_tokens": max_tokens, "temperature": temperature}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                r = await client.post(f"{self.base}/v1/chat/completions",
                                      json=body, headers=self.headers)
        except httpx.HTTPError as e:
            self._down_until = time.monotonic() + 300
            raise GatewayUnavailable(f"litellm unreachable: {e}") from e
        # 401/403: no provider keys configured (or bad master key) — same downstream
        # handling as exhaustion: defer enrichment, retry via catch-up job.
        if r.status_code in (401, 403, 429) or r.status_code >= 500:
            self._down_until = time.monotonic() + 300
            raise GatewayUnavailable(f"rotation unavailable ({r.status_code}): {r.text[:200]}")
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"] or ""
        served = data.get("model", task)
        usage = data.get("usage", {}) or {}
        meta = {"task": task, "model": served, "provider": _provider_of(served),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0)}
        self._record(meta)
        return content, meta

    async def chat_json(self, task: str, messages: list[dict], max_tokens: int = 800) -> dict:
        """chat() + parse JSON, one repair retry."""
        content, _ = await self.chat(task, messages, max_tokens=max_tokens, json_mode=True)
        try:
            return _extract_json(content)
        except ValueError:
            retry = messages + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": "That was not valid JSON. Reply with ONLY the JSON object."},
            ]
            content, _ = await self.chat(task, retry, max_tokens=max_tokens, json_mode=True)
            return _extract_json(content)

    async def embed(self, texts: list[str]) -> list[list[float]] | None:
        """Returns vectors, or None when no embedding provider is available (caller falls back to TF-IDF)."""
        import time
        if time.monotonic() < self._down_until:
            return None
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(f"{self.base}/v1/embeddings",
                                      json={"model": "embed", "input": texts}, headers=self.headers)
            if r.status_code != 200:
                if r.status_code in (401, 403, 429) or r.status_code >= 500:
                    self._down_until = time.monotonic() + 300
                return None
            data = r.json()
            self._record({"task": "embed", "model": data.get("model", "embed"),
                          "provider": _provider_of(data.get("model", "")),
                          "prompt_tokens": (data.get("usage") or {}).get("prompt_tokens", 0),
                          "completion_tokens": 0})
            return [d["embedding"] for d in data["data"]]
        except httpx.HTTPError:
            return None

    async def test_provider(self, provider: str) -> dict:
        model = PROVIDER_TEST_MODEL.get(provider)
        if not model:
            return {"provider": provider, "ok": False, "error": "unknown provider"}
        import time
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{self.base}/v1/chat/completions", headers=self.headers,
                    json={"model": model, "messages": [{"role": "user", "content": "ping"}],
                          "max_tokens": 2,
                          # pin to the exact deployment, don't let fallbacks mask a dead key
                          "fallbacks": []})
            ms = int((time.monotonic() - t0) * 1000)
            if r.status_code == 200:
                served = r.json().get("model", model)
                return {"provider": provider, "ok": True, "latency_ms": ms, "served_model": served}
            return {"provider": provider, "ok": False, "latency_ms": ms,
                    "error": f"{r.status_code}: {r.text[:200]}"}
        except httpx.HTTPError as e:
            return {"provider": provider, "ok": False, "error": str(e)}

    def _record(self, meta: dict) -> None:
        """Token accounting — best-effort, never blocks the pipeline."""
        try:
            from ..db import SessionLocal
            from ..models import TokenUsage
            with SessionLocal() as db:
                db.add(TokenUsage(task=meta["task"], model=meta["model"],
                                  provider=meta["provider"],
                                  prompt_tokens=meta["prompt_tokens"],
                                  completion_tokens=meta["completion_tokens"]))
                db.commit()
        except Exception:  # noqa: BLE001
            log.warning("token usage record failed", exc_info=True)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found")
    return json.loads(text[start:end + 1])


gateway = Gateway()
