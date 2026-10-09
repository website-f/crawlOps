"""Agentic dark-web researcher — browser-use driving Chromium over Tor.

One investigation per /research call: the backend hands us a single already-discovered
.onion (or clearnet) URL plus the DeepSeek credentials to use as the agent's brain, and
we return structured findings. The backend owns discovery (Ahmia + seeds), cost control
(how many sites, how often), and the warehouse — this service is a stateless worker so
the heavy deps (Chromium + agent loop) stay isolated, exactly like loginsvc.

SAFETY — passive observation only. The task prompt forbids logging in, registering,
submitting any form, downloading files, or transacting. We read and extract; nothing else.
"""
import asyncio
import json
import logging
import os
import re

from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("darkweb-agent")

TOR_SOCKS = os.environ.get("TOR_SOCKS", "socks5://tor:9050")
CHROMIUM_PATH = os.environ.get("CHROMIUM_PATH") or None   # set in the image; browser-use drives it
app = FastAPI(title="CrawlOps dark-web agent")

# Hard caps so one call can never run away (slow Tor + per-step LLM cost).
MAX_STEPS_CAP = 14
GLOBAL_CONCURRENCY = asyncio.Semaphore(1)   # one Chromium at a time on a shared box

_TASK = """You are a defensive threat-intelligence analyst. FIRST, open this URL: {url}
Then your ONLY goal is to observe and report whether this site contains material relevant to:

    {query}

STRICT RULES (safety + legality — never break these):
- PASSIVE OBSERVATION ONLY. Do NOT log in, register, create an account, enter credentials,
  submit any form, click "buy"/"download"/"contact", or transact in any way.
- Only read visible content and follow at most {max_links} in-site links that look relevant.
- If the site asks you to log in or solve a captcha, do not — just report what is visible.

When done, output ONLY a JSON object, no prose:
{{"relevant": true|false,
  "summary": "<2-3 sentence factual summary of what the site is and any relevance>",
  "findings": [{{"title": "...", "text": "<the relevant excerpt>", "url": "<permalink if any>",
                "iocs": ["<emails/domains/wallets/handles seen>"]}}]}}
If nothing is relevant, return relevant=false with an empty findings list."""


class ResearchIn(BaseModel):
    query: str
    url: str
    llm: dict                 # {base_url, api_key, model}
    max_steps: int = 10
    max_links: int = 3


class Finding(BaseModel):
    title: str = ""
    text: str = ""
    url: str = ""
    iocs: list = []


class ResearchOut(BaseModel):
    ok: bool
    url: str
    relevant: bool = False
    summary: str = ""
    findings: list[Finding] = []
    error: str | None = None
    steps: int = 0


def _parse(raw: str) -> dict:
    if not raw:
        return {}
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S)
    s, e = raw.find("{"), raw.rfind("}")
    if s == -1 or e == -1:
        return {}
    try:
        return json.loads(raw[s:e + 1])
    except ValueError:
        return {}


async def _investigate(body: ResearchIn) -> ResearchOut:
    from browser_use import Agent
    from browser_use.browser.profile import BrowserProfile, ProxySettings
    from browser_use.browser.session import BrowserSession
    from browser_use.llm import ChatOpenAI

    llm = ChatOpenAI(model=body.llm.get("model", "deepseek-flash"),
                     base_url=body.llm.get("base_url", "https://api.deepseek.com/v1"),
                     api_key=body.llm.get("api_key", ""), temperature=0.0)
    profile = BrowserProfile(
        headless=True,
        executable_path=CHROMIUM_PATH,
        proxy=ProxySettings(server=TOR_SOCKS),
        # a plain profile on Tor: do NOT randomize a unique fingerprint here — on Tor the
        # anonymity set is "everyone looks the same", so uniqueness is counter-productive.
        args=["--no-sandbox", "--disable-dev-shm-usage",
              # resolve .onion at the SOCKS proxy, never locally
              "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE tor"],
    )
    session = BrowserSession(browser_profile=profile)
    task = _TASK.format(url=body.url, query=body.query,
                        max_links=max(0, min(body.max_links, 5)))
    steps = max(2, min(body.max_steps, MAX_STEPS_CAP))
    agent = Agent(task=task, llm=llm, browser_session=session)
    try:
        history = await agent.run(max_steps=steps)
        raw = history.final_result() if hasattr(history, "final_result") else str(history)
        data = _parse(raw or "")
        return ResearchOut(
            ok=True, url=body.url,
            relevant=bool(data.get("relevant")),
            summary=(data.get("summary") or "")[:2000],
            findings=[Finding(**{k: f.get(k) for k in ("title", "text", "url", "iocs")
                                 if k in f}) for f in (data.get("findings") or [])[:20]
                      if isinstance(f, dict)],
            steps=steps)
    finally:
        try:
            await session.kill()
        except Exception:  # noqa: BLE001
            pass


@app.post("/research", response_model=ResearchOut)
async def research(body: ResearchIn) -> ResearchOut:
    async with GLOBAL_CONCURRENCY:
        try:
            return await asyncio.wait_for(_investigate(body), timeout=300)
        except asyncio.TimeoutError:
            return ResearchOut(ok=False, url=body.url, error="agent timed out")
        except Exception as e:  # noqa: BLE001
            log.exception("research failed")
            return ResearchOut(ok=False, url=body.url, error=f"{type(e).__name__}: {e}"[:300])


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "tor": TOR_SOCKS}
