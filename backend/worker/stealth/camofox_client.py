"""Client for the camofox-browser REST server (anti-detect Firefox).

camofox API shape (verified against the running server):
  POST   /tabs                        {url, userId, sessionKey} -> {tabId, url}
  GET    /tabs/:id/snapshot?userId=   -> {url, snapshot(TEXT aria tree), truncated}
  POST   /tabs/:id/navigate?userId=   {url}
  DELETE /tabs/:id?userId=
  POST   /sessions/:userId/cookies    {cookies:[...]}
The snapshot is a token-efficient TEXT accessibility tree (designed for LLM agents),
not JSON — so extraction reads the text, not a node graph.
"""
import asyncio
import random

import httpx

from app.config import settings


class CamofoxError(Exception):
    pass


class SelectorBroken(Exception):
    """Layout changed or content is behind a wall — hand the snapshot to the agent."""
    def __init__(self, msg: str, snapshot: str = ""):
        super().__init__(msg)
        self.snapshot = snapshot


class LoginRequired(Exception):
    """The platform served a login wall to this (anonymous) session."""


class CamofoxClient:
    def __init__(self):
        self.base = settings.camofox_url.rstrip("/")
        self.headers = ({"Authorization": f"Bearer {settings.camofox_access_key}"}
                        if settings.camofox_access_key else {})

    async def _req(self, method: str, path: str, **kw) -> dict:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.request(method, f"{self.base}{path}", headers=self.headers, **kw)
            r.raise_for_status()
            return r.json() if r.content else {}
        except httpx.HTTPError as e:
            raise CamofoxError(f"{method} {path}: {e}") from e

    async def open_tab(self, url: str, user_id: str) -> str:
        data = await self._req("POST", "/tabs",
                               json={"url": url, "userId": user_id, "sessionKey": user_id})
        return data.get("tabId") or data.get("id")

    async def navigate(self, tab_id: str, url: str, user_id: str) -> None:
        await self._req("POST", f"/tabs/{tab_id}/navigate",
                        params={"userId": user_id}, json={"url": url})

    async def snapshot_text(self, tab_id: str, user_id: str) -> tuple[str, str]:
        """Returns (snapshot_text, final_url)."""
        data = await self._req("GET", f"/tabs/{tab_id}/snapshot", params={"userId": user_id})
        return data.get("snapshot", "") or "", data.get("url", "")

    async def close_tab(self, tab_id: str, user_id: str) -> None:
        try:
            await self._req("DELETE", f"/tabs/{tab_id}", params={"userId": user_id})
        except CamofoxError:
            pass

    async def import_cookies(self, user_id: str, cookies: list[dict]) -> None:
        # cookie import is gated behind CAMOFOX_API_KEY, sent as a bearer token,
        # and requires the session (tab) to exist first
        await self._req("POST", "/tabs",
                        json={"url": "about:blank", "userId": user_id, "sessionKey": user_id})
        headers = {"Authorization": f"Bearer {settings.camofox_api_key}"}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{self.base}/sessions/{user_id}/cookies",
                                  json={"cookies": cookies}, headers=headers)
        if r.status_code >= 300:
            raise CamofoxError(f"cookie import failed: {r.status_code} {r.text[:200]}")

    async def health(self) -> bool:
        try:
            await self._req("GET", "/health")
            return True
        except CamofoxError:
            return False


LOGIN_WALL_MARKERS = ("log in", "login", "sign in", "log into", "create new account",
                      "log in to continue", "see more on")


def looks_like_login_wall(snapshot: str) -> bool:
    s = (snapshot or "").lower()
    if len(s) < 400:  # near-empty page = redirected/blocked
        return True
    return any(m in s for m in LOGIN_WALL_MARKERS) and "article" not in s


async def human_dwell(low: float = 2.0, high: float = 8.0) -> None:
    await asyncio.sleep(random.uniform(low, high))
