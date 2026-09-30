"""Runtime config in the app_settings KV table, with sane defaults.

Anything editable in the Settings UI lives here (not in .env), so a change takes
effect without a redeploy.
"""
from sqlalchemy.orm import Session

from ..models import AppSetting
from .crypto import decrypt, encrypt
from .scoring import CPM as DEFAULT_CPM

# notifier fields that are secrets: encrypted at rest, never returned in plaintext.
_NOTIFIER_SECRETS = ("webhook_url", "telegram_bot_token")
_MASK = "********"   # what the API shows for a stored secret; echoed back = "keep"

DEFAULTS: dict[str, dict] = {
    "cpm": DEFAULT_CPM,  # platform -> RM per 1000 impressions
    "notifiers": {
        "webhook_url": "",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
    },
    "pipeline": {
        "default_threshold": 55,
        "retention_days": 90,
    },
    # scheduled digest delivery (to the alert channels)
    "digest": {
        "enabled": False,
        "frequency": "daily",   # daily | weekly (Mondays)
        "hour": 8,              # UTC hour to send
        "topic_id": None,      # None = all topics
        "include_brief": True,
    },
    "issues": {
        "list": ["economy", "cost of living", "jobs", "healthcare", "education",
                 "security", "corruption", "environment", "infrastructure", "housing"],
    },
    # custom "impact" scoring — the team's own value framework (Meltwater beyond-AVE)
    "scoring": {
        "enabled": True,
        "w_relevance": 1.0, "w_reach": 1.0, "w_engagement": 1.0,
        "sentiment": {"pos": 1.0, "neu": 1.0, "neg": 1.3},  # crises often matter more
        "verified_bonus": 1.4,
        "platform_priority": {"news": 1.5},                  # platform -> multiplier
        "keyword_terms": [],                                 # spokesperson / priority terms
        "keyword_factor": 2.0,
    },
}


def get_setting(db: Session, key: str) -> dict:
    row = db.get(AppSetting, key)
    if row is not None and row.value:
        # shallow-merge over defaults so new default keys appear for old rows
        base = dict(DEFAULTS.get(key, {}))
        base.update(row.value)
        return base
    return dict(DEFAULTS.get(key, {}))


def _prepare_notifiers(db: Session, value: dict) -> dict:
    """Encrypt notifier secrets before storage. The API echoes back the mask sentinel
    for an unchanged secret (-> keep the stored one), "" to clear, or a new value."""
    stored = get_setting(db, "notifiers")
    for f in _NOTIFIER_SECRETS:
        incoming = value.get(f, "")
        if incoming == _MASK:
            s = stored.get(f, "")
            # keep stored, migrating any legacy plaintext to ciphertext on the way through
            value[f] = s if (s and decrypt(s)) else (encrypt(s) if s else "")
        elif incoming == "":
            value[f] = ""
        else:
            value[f] = encrypt(incoming)
    return value


def set_setting(db: Session, key: str, value: dict) -> dict:
    if key == "notifiers":
        value = _prepare_notifiers(db, dict(value))
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()
    return masked_notifiers(db) if key == "notifiers" else get_setting(db, key)


def notifier_config(db: Session) -> dict:
    """Notifiers with secrets DECRYPTED — for the sender only, never returned to a client.
    Falls back to treating a non-decryptable value as legacy plaintext."""
    n = dict(get_setting(db, "notifiers"))
    for f in _NOTIFIER_SECRETS:
        v = n.get(f, "")
        n[f] = (decrypt(v) or v) if v else ""
    return n


def masked_notifiers(db: Session) -> dict:
    """Notifiers for the API: each secret replaced with a mask sentinel (or "" if unset)."""
    n = dict(get_setting(db, "notifiers"))
    for f in _NOTIFIER_SECRETS:
        n[f] = _MASK if n.get(f) else ""
    return n


def all_settings(db: Session) -> dict:
    data = {k: get_setting(db, k) for k in DEFAULTS}
    data["notifiers"] = masked_notifiers(db)   # never expose notifier secrets
    return data
