"""Shared Tier-3 stealth connector base (docs/ALGORITHMS.md §3).

Flow: pick a ready session under its daily cap -> open the platform search page in
camofox under the session's sticky identity -> read the TEXT accessibility snapshot
-> if it's a login wall, raise LoginRequired (surfaced as an actionable source
status) -> else extract posts. Extraction prefers the AI agent (the snapshot is
LLM-optimized text) and falls back to a keyless text heuristic.

Public search on Facebook/Instagram/TikTok/X/Threads is login-walled: an anonymous
session sees only a "Log in" page, exactly like a human in incognito. Import an
account's cookies (Sources -> stealth session -> cookies) to browse as that logged-in
human. camofox defeats fingerprinting, not the login requirement itself.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

from app.models import StealthSession

from ..connectors.base import Connector, RawMention
from .camofox_client import (CamofoxClient, LoginRequired, SelectorBroken,
                             human_dwell, looks_like_login_wall)
from .snapshot_parse import extract_posts

log = logging.getLogger("stealth")


class StealthConnector(Connector):
    tier = 3
    search_terms_cap = 1  # keep per-session volume low / human-like

    def __init__(self, db: DbSession | None = None):
        self.db = db
        self.client = CamofoxClient()

    def enabled(self) -> bool:
        return True  # gated at runtime; listed so the Sources UI shows state

    def disabled_reason(self) -> str:
        return f"Needs camofox running + a {self.platform} session with imported cookies"

    def search_url(self, term: str) -> str:
        raise NotImplementedError

    def _pick_session(self):
        """Least-recently-used ready session under its daily cap. Prefer sessions
        that HAVE cookies (can see walled content) over bare public ones."""
        q = (self.db.query(StealthSession)
             .filter(StealthSession.platform == self.platform,
                     StealthSession.status == "ready",
                     StealthSession.daily_used < StealthSession.daily_cap)
             .order_by(StealthSession.cookie_ref.isnot(None).desc(),
                       StealthSession.last_used_at.asc().nulls_first()))
        return q.first()

    async def fetch(self, cq) -> list[RawMention]:
        from app.services.boolean_query import to_api_terms
        if self.db is None:
            return []
        session = self._pick_session()
        if session is None:
            log.info("%s: no ready session under daily cap", self.platform)
            return []
        if not await self.client.health():
            raise RuntimeError("camofox not running (start the camofox service)")

        terms = to_api_terms(cq, self.search_terms_cap)
        if not terms:
            return []
        has_cookies = bool(session.cookie_ref)
        user_id = session.cookie_ref or f"{self.platform}-{session.id}"
        tab = await self.client.open_tab(self.search_url(terms[0]), user_id)
        try:
            await human_dwell()
            snapshot, _ = await self.client.snapshot_text(tab, user_id)
            session.daily_used += 1
            session.last_used_at = datetime.now(timezone.utc)
            if session.daily_used >= session.daily_cap:
                session.status = "resting"  # rotate away; nightly resets it
            self.db.commit()

            if looks_like_login_wall(snapshot):
                if has_cookies:
                    # cookies present but still walled -> they expired
                    session.status = "needs_reauth"
                    self.db.commit()
                    raise LoginRequired(
                        f"{self.platform} session '{session.label}' cookies expired. "
                        f"Re-import fresh cookies in Sources -> stealth session.")
                raise LoginRequired(
                    f"{self.platform} needs login. Import an account's cookies in "
                    f"Sources -> stealth session to crawl logged-in.")

            posts = extract_posts(self.platform, snapshot)
            if posts:
                return posts
            # no structured posts from the heuristic -> let the AI agent read the text
            raise SelectorBroken(f"{self.platform}: heuristic found nothing", snapshot)
        finally:
            await self.client.close_tab(tab, user_id)
