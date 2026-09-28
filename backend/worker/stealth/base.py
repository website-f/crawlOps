"""Shared Tier-3 stealth connector base (docs/ALGORITHMS.md §3).

Subclasses only supply a platform name and a search-URL builder. This base owns:
session selection under daily cap, camofox tab lifecycle, human dwell pacing,
snapshot extraction against the current selector map, and the AI-agent self-heal
fallback when the layout changes.

All of this scrapes PUBLIC content only, at low per-session volume, and violates
the target platforms' ToS — sessions/IPs get burned; the pool design absorbs it.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

from app.models import SelectorPatch, StealthSession

from ..connectors.base import Connector, RawMention
from .camofox_client import CamofoxClient, SelectorBroken, human_dwell

log = logging.getLogger("stealth")

DEFAULT_SELECTORS = {
    "post_container": "article",
    "author": "link",
    "text": "text",
    "timestamp": "time",
}


class StealthConnector(Connector):
    tier = 3
    search_terms_cap = 1  # keep per-session volume low

    def __init__(self, db: DbSession | None = None):
        self.db = db
        self.client = CamofoxClient()

    def enabled(self) -> bool:
        return True  # gated at runtime; listed so the Sources UI shows state

    def disabled_reason(self) -> str:
        return f"Needs camofox (--profile stealth) + a ready {self.platform} session"

    def search_url(self, term: str) -> str:
        raise NotImplementedError

    async def fetch(self, cq) -> list[RawMention]:
        from app.services.boolean_query import to_api_terms
        if self.db is None:
            return []
        session = (self.db.query(StealthSession)
                   .filter(StealthSession.platform == self.platform,
                           StealthSession.status == "ready",
                           StealthSession.daily_used < StealthSession.daily_cap)
                   .first())
        if session is None:
            log.info("%s: no ready session under daily cap — skipping", self.platform)
            return []
        if not await self.client.health():
            log.info("%s: camofox not running (start with --profile stealth)", self.platform)
            return []

        terms = to_api_terms(cq, self.search_terms_cap)
        if not terms:
            return []
        tab = await self.client.open_tab(self.search_url(terms[0]),
                                         user_id=f"{self.platform}-{session.id}")
        try:
            await human_dwell()
            snap = await self.client.snapshot(tab)
            posts = self._extract(snap)
            session.daily_used += 1
            session.last_used_at = datetime.now(timezone.utc)
            self.db.commit()
            return posts
        except SelectorBroken as e:
            e.snapshot = snap if "snap" in dir() else {}  # hand snapshot to the agent
            raise
        finally:
            await self.client.close_tab(tab)

    def _extract(self, snapshot: dict) -> list[RawMention]:
        nodes = _find_role(snapshot, "article")
        if not nodes:
            err = SelectorBroken(f"{self.platform}: no article nodes in snapshot")
            err.snapshot = snapshot
            raise err
        out = []
        for i, node in enumerate(nodes[:20]):
            text = _text_of(node)[:1500]
            if not text:
                continue
            author = _first_role_name(node, "link") or "unknown"
            out.append(RawMention(
                platform=self.platform,
                native_id=f"{self.platform}:{hash(text) & 0xFFFFFFFF}:{i}",
                url="", text=text, author_key=author, author_name=author,
                posted_at=datetime.now(timezone.utc)))
        return out


def _find_role(node, role, out=None):
    if out is None:
        out = []
    if isinstance(node, dict):
        if node.get("role") == role:
            out.append(node)
        for c in node.get("children", []) or []:
            _find_role(c, role, out)
    elif isinstance(node, list):
        for c in node:
            _find_role(c, role, out)
    return out


def _text_of(node) -> str:
    if not isinstance(node, dict):
        return ""
    parts = [str(node["name"])] if node.get("name") else []
    for c in node.get("children", []) or []:
        parts.append(_text_of(c))
    return " ".join(p for p in parts if p).strip()


def _first_role_name(node, role) -> str:
    if not isinstance(node, dict):
        return ""
    if node.get("role") == role and node.get("name"):
        return str(node["name"])
    for c in node.get("children", []) or []:
        found = _first_role_name(c, role)
        if found:
            return found
    return ""
