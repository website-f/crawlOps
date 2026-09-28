"""Thin client for the camofox-browser REST server (anti-detect Firefox).

Tab lifecycle: create -> navigate/snapshot loop -> close. Human pacing lives in
the platform scripts, not here.
"""
import asyncio
import random

import httpx

from app.config import settings


class CamofoxError(Exception):
    pass


class SelectorBroken(Exception):
    """Platform layout changed — deterministic script can't find its anchors."""


class CamofoxClient:
    def __init__(self):
        self.base = settings.camofox_url.rstrip("/")
        self.headers = ({"Authorization": f"Bearer {settings.camofox_access_key}"}
                        if settings.camofox_access_key else {})

    async def _req(self, method: str, path: str, **kw) -> dict:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.request(method, f"{self.base}{path}",
                                         headers=self.headers, **kw)
            r.raise_for_status()
            return r.json() if r.content else {}
        except httpx.HTTPError as e:
            raise CamofoxError(f"{method} {path}: {e}") from e

    async def open_tab(self, url: str, user_id: str | None = None) -> str:
        body = {"url": url}
        if user_id:
            body["userId"] = user_id  # binds the camofox per-user sticky proxy + cookie jar
        data = await self._req("POST", "/tabs", json=body)
        return data.get("id") or data.get("tabId")

    async def navigate(self, tab_id: str, url: str) -> None:
        await self._req("POST", f"/tabs/{tab_id}/navigate", json={"url": url})

    async def snapshot(self, tab_id: str) -> dict:
        """Accessibility snapshot with stable element refs — token-efficient for agents."""
        return await self._req("GET", f"/tabs/{tab_id}/snapshot")

    async def close_tab(self, tab_id: str) -> None:
        try:
            await self._req("DELETE", f"/tabs/{tab_id}")
        except CamofoxError:
            pass

    async def import_cookies(self, user_id: str, cookies: list[dict]) -> None:
        await self._req("POST", f"/sessions/{user_id}/cookies", json={"cookies": cookies})

    async def health(self) -> bool:
        try:
            await self._req("GET", "/health")
            return True
        except CamofoxError:
            return False


async def human_dwell(low: float = 2.0, high: float = 8.0) -> None:
    """Randomized think-time between page actions (docs/ALGORITHMS.md §3)."""
    await asyncio.sleep(random.uniform(low, high))
