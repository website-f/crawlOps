"""Per-source credentials: what each connector needs, and where it is kept.

Keys used to live in the .env file, which meant a shell + a container restart to
connect a source, and one shared key per connector for the whole deployment. They
now live in the database: secrets encrypted with the same Fernet key as the AI
provider keys (see crypto.py), non-secret settings (feed URLs, channel names) in
plain `Source.config` so they stay greppable and diffable.

`.env` is still read as a fallback so an existing deployment keeps working after an
upgrade without re-entering anything — the DB wins when both are set.
"""
from ..config import settings
from .crypto import decrypt, encrypt, mask

# type: "secret" -> encrypted, write-only, UI shows a masked hint
#       "text"   -> plain string in config
#       "list"   -> newline-separated list in config
FIELD_SPECS: dict[str, list[dict]] = {
    "youtube": [
        {"key": "api_key", "type": "secret", "label": "YouTube Data API key", "required": True,
         "help": "Google Cloud → APIs & Services → Credentials → API key, then enable "
                 "“YouTube Data API v3”. Free tier: 10,000 units/day (~100 searches).",
         "placeholder": "AIza…"},
    ],
    "threads": [
        {"key": "access_token", "type": "secret", "label": "Threads access token", "required": True,
         "help": "A Meta app token with the threads_keyword_search scope. ~2,200 "
                 "queries/user/day. Without it, Threads falls back to the stealth crawler.",
         "placeholder": "THAA…"},
    ],
    "factcheck": [
        {"key": "api_key", "type": "secret", "label": "Google Fact Check Tools API key",
         "required": True, "placeholder": "AIza…",
         "help": "Same Google Cloud console as YouTube; enable “Fact Check Tools API”. Free."},
    ],
    "podcastindex": [
        {"key": "api_key", "type": "secret", "label": "Podcast Index API key", "required": True,
         "help": "Free key from podcastindex.org/developer.", "placeholder": "ABCD…"},
        {"key": "api_secret", "type": "secret", "label": "Podcast Index API secret",
         "required": True, "help": "Issued together with the key.", "placeholder": ""},
    ],
    "places": [
        {"key": "api_key", "type": "secret", "label": "Google Places API key", "required": True,
         "help": "Billed per request — this is a paid Google API, unlike the others here.",
         "placeholder": "AIza…"},
        {"key": "place_ids", "type": "list", "label": "Place IDs (one per line)", "required": True,
         "help": "Find them with Google's Place ID finder.", "placeholder": "ChIJN1t_tDeuEmsRUsoyG83frY4"},
    ],
    "appstore": [
        {"key": "app_ids", "type": "list", "label": "App Store app IDs (one per line)",
         "required": True, "placeholder": "310633997",
         "help": "The numeric id in an App Store URL: apps.apple.com/app/id310633997. No key needed."},
        {"key": "country", "type": "text", "label": "Store country code", "required": False,
         "placeholder": "us", "help": "Two-letter store front, e.g. us, my, gb. Defaults to us."},
    ],
    "rss": [
        {"key": "feeds", "type": "list", "label": "RSS/Atom feed URLs (one per line)",
         "required": False, "placeholder": "https://techcrunch.com/feed/",
         "help": "Any feed URL. Polled with conditional GETs, so a quiet feed is nearly free."},
        {"key": "rsshub_routes", "type": "list", "label": "RSSHub routes (one per line)",
         "required": False, "placeholder": "/twitter/user/elonmusk",
         "help": "Served by the bundled RSSHub container — turns many sites into feeds."},
    ],
    "telegram": [
        {"key": "channels", "type": "list", "label": "Public channel usernames (one per line)",
         "required": False, "placeholder": "durov",
         "help": "Public channels only, read via t.me/s/<name>. No API key or login needed."},
    ],
}

# .env fallbacks, so an upgrade doesn't disconnect a source that already worked
_ENV_FALLBACK = {
    ("youtube", "api_key"): lambda: settings.youtube_api_key,
    ("threads", "access_token"): lambda: settings.threads_access_token,
}


def spec_for(connector: str) -> list[dict]:
    return FIELD_SPECS.get(connector, [])


def needs_credentials(connector: str) -> bool:
    return bool(FIELD_SPECS.get(connector))


def _secret_keys(connector: str) -> set:
    return {f["key"] for f in spec_for(connector) if f["type"] == "secret"}


def read_secrets(source) -> dict:
    """Decrypted secret values for this source (DB first, then .env fallback)."""
    import json
    out = {}
    raw = decrypt(getattr(source, "secrets_enc", "") or "")
    if raw:
        try:
            out = {k: v for k, v in json.loads(raw).items() if v}
        except ValueError:
            out = {}
    for key in _secret_keys(source.connector):
        if not out.get(key):
            fallback = _ENV_FALLBACK.get((source.connector, key))
            if fallback:
                val = fallback()
                if val:
                    out[key] = val
    return out


def write_secrets(source, values: dict) -> None:
    """Merge new secret values in. A blank value means 'keep the stored one', so the
    UI can show masked hints and submit the form without re-typing every key."""
    import json
    current = {}
    raw = decrypt(getattr(source, "secrets_enc", "") or "")
    if raw:
        try:
            current = json.loads(raw)
        except ValueError:
            current = {}
    for key in _secret_keys(source.connector):
        if key in values:
            new = (values.get(key) or "").strip()
            if new:
                current[key] = new
    source.secrets_enc = encrypt(json.dumps(current)) if current else ""


def clear_secrets(source) -> None:
    source.secrets_enc = ""


def effective_config(source) -> dict:
    """What build() should hand the connector: plain config + decrypted secrets."""
    cfg = dict(source.config or {})
    cfg.update(read_secrets(source))
    return cfg


def status_fields(source) -> list[dict]:
    """Per-field state for the UI — never the plaintext, only whether it is set."""
    cfg = source.config or {}
    secrets = read_secrets(source)
    out = []
    for f in spec_for(source.connector):
        if f["type"] == "secret":
            val = secrets.get(f["key"], "")
            out.append({**f, "set": bool(val), "hint": mask(val)})
        else:
            val = cfg.get(f["key"])
            filled = bool(val) if not isinstance(val, str) else bool(val.strip())
            out.append({**f, "set": filled,
                        "value": val if isinstance(val, (str, list)) else None})
    return out


def missing_required(source) -> list[str]:
    return [f["label"] for f in status_fields(source) if f.get("required") and not f["set"]]
