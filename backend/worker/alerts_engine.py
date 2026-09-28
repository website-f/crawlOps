"""Evaluate alert rules after a topic run, fire events, deliver notifications.

Dedup: won't re-fire the same rule within its cooldown window (default 6h) —
mirrors Radar's "no same alert type twice in 24h" but per-rule configurable.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AlertEvent, AlertRule, Post
from app.services.notifier import notify
from app.services.spikes import detect_spike, hourly_counts, volume_alert

log = logging.getLogger("alerts")

DEFAULT_COOLDOWN_H = 6


def _recently_fired(db: Session, rule: AlertRule, cooldown_h: int) -> bool:
    since = datetime.now(timezone.utc) - timedelta(hours=cooldown_h)
    return db.query(AlertEvent.id).filter(
        AlertEvent.rule_id == rule.id, AlertEvent.fired_at >= since).first() is not None


def evaluate_topic_alerts(db: Session, topic_id: int) -> int:
    rules = (db.query(AlertRule)
             .filter(AlertRule.topic_id == topic_id, AlertRule.active.is_(True)).all())
    fired = 0
    for rule in rules:
        cooldown = int(rule.config.get("cooldown_hours", DEFAULT_COOLDOWN_H))
        if _recently_fired(db, rule, cooldown):
            continue
        event = _check(db, rule)
        if event is None:
            continue
        db.add(AlertEvent(rule_id=rule.id, payload=event))
        db.commit()
        notify(db, event["title"], event["body"], event, channels=rule.notify)
        fired += 1
        log.info("alert fired: rule=%s %s", rule.id, event["title"])
    return fired


def _check(db: Session, rule: AlertRule) -> dict | None:
    from app.models import Topic
    topic = db.get(Topic, rule.topic_id)
    tname = topic.name if topic else f"topic {rule.topic_id}"

    if rule.kind == "spike":
        counts = hourly_counts(db, rule.topic_id)
        spike = detect_spike(counts)
        if spike:
            recent = spike["recent"][-1]
            return {"kind": "spike", "topic_id": rule.topic_id, "topic": tname,
                    "title": f"Volume spike: {tname}",
                    "body": (f"{recent} posts in the last hour vs a baseline of "
                             f"{spike['baseline']}/h. Threshold {spike['threshold']}."),
                    **spike}
        vol = volume_alert(db, rule.topic_id)
        if vol:
            return {"kind": "spike", "topic_id": rule.topic_id, "topic": tname,
                    "title": f"Volume spike: {tname}",
                    "body": (f"{vol['last24']} posts in 24h vs a daily average of "
                             f"{vol['avg_daily']}. Severity {vol['severity']}."),
                    **vol}
        return None

    if rule.kind == "neg_sentiment":
        # negative-sentiment share over the last N hours crosses a threshold
        hours = int(rule.config.get("window_hours", 24))
        min_volume = int(rule.config.get("min_volume", 10))
        pct_threshold = float(rule.config.get("neg_pct", 40))
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        base = db.query(Post).filter(Post.topic_id == rule.topic_id,
                                     Post.is_hidden.is_(False), Post.posted_at >= since,
                                     Post.sentiment.isnot(None))
        total = base.count()
        neg = base.filter(Post.sentiment == "neg").count()
        if total >= min_volume:
            pct = round(neg / total * 100, 1)
            if pct >= pct_threshold:
                return {"kind": "neg_sentiment", "topic_id": rule.topic_id, "topic": tname,
                        "title": f"Negative sentiment surge: {tname}",
                        "body": (f"{pct}% of {total} posts in the last {hours}h are negative "
                                 f"(threshold {pct_threshold}%)."),
                        "neg_pct": pct, "total": total, "window_hours": hours}
        return None

    return None
