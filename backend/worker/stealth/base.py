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

    def _pick_session(self, db: DbSession):
        """Least-recently-used ready session under its daily cap. Prefer sessions
        that HAVE cookies (can see walled content) over bare public ones."""
        q = (db.query(StealthSession)
             .filter(StealthSession.platform == self.platform,
                     StealthSession.status == "ready",
                     StealthSession.daily_used < StealthSession.daily_cap)
             .order_by(StealthSession.cookie_ref.isnot(None).desc(),
                       StealthSession.last_used_at.asc().nulls_first()))
        return q.first()

    async def fetch(self, cq) -> list[RawMention]:
        from app.services.boolean_query import to_api_terms
        if self.db is None:
            return []                              # not a real fetch context (UI listing)
        # Own a private DB session: fetch() runs concurrently with other connectors in
        # the pipeline's Phase 1, so it must NOT touch the shared pipeline session.
        from app.db import SessionLocal
        with SessionLocal() as db:
            session = self._pick_session(db)
            if session is None:
                log.info("%s: no ready session under daily cap", self.platform)
                return []
            if not await self.client.health():
                raise RuntimeError("camofox not running (start the camofox service)")

            terms = to_api_terms(cq, self.search_terms_cap)
            if not terms:
                return []
            has_cookies = bool(session.cookie_ref)
            label = session.label
            user_id = session.cookie_ref or f"{self.platform}-{session.id}"
            tab = await self.client.open_tab(self.search_url(terms[0]), user_id)
            try:
                await human_dwell()
                snapshot, _ = await self.client.snapshot_text(tab, user_id)
                session.daily_used += 1
                session.last_used_at = datetime.now(timezone.utc)
                if session.daily_used >= session.daily_cap:
                    session.status = "resting"  # rotate away; nightly resets it
                db.commit()

                if looks_like_login_wall(snapshot):
                    if has_cookies:
                        # cookies present but still walled -> they expired
                        session.status = "needs_reauth"
                        db.commit()
                        raise LoginRequired(
                            f"“{label}” is connected but its cookies expired — "
                            f"reconnect it on Sources to resume logged-in crawling.")
                    # No cookies on THIS session, but the platform may still have an
                    # account that is merely expired or resting. Say which — otherwise a
                    # connected-but-unusable account reads as "no account connected",
                    # which is exactly what made Facebook look unconnected when it wasn't.
                    other = (db.query(StealthSession)
                             .filter(StealthSession.platform == self.platform,
                                     StealthSession.cookie_ref.isnot(None))
                             .order_by(StealthSession.id).first())
                    if other is not None:
                        raise LoginRequired(
                            f"“{other.label}” is connected but not usable right now "
                            f"({other.status}) — crawling logged-out until it is.")
                    raise LoginRequired(
                        f"No {self.platform} account connected — log in on Sources "
                        f"to crawl as a real account.")

                posts = extract_posts(self.platform, snapshot)
                if posts:
                    return posts
                # no structured posts from the heuristic -> let the AI agent read the text
                raise SelectorBroken(f"{self.platform}: heuristic found nothing", snapshot)
            finally:
                await self.client.close_tab(tab, user_id)
