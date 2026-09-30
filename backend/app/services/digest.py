"""Scheduled digest — a periodic summary of what the crawler found, delivered to the
same channels as alerts (webhook + Telegram). Config lives in Settings ('digest')."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from ..models import Post, Topic
from .notifier import notify
from .settings_store import get_setting

log = logging.getLogger("digest")


def _trending(db: Session, topic_id, hours: int = 24) -> list[str]:
    now = datetime.now(timezone.utc)
    recent_start = now - timedelta(hours=hours)
    prior_start = recent_start - timedelta(hours=hours)
    tfilter = "AND topic_id = :tid" if topic_id else ""
    params = {"recent_start": recent_start, "prior_start": prior_start}
    if topic_id:
        params["tid"] = topic_id
    sql = text(f"""
        WITH terms AS (
          SELECT lower(t) term, fetched_at FROM posts, LATERAL jsonb_array_elements_text(topics) t
          WHERE is_hidden=false AND fetched_at >= :prior_start {tfilter}
          UNION ALL
          SELECT lower(e), fetched_at FROM posts, LATERAL jsonb_array_elements_text(entities) e
          WHERE is_hidden=false AND fetched_at >= :prior_start {tfilter}),
        recent AS (SELECT term, count(*) c FROM terms WHERE fetched_at >= :recent_start GROUP BY term),
        prior AS (SELECT term, count(*) c FROM terms WHERE fetched_at < :recent_start GROUP BY term)
        SELECT r.term FROM recent r LEFT JOIN prior p USING(term)
        WHERE r.c >= 3 AND length(r.term) >= 2
        ORDER BY (r.c::numeric+1)/(COALESCE(p.c,0)+1) DESC, r.c DESC LIMIT 8""")
    try:
        return [row.term for row in db.execute(sql, params).all()]
    except Exception:  # noqa: BLE001
        db.rollback()
        return []


async def build_digest(db: Session, topic_id=None, include_brief: bool = True) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)
    q = db.query(Post).filter(Post.is_hidden.is_(False), Post.posted_at >= since)
    if topic_id:
        q = q.filter(Post.topic_id == topic_id)
    total = q.count()
    sent = dict(q.with_entities(Post.sentiment, func.count()).group_by(Post.sentiment).all())
    platforms = (q.with_entities(Post.platform, func.count()).group_by(Post.platform)
                 .order_by(func.count().desc()).limit(5).all())
    authors = (q.with_entities(Post.author_name, func.count())
               .filter(Post.author_key != "").group_by(Post.author_name)
               .order_by(func.count().desc()).limit(5).all())
    top_impact = (q.with_entities(Post.title, Post.platform, Post.custom_score)
                  .filter(Post.custom_score.isnot(None))
                  .order_by(Post.custom_score.desc()).limit(3).all())
    trends = _trending(db, topic_id)

    topic = db.get(Topic, topic_id) if topic_id else None
    scope = topic.name if topic else "all topics"
    lines = [f"📊 Last 24h · {scope}", f"{total} mentions "
             f"(👍 {sent.get('pos', 0)} · 😐 {sent.get('neu', 0)} · 👎 {sent.get('neg', 0)})"]
    if platforms:
        lines.append("Sources: " + ", ".join(f"{p} {n}" for p, n in platforms))
    if trends:
        lines.append("🔥 Trending: " + ", ".join(trends))
    if authors:
        lines.append("Top voices: " + ", ".join(f"{a}" for a, _ in authors[:5]))
    if top_impact:
        lines.append("Highest impact:")
        lines += [f"  • {(t or '')[:80]} ({pl}, {int(sc)})" for t, pl, sc in top_impact]

    if include_brief:
        try:
            from .ai_insights import daily_brief
            from .gateway import gateway
            if gateway.available("judge"):
                b = await daily_brief(db, topic_id, days=1)
                summary = b.get("summary") or b.get("brief") or b.get("headline") or ""
                if summary:
                    lines.append("\n🧠 " + str(summary)[:600])
        except Exception:  # noqa: BLE001
            pass

    return f"CrawlOps digest — {scope}", "\n".join(lines)


async def send_digest(db: Session) -> dict:
    cfg = get_setting(db, "digest")
    title, body = await build_digest(db, cfg.get("topic_id") or None,
                                     include_brief=cfg.get("include_brief", True))
    return notify(db, title, body, {"kind": "digest"})


def is_due(db: Session, now: datetime) -> bool:
    cfg = get_setting(db, "digest")
    if not cfg.get("enabled"):
        return False
    if now.hour != int(cfg.get("hour", 8)):
        return False
    freq = cfg.get("frequency", "daily")
    if freq == "weekly" and now.weekday() != 0:       # Monday
        return False
    return True
