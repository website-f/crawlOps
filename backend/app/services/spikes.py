"""Spike detection — EWMA baseline + MAD residuals over hourly buckets (§7),
plus Radar-style 24h volume-vs-week alerts as a second, simpler signal."""
import statistics
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Post

EWMA_ALPHA = 0.3


def hourly_counts(db: Session, topic_id: int, hours: int = 96) -> list[int]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (db.query(func.date_trunc("hour", Post.posted_at).label("h"), func.count())
            .filter(Post.topic_id == topic_id, Post.posted_at >= since,
                    Post.is_hidden.is_(False))
            .group_by("h").order_by("h").all())
    by_hour = {r[0].replace(tzinfo=timezone.utc) if r[0].tzinfo is None else r[0]: r[1] for r in rows}
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return [by_hour.get(now - timedelta(hours=i), 0) for i in range(hours - 1, -1, -1)]


def detect_spike(counts: list[int]) -> dict | None:
    """counts = oldest..newest hourly buckets. Spike when the last 2 buckets both
    exceed baseline + max(4*MAD, 5)."""
    if len(counts) < 26:
        return None
    history, recent = counts[:-2], counts[-2:]
    ewma = history[0]
    residuals = []
    for c in history[1:]:
        residuals.append(abs(c - ewma))
        ewma = EWMA_ALPHA * c + (1 - EWMA_ALPHA) * ewma
    mad = statistics.median(residuals) if residuals else 0.0
    threshold = ewma + max(4 * mad, 5)
    if all(c > threshold for c in recent):
        return {"baseline": round(ewma, 2), "mad": round(mad, 2),
                "threshold": round(threshold, 2), "recent": recent}
    return None


def volume_alert(db: Session, topic_id: int) -> dict | None:
    """Radar heuristic: last24 > max(10, 2.5 x daily average of the prior week)."""
    now = datetime.now(timezone.utc)
    base = db.query(func.count()).filter(Post.topic_id == topic_id, Post.is_hidden.is_(False))
    last24 = base.filter(Post.posted_at >= now - timedelta(hours=24)).scalar() or 0
    prev7 = base.filter(Post.posted_at >= now - timedelta(days=8),
                        Post.posted_at < now - timedelta(hours=24)).scalar() or 0
    avg_daily = prev7 / 7
    if avg_daily >= 3 and last24 > max(10, 2.5 * avg_daily):
        return {"last24": last24, "avg_daily": round(avg_daily, 1),
                "severity": "high" if last24 > 5 * avg_daily else "medium"}
    return None
