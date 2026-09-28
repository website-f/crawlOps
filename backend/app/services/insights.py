"""Radar-faithful analytics: brand health, momentum quadrant, crisis, sentiment
flow (Sankey), waterfall, author pyramid. Formulas ported from radar-intelligence
lib/insights.ts (see docs/ALGORITHMS.md and the research notes).

Postgres-only aggregation over the posts table; AI never touches these numbers.
"""
import statistics
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from ..models import Post


def _clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


def _scope(topic_id: int | None, days: int, extra: list | None = None):
    f = [Post.is_hidden.is_(False),
         Post.posted_at >= datetime.now(timezone.utc) - timedelta(days=days)]
    if topic_id:
        f.append(Post.topic_id == topic_id)
    if extra:
        f.extend(extra)
    return f


def grade(score: float) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 65:
        return "Good"
    if score >= 50:
        return "Fair"
    return "At risk"


def brand_health(db: Session, topic_id: int | None, days: int = 14) -> dict:
    """Composite 0-100 = 0.35 sentiment + 0.25 positivity + 0.20 momentum + 0.20 reach.
    Faithful port of Radar healthFor()."""
    f = _scope(topic_id, days)
    now = datetime.now(timezone.utc)
    mid = now - timedelta(days=days / 2)

    row = db.query(
        func.count().label("total"),
        func.coalesce(func.avg(Post.sentiment_score), 0).label("avg_sent"),
        func.count().filter(Post.sentiment == "pos").label("pos"),
        func.count().filter(Post.sentiment.in_(("pos", "neg"))).label("classified"),
        func.count().filter(func.coalesce(Post.reach, 0) > 0).label("resonant"),
        func.count().filter(Post.posted_at >= mid).label("recent"),
        func.count().filter(Post.posted_at < mid).label("older"),
    ).filter(and_(*f)).one()

    total = row.total or 0
    if total == 0:
        return {"score": 0, "grade": "At risk", "total": 0,
                "components": {"sentiment": 0, "positivity": 0, "momentum": 50, "reach": 0},
                "spark": []}

    sentiment = round((float(row.avg_sent) + 1) / 2 * 100)
    positivity = round((row.pos / row.classified * 100) if row.classified else 0)
    change_pct = ((row.recent - row.older) / row.older * 100) if row.older else (100 if row.recent else 0)
    momentum = round(_clamp(50 + change_pct / 2))
    reach = round(row.resonant / total * 100)

    score = round(sentiment * 0.35 + positivity * 0.25 + momentum * 0.20 + reach * 0.20)

    # sparkline: per-day rescaled sentiment
    spark_rows = (db.query(func.date_trunc("day", Post.posted_at).label("d"),
                           func.avg(Post.sentiment_score))
                  .filter(and_(*f)).group_by("d").order_by("d").all())
    spark = [round((float(s or 0) + 1) / 2 * 100) for _, s in spark_rows]

    return {"score": score, "grade": grade(score), "total": total,
            "components": {"sentiment": sentiment, "positivity": positivity,
                           "momentum": momentum, "reach": reach},
            "spark": spark}


def momentum_quadrant(db: Session, topic_id: int | None, days: int = 14) -> list[dict]:
    """Per-topic acceleration vs volume 2x2 (Rising stars / Emerging / Steady / Declining)."""
    f = _scope(topic_id, days)
    mid = datetime.now(timezone.utc) - timedelta(days=days / 2)
    rows = (db.query(
                func.jsonb_array_elements_text(Post.topics).label("t"),
                func.count().label("vol"),
                func.count().filter(Post.posted_at >= mid).label("recent"),
                func.count().filter(Post.posted_at < mid).label("older"),
                func.coalesce(func.avg(Post.sentiment_score), 0).label("sent"))
            .filter(and_(*f)).group_by("t")
            .having(func.count() >= 4).order_by(func.count().desc()).limit(30).all())
    if not rows:
        return []
    vols = sorted(r.vol for r in rows)
    median_vol = statistics.median(vols)
    out = []
    for r in rows:
        if r.older == 0:
            accel = 100 if r.recent > 0 else 0
        else:
            accel = (r.recent - r.older) / r.older * 100
        accel = round(max(-100, min(200, accel)))
        vol_high = r.vol >= median_vol
        if accel >= 0:
            quad = "Rising stars" if vol_high else "Emerging"
        else:
            quad = "Steady" if vol_high else "Declining"
        out.append({"topic": r.t, "volume": r.vol, "acceleration": accel,
                    "sentiment": round(float(r.sent) * 100) / 100, "quadrant": quad})
    return out


def crisis(db: Session, topic_id: int | None, days: int = 14) -> dict:
    """Risk 0-100 = capped(neg-share 50) + capped(spike 30) + capped(high-alerts 20)."""
    from ..models import AlertEvent, AlertRule
    now = datetime.now(timezone.utc)
    f = _scope(topic_id, days)
    recent_cut = now - timedelta(days=2)

    daily = (db.query(func.date_trunc("day", Post.posted_at).label("d"), func.count())
             .filter(and_(*f)).group_by("d").order_by("d").all())
    recent_vol = db.query(func.count()).filter(and_(*f, Post.posted_at >= recent_cut)).scalar() or 0
    recent_neg = db.query(func.count()).filter(
        and_(*f, Post.posted_at >= recent_cut, Post.sentiment == "neg")).scalar() or 0
    prior_days = [c for d, c in daily if d < recent_cut]
    recent_daily_avg = recent_vol / 2
    prior_daily_avg = (sum(prior_days) / len(prior_days)) if prior_days else 0

    neg_share48 = (recent_neg / recent_vol) if recent_vol else 0
    spike = (recent_daily_avg / prior_daily_avg) if prior_daily_avg else 1
    high_alerts = 0
    if topic_id:
        high_alerts = (db.query(func.count()).select_from(AlertEvent)
                       .join(AlertRule, AlertRule.id == AlertEvent.rule_id)
                       .filter(AlertRule.topic_id == topic_id,
                               AlertEvent.fired_at >= now - timedelta(days=7)).scalar() or 0)

    c_neg = round(min(50, neg_share48 * 100 * 0.9))
    c_spike = round(max(0, min(30, (spike - 1) * 40)))
    c_alert = min(20, high_alerts * 10)
    risk = round(_clamp(c_neg + c_spike + c_alert))
    level = ("Critical" if risk >= 75 else "Elevated" if risk >= 50
             else "Watch" if risk >= 25 else "Calm")
    return {"risk": risk, "level": level,
            "drivers": {"negative": c_neg, "spike": c_spike, "alerts": c_alert},
            "neg_share_48h": round(neg_share48 * 100, 1),
            "spike_ratio": round(spike, 2)}


def sentiment_flow(db: Session, topic_id: int | None, days: int = 30) -> dict:
    """3-layer Sankey Source -> Topic -> Sentiment (top 6 sources, top 8 topics)."""
    f = _scope(topic_id, days)
    src_top = [r[0] for r in
               (db.query(Post.platform, func.count()).filter(and_(*f))
                .group_by(Post.platform).order_by(func.count().desc()).limit(6).all())]
    topic_top = [r[0] for r in
                 (db.query(func.jsonb_array_elements_text(Post.topics).label("t"), func.count())
                  .filter(and_(*f)).group_by("t").order_by(func.count().desc()).limit(8).all())]
    if not src_top or not topic_top:
        return {"nodes": [], "links": []}

    st = (db.query(Post.platform, func.jsonb_array_elements_text(Post.topics).label("t"), func.count())
          .filter(and_(*f, Post.platform.in_(src_top)))
          .group_by(Post.platform, "t").all())
    ts = (db.query(func.jsonb_array_elements_text(Post.topics).label("t"), Post.sentiment, func.count())
          .filter(and_(*f)).group_by("t", Post.sentiment).all())

    nodes, node_idx = [], {}

    def node(key, label, layer):
        if key not in node_idx:
            node_idx[key] = len(nodes)
            nodes.append({"key": key, "label": label, "layer": layer})
        return node_idx[key]

    for s in src_top:
        node(f"s:{s}", s, 0)
    for t in topic_top:
        node(f"t:{t}", t, 1)
    for x in ("pos", "neu", "neg"):
        node(f"x:{x}", x, 2)

    links = []
    for platform, t, n in st:
        if t in topic_top:
            links.append({"source": node_idx[f"s:{platform}"], "target": node_idx[f"t:{t}"], "value": n})
    for t, sent, n in ts:
        if t in topic_top and sent in ("pos", "neu", "neg"):
            links.append({"source": node_idx[f"t:{t}"], "target": node_idx[f"x:{sent}"], "value": n})
    return {"nodes": nodes, "links": links}


def author_pyramid(db: Session, topic_id: int | None, days: int = 30) -> dict:
    """Author tiers by engagement percentile (top 5% / 20% / 50% / rest)."""
    f = _scope(topic_id, days, [Post.author_key != ""])
    rows = (db.query(Post.author_key, Post.author_name,
                     func.count().label("posts"),
                     func.coalesce(func.sum(
                         func.coalesce(Post.engagement["likes"].as_float(), 0)), 0).label("reach"))
            .filter(and_(*f)).group_by(Post.author_key, Post.author_name)
            .order_by(func.sum(func.coalesce(Post.engagement["likes"].as_float(), 0)).desc())
            .limit(500).all())
    if not rows:
        return {"tiers": [], "top_authors": []}
    n = len(rows)
    total_reach = sum(float(r.reach) for r in rows) or 1
    b1 = max(1, round(n * 0.05))
    b2 = max(b1 + 1, round(n * 0.20))
    b3 = max(b2 + 1, round(n * 0.50))
    bands = [("Mega voices", 0, b1), ("Macro", b1, b2), ("Micro", b2, b3), ("Long tail", b3, n)]
    tiers = []
    for label, lo, hi in bands:
        chunk = rows[lo:hi]
        reach = sum(float(r.reach) for r in chunk)
        tiers.append({"tier": label, "authors": len(chunk),
                      "reach": round(reach),
                      "share": round(reach / total_reach * 1000) / 10,
                      "examples": [r.author_name or r.author_key for r in chunk[:3]]})

    def tier_of(i):
        return ("mega" if i < b1 else "macro" if i < b2 else "micro" if i < b3 else "longtail")
    top = [{"author": r.author_name or r.author_key, "tier": tier_of(i),
            "posts": r.posts, "reach": round(float(r.reach))} for i, r in enumerate(rows[:24])]
    return {"tiers": tiers, "top_authors": top,
            "top_concentration": tiers[0]["share"] if tiers else 0}
