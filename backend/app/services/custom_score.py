"""Custom "impact" scoring — a team-defined value per mention (Meltwater beyond-AVE).

Score = base(relevance, reach, engagement) x multipliers(platform, sentiment, verified,
priority keywords). All inputs are already stored on the post, so scoring — and
re-scoring after a weight change — is pure arithmetic (no AI, no re-crawl).
"""
import math
import time

from sqlalchemy.orm import Session

from .settings_store import get_setting

_cache: dict = {"at": 0.0, "cfg": None}


def current_config(db: Session) -> dict:
    """Scoring config, cached ~60s so per-post scoring doesn't hit the DB each time."""
    now = time.monotonic()
    if _cache["cfg"] is None or now - _cache["at"] > 60:
        _cache["cfg"] = get_setting(db, "scoring")
        _cache["at"] = now
    return _cache["cfg"]


def invalidate() -> None:
    _cache["cfg"] = None


def _norm(v, scale: float) -> float:
    return math.log10(max(0.0, float(v or 0)) + 1) / scale   # clamp (reddit scores go negative)


def compute(cfg: dict, *, platform: str, reach, engagement_total, relevance,
            sentiment, verified: bool, text: str) -> float:
    """Bounded, tunable impact score (~0-400 typical). 0 when scoring is disabled."""
    if not cfg or not cfg.get("enabled", True):
        return 0.0
    base = (float(cfg.get("w_relevance", 1.0)) * ((relevance or 0) / 100.0)
            + float(cfg.get("w_reach", 1.0)) * _norm(reach, 7.0)
            + float(cfg.get("w_engagement", 1.0)) * _norm(engagement_total, 6.0))
    mult = float((cfg.get("platform_priority") or {}).get(platform, 1.0))
    mult *= float((cfg.get("sentiment") or {}).get(sentiment or "neu", 1.0))
    if verified:
        mult *= float(cfg.get("verified_bonus", 1.0))
    terms = [t.lower() for t in (cfg.get("keyword_terms") or []) if t and t.strip()]
    if terms and text and any(t in text.lower() for t in terms):
        mult *= float(cfg.get("keyword_factor", 1.0))
    return round(base * mult * 100, 1)
