"""Interactive login service — Playwright-driven Camoufox (anti-detect Firefox).

Unlike the camofox-browser REST API (selector/ref-based, flaky), Playwright gives
reliable coordinate clicks + real keyboard events, so the operator can drive a live
login page from CrawlOps: see the real page as a screenshot stream, click and type
on it (handling 2FA/CAPTCHA themselves), and on success we capture the session
cookies. No passwords are stored — the operator types them into the live page.
"""
import asyncio
import random
import secrets
import time
from contextlib import suppress

from camoufox.async_api import AsyncCamoufox
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

VIEWPORT = {"width": 1280, "height": 800}
IDLE_TIMEOUT = 900  # close abandoned sessions after 15 min

LOGIN_URLS = {
    "facebook": "https://www.facebook.com/login",
    "instagram": "https://www.instagram.com/accounts/login/",
    "tiktok": "https://www.tiktok.com/login",
    "x": "https://x.com/login",
    "threads": "https://www.threads.net/login",
}

sessions: dict[str, dict] = {}
app = FastAPI(title="CrawlOps login service")


async def _gc():
    while True:
        await asyncio.sleep(60)
        now = time.time()
        for sid in list(sessions):
            if now - sessions[sid]["last"] > IDLE_TIMEOUT:
                await _close(sid)


@app.on_event("startup")
async def _startup():
    asyncio.create_task(_gc())


async def _close(sid: str):
    s = sessions.pop(sid, None)
    if s:
        with suppress(Exception):
            await s["cm"].__aexit__(None, None, None)


def _get(sid: str) -> dict:
    s = sessions.get(sid)
    if not s:
        raise HTTPException(404, "session expired or closed")
    s["last"] = time.time()
    return s


@app.get("/health")
async def health():
    return {"ok": True, "sessions": len(sessions)}


class StartIn(BaseModel):
    platform: str
    proxy: str | None = None


@app.post("/session")
async def start(b: StartIn):
    url = LOGIN_URLS.get(b.platform)
    if not url:
        raise HTTPException(400, f"unknown platform '{b.platform}'")
    kwargs: dict = {"headless": True, "humanize": True, "os": "windows"}
    if b.proxy:
        kwargs["proxy"] = {"server": b.proxy}
    cm = AsyncCamoufox(**kwargs)
    browser = await cm.__aenter__()
    page = await browser.new_page(viewport=VIEWPORT)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception:  # noqa: BLE001 - some login pages never fully settle; keep going
        pass
    sid = secrets.token_hex(8)
    sessions[sid] = {"cm": cm, "browser": browser, "page": page,
                     "platform": b.platform, "last": time.time()}
    return {"sid": sid, **VIEWPORT}


@app.get("/session/{sid}/frame")
async def frame(sid: str):
    s = _get(sid)
    try:
        png = await s["page"].screenshot(type="jpeg", quality=55, timeout=15000)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"frame failed: {e}") from e
    return Response(content=png, media_type="image/jpeg",
                    headers={"Cache-Control": "no-store"})


class XY(BaseModel):
    x: float
    y: float


@app.post("/session/{sid}/click")
async def click(sid: str, b: XY):
    s = _get(sid)
    await s["page"].mouse.move(b.x, b.y, steps=random.randint(4, 12))
    await asyncio.sleep(random.uniform(0.04, 0.14))
    await s["page"].mouse.click(b.x, b.y)
    return {"ok": True}


class TypeIn(BaseModel):
    text: str


@app.post("/session/{sid}/type")
async def type_text(sid: str, b: TypeIn):
    s = _get(sid)
    for ch in b.text:
        await s["page"].keyboard.type(ch, delay=random.randint(45, 155))
    return {"ok": True}


class KeyIn(BaseModel):
    key: str  # e.g. Enter, Tab, Backspace, ArrowDown


@app.post("/session/{sid}/key")
async def key(sid: str, b: KeyIn):
    s = _get(sid)
    await s["page"].keyboard.press(b.key)
    return {"ok": True}


class ScrollIn(BaseModel):
    dy: float


@app.post("/session/{sid}/scroll")
async def scroll(sid: str, b: ScrollIn):
    s = _get(sid)
    await s["page"].mouse.wheel(0, b.dy)
    return {"ok": True}


@app.post("/session/{sid}/finish")
async def finish(sid: str):
    s = _get(sid)
    cookies = await s["page"].context.cookies()
    platform = s["platform"]
    await _close(sid)
    return {"platform": platform, "cookies": cookies}


@app.delete("/session/{sid}")
async def close(sid: str):
    await _close(sid)
    return {"ok": True}
