"""AI gateway — our own multi-provider rotation (no LiteLLM).

Providers live in the DB (ai_providers), keys encrypted. Every provider is called
via the OpenAI-compatible /chat/completions + /embeddings shape, which OpenAI,
DeepSeek, Groq, OpenRouter, Mistral, HuggingFace router, Together, etc. all speak.

Per task (judge|enrich|agent|embed) we try enabled providers in `priority` order
(low first), skipping ones cooling down after a recent 429/limit/auth error, until
one succeeds. Usage is recorded to token_usage for the monitor.
"""
import logging
import time

import httpx
import redis

from ..config import settings

log = logging.getLogger("gateway")


class GatewayUnavailable(Exception):
    """No provider could serve the task (none configured, or all cooling/failing)."""


class Gateway:
    def __init__(self):
        self._redis = None

    @property
    def redis(self):
        if self._redis is None:
            self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    def _cooling(self, provider_id: int) -> bool:
        return self.redis.exists(f"ai_cooldown:{provider_id}") == 1

    def _cool(self, provider_id: int, seconds: int = 300) -> None:
        self.redis.set(f"ai_cooldown:{provider_id}", "1", ex=seconds)

    def _providers_for(self, task: str) -> list[dict]:
        """Load enabled providers that declare a model for this task, priority order."""
        from ..db import SessionLocal
        from ..models import AIProvider
        from .crypto import decrypt
        out = []
        with SessionLocal() as db:
            rows = (db.query(AIProvider)
                    .filter(AIProvider.enabled.is_(True))
                    .order_by(AIProvider.priority.asc(), AIProvider.id.asc()).all())
            for p in rows:
                model = (p.task_models or {}).get(task)
                key = decrypt(p.api_key_enc)
                if model and key:
                    out.append({"id": p.id, "name": p.name, "base_url": p.base_url.rstrip("/"),
                                "key": key, "model": model})
        return out

    def _why_none(self, task: str) -> str:
        """Say which of enabled / key / model is missing, instead of a bare 'none'."""
        from ..db import SessionLocal
        from ..models import AIProvider
        from .crypto import decrypt
        with SessionLocal() as db:
            rows = db.query(AIProvider).all()
        ready_but_off = [p.name for p in rows if not p.enabled
                         and (p.task_models or {}).get(task) and decrypt(p.api_key_enc)]
        if ready_but_off:
            return (f"no enabled provider for '{task}' — {', '.join(ready_but_off)} "
                    f"has a key and model but is disabled; enable it in AI Engine")
        return f"no provider configured for '{task}' — add a key and pick a '{task}' model in AI Engine"

    # Reasoning models (deepseek-flash, o-series, ...) spend max_tokens on hidden
    # thinking first; a budget sized for the answer alone comes back empty with
    # finish_reason=length. Such providers get this floor, remembered in Redis.
    REASONING_BUDGET = 8000

    def _is_reasoning(self, provider_id: int) -> bool:
        return self.redis.exists(f"ai_reasoning:{provider_id}") == 1

    async def _call(self, p: dict, messages: list[dict], max_tokens: int,
                    temperature: float, json_mode: bool) -> httpx.Response:
        body = {"model": p["model"], "messages": messages,
                "max_tokens": max_tokens, "temperature": temperature}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=180) as client:
            return await client.post(f"{p['base_url']}/chat/completions", json=body,
                                     headers={"Authorization": f"Bearer {p['key']}"})

    async def chat(self, task: str, messages: list[dict], max_tokens: int = 800,
                   temperature: float = 0.1, json_mode: bool = False,
                   accept=None) -> tuple[str, dict]:
        """accept: optional check on the content; a reply it rejects falls through
        to the next provider instead of being returned."""
        providers = self._providers_for(task)
        if not providers:
            raise GatewayUnavailable(self._why_none(task))
        last_err = "all providers cooling/failing"
        for p in providers:
            if self._cooling(p["id"]):
                continue
            budget = max(max_tokens, self.REASONING_BUDGET) if self._is_reasoning(p["id"]) else max_tokens
            try:
                r = await self._call(p, messages, budget, temperature, json_mode)
                data = r.json() if r.status_code == 200 else None
                choice = data["choices"][0] if data else None
                # empty + truncated = the thinking ate the budget; retry once with room
                if (choice and choice.get("finish_reason") == "length"
                        and not (choice["message"].get("content") or "").strip()
                        and budget < self.REASONING_BUDGET):
                    self.redis.set(f"ai_reasoning:{p['id']}", "1", ex=7 * 86400)
                    log.info("%s is a reasoning model; retrying with %s tokens",
                             p["name"], self.REASONING_BUDGET)
                    r = await self._call(p, messages, self.REASONING_BUDGET, temperature, json_mode)
                    data = r.json() if r.status_code == 200 else None
            except httpx.HTTPError as e:
                last_err = f"{p['name']}: {e}"
                self._cool(p["id"], 60)
                continue
            if r.status_code in (401, 403, 429) or r.status_code >= 500:
                last_err = f"{p['name']}: {r.status_code} {r.text[:120]}"
                self._cool(p["id"], 300)
                continue
            if r.status_code != 200:
                last_err = f"{p['name']}: {r.status_code} {r.text[:120]}"
                continue
            content = data["choices"][0]["message"].get("content") or ""
            usage = data.get("usage", {}) or {}
            self._record(task, p["name"], data.get("model", p["model"]),
                         usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            if not content.strip() or (accept and not accept(content)):
                last_err = f"{p['name']}: unusable reply ({content[:80]!r})"
                continue
            return content, {"provider": p["name"], "model": p["model"]}
        raise GatewayUnavailable(last_err)

    def available(self, task: str) -> bool:
        """Is at least one provider configured + enabled for this task? (ignores
        transient cooldowns.) Lets callers skip expensive prep when the AI is off."""
        return bool(self._providers_for(task))

    async def chat_json(self, task: str, messages: list[dict], max_tokens: int = 800) -> dict:
        content, _ = await self.chat(task, messages, max_tokens=max_tokens, json_mode=True,
                                     accept=_is_json)
        return _extract_json(content)

    async def embed(self, texts: list[str]) -> list[list[float]] | None:
        providers = self._providers_for("embed")
        for p in providers:
            if self._cooling(p["id"]):
                continue
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    r = await client.post(f"{p['base_url']}/embeddings",
                                          json={"model": p["model"], "input": texts},
                                          headers={"Authorization": f"Bearer {p['key']}"})
                if r.status_code != 200:
                    # only rate/auth/server errors mean the provider is unwell; a 400/404
                    # (usually a chat model picked for embed) must not cool it for judge too
                    if r.status_code in (401, 403, 429) or r.status_code >= 500:
                        self._cool(p["id"], 300)
                    continue
                data = r.json()
                self._record("embed", p["name"], p["model"],
                             (data.get("usage") or {}).get("prompt_tokens", 0), 0)
                return [d["embedding"] for d in data["data"]]
            except httpx.HTTPError:
                self._cool(p["id"], 60)
        return None  # caller falls back to TF-IDF

    async def test_provider(self, base_url: str, api_key: str, model: str) -> dict:
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(f"{base_url.rstrip('/')}/chat/completions",
                                      headers={"Authorization": f"Bearer {api_key}"},
                                      json={"model": model, "max_tokens": 2,
                                            "messages": [{"role": "user", "content": "ping"}]})
            ms = int((time.monotonic() - t0) * 1000)
            if r.status_code == 200:
                return {"ok": True, "latency_ms": ms, "served_model": r.json().get("model", model)}
            return {"ok": False, "latency_ms": ms, "error": f"{r.status_code}: {r.text[:160]}"}
        except httpx.HTTPError as e:
            return {"ok": False, "error": str(e)}

    async def list_models(self, base_url: str, api_key: str) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                r = await client.get(f"{base_url.rstrip('/')}/models",
                                     headers={"Authorization": f"Bearer {api_key}"})
            if r.status_code != 200:
                return []
            data = r.json().get("data", [])
            return sorted(m.get("id") for m in data if m.get("id"))
        except httpx.HTTPError:
            return []

    def _record(self, task, provider, model, prompt_tokens, completion_tokens):
        try:
            from ..db import SessionLocal
            from ..models import TokenUsage
            with SessionLocal() as db:
                db.add(TokenUsage(task=task, model=model, provider=provider,
                                  prompt_tokens=prompt_tokens or 0,
                                  completion_tokens=completion_tokens or 0))
                db.commit()
        except Exception:  # noqa: BLE001
            log.warning("token usage record failed", exc_info=True)


def _is_json(text: str) -> bool:
    try:
        _extract_json(text)
        return True
    except ValueError:  # json.JSONDecodeError is a ValueError too
        return False


def _extract_json(text: str) -> dict:
    import json
    import re
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object")
    return json.loads(text[start:end + 1])


gateway = Gateway()
