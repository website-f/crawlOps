"""API-first, crawler-fallback connector.

Tries each connector in order and returns the first non-empty result. So a platform
with an official API uses it when a key is present, and automatically falls back to
the camofox stealth crawler when the API is dormant, rate-limited, or returns nothing.
"""
import logging

from app.services.boolean_query import CompiledQuery

from .base import Connector, RawMention

log = logging.getLogger("connectors.fallback")


class FallbackConnector(Connector):
    def __init__(self, platform: str, chain: list[Connector]):
        self.platform = platform
        self.chain = [c for c in chain if c is not None]
        self.tier = min((c.tier for c in self.chain), default=1)

    def enabled(self) -> bool:
        return any(c.enabled() for c in self.chain)

    def disabled_reason(self) -> str:
        return " / ".join(c.disabled_reason() for c in self.chain if not c.enabled())

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        for c in self.chain:
            if not c.enabled():
                continue
            try:
                res = await c.fetch(cq)
            except Exception as e:  # noqa: BLE001 — try the next path in the chain
                log.warning("%s: %s failed (%s), falling back", self.platform,
                            type(c).__name__, e)
                continue
            if res:
                log.info("%s: served %d via %s", self.platform, len(res), type(c).__name__)
                return res
        return []
