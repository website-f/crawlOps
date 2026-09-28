"""Per-platform stealth connectors — thin URL builders over StealthConnector."""
from urllib.parse import quote

from .base import StealthConnector


class FacebookStealth(StealthConnector):
    key = "facebook_stealth"
    platform = "facebook"

    def search_url(self, term: str) -> str:
        return f"https://www.facebook.com/search/posts/?q={quote(term)}"


class InstagramStealth(StealthConnector):
    key = "instagram_stealth"
    platform = "instagram"

    def search_url(self, term: str) -> str:
        # hashtag-style discovery works logged-out for public tags
        tag = "".join(ch for ch in term.lower() if ch.isalnum())
        return f"https://www.instagram.com/explore/tags/{tag}/"


class TikTokStealth(StealthConnector):
    key = "tiktok_stealth"
    platform = "tiktok"

    def search_url(self, term: str) -> str:
        return f"https://www.tiktok.com/search?q={quote(term)}"


class XStealth(StealthConnector):
    key = "x_stealth"
    platform = "x"

    def search_url(self, term: str) -> str:
        return f"https://x.com/search?q={quote(term)}&f=live"


class ThreadsStealth(StealthConnector):
    key = "threads_stealth"
    platform = "threads"

    def search_url(self, term: str) -> str:
        return f"https://www.threads.net/search?q={quote(term)}&serp_type=default"
