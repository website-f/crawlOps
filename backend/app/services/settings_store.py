"""Runtime config in the app_settings KV table, with sane defaults.

Anything editable in the Settings UI lives here (not in .env), so a change takes
effect without a redeploy.
"""
from sqlalchemy.orm import Session

from ..models import AppSetting
from .scoring import CPM as DEFAULT_CPM

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


def set_setting(db: Session, key: str, value: dict) -> dict:
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()
    return get_setting(db, key)


def all_settings(db: Session) -> dict:
    return {k: get_setting(db, k) for k in DEFAULTS}
