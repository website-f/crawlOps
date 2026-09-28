"""Telegram connector via public t.me/s/<channel> web preview — keyless.

Only works for public channels (the /s/ preview page). Channels are configured on
the Source (config.channels = ["durov", "telegram"]). No MTProto, no API creds,
no session — just the same HTML a logged-out visitor sees.
"""
import html
import re
from datetime import datetime, timezone

import httpx
from dateutil import parser as dtparse

from app.services.boolean_query import CompiledQuery

from .base import UA, Connector, RawMention, collect

_MSG = re.compile(
    r'<div class="tgme_widget_message[^"]*"[^>]*data-post="([^"]+)".*?'
    r'(?:<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>)?'
    r'<a class="tgme_widget_message_date"[^>]*href="[^"]*"[^>]*>.*?'
    r'<time[^>]*datetime="([^"]+)"',
    re.S)
_TAGS = re.compile(r"<[^>]+>")
_BR = re.compile(r"<br\s*/?>", re.I)


class Telegram(Connector):
    key = "telegram"
    platform = "telegram"

    def __init__(self, channels: list[str] | None = None):
        self.channels = channels or []

    def enabled(self) -> bool:
        return bool(self.channels)

    def disabled_reason(self) -> str:
        return "Add public channel usernames in the source config (config.channels)"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        return await collect(self._channel(c.lstrip("@")) for c in self.channels[:15])

    async def _channel(self, channel: str) -> list[RawMention]:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(f"https://t.me/s/{channel}", headers={"User-Agent": UA})
        if r.status_code != 200:
            return []
        out = []
        for post_id, text_html, dt in _MSG.findall(r.text):
            text = _TAGS.sub(" ", _BR.sub("\n", html.unescape(text_html or ""))).strip()
            if not text:
                continue
            out.append(RawMention(
                platform="telegram", native_id=post_id,
                url=f"https://t.me/{post_id}",
                text=text[:1500],
                author_key=channel, author_name=channel, author_handle=f"@{channel}",
                community=channel,
                posted_at=dtparse.parse(dt) if dt else datetime.now(timezone.utc)))
        return out
