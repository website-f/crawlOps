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


def _kw_filter(keywords: list[str]):
    """Radar kwFilter: OR of ILIKE over title+text. Empty = whole theme (no filter)."""
    from sqlalchemy import or_
    if not keywords:
        return None
    clauses = []
    for k in keywords:
        clauses.append(Post.text.ilike(f"%{k}%"))
        clauses.append(Post.title.ilike(f"%{k}%"))
    return or_(*clauses)


def grade(score: float) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 65:
        return "Good"
    if score >= 50:
        return "Fair"
    return "At risk"


def brand_health(db: Session, topic_id: int | None, days: int = 14,
                 keywords: list[str] | None = None) -> dict:
    """Composite 0-100 = 0.35 sentiment + 0.25 positivity + 0.20 momentum + 0.20 reach.
    Faithful port of Radar healthFor(). keywords scopes it to a brand (else whole theme)."""
    f = _scope(topic_id, days)
    kw = _kw_filter(keywords or [])
    if kw is not None:
        f.append(kw)
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


def share_of_voice(db: Session, topic_id: int | None, entities: list, days: int = 30) -> dict:
    """Volume per benchmark entity over a continuous day grid (streamgraph)."""
    from datetime import date
    start = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    grid = [(start + timedelta(days=i)).isoformat() for i in range(days + 1)]
    rows_by_day = {d: {"day": d} for d in grid}
    names = []
    for ent in entities:
        names.append(ent.name)
        kws = ent.keywords or [ent.name]
        f = _scope(topic_id, days)
        kw = _kw_filter(kws)
        if kw is not None:
            f.append(kw)
        daily = (db.query(func.date_trunc("day", Post.posted_at).label("d"), func.count())
                 .filter(and_(*f)).group_by("d").all())
        counts = {d.date().isoformat(): c for d, c in daily}
        for d in grid:
            rows_by_day[d][ent.name] = counts.get(d, 0)
    return {"entities": names, "days": list(rows_by_day.values())}


def benchmark_compare(db: Session, topic_id: int | None, entities: list, days: int = 14) -> list[dict]:
    """Brand-vs-competitor-vs-market health comparison (Radar brandHealthReport)."""
    out = [{"name": "Market (all)", "is_brand": False,
            **brand_health(db, topic_id, days)}]
    for ent in entities:
        h = brand_health(db, topic_id, days, keywords=ent.keywords or [ent.name])
        out.append({"name": ent.name, "is_brand": ent.is_own_brand,
                    "score": h["score"], "grade": h["grade"], "total": h["total"]})
    return sorted(out, key=lambda x: -x["score"])


def heatmap(db: Session, topic_id: int | None, days: int = 30) -> list[list[int]]:
    """day-of-week (Mon..Sun) x hour-of-day counts."""
    f = _scope(topic_id, days)
    rows = (db.query(func.extract("dow", Post.posted_at).label("dow"),
                     func.extract("hour", Post.posted_at).label("hr"), func.count())
            .filter(and_(*f)).group_by("dow", "hr").all())
    grid = [[0] * 24 for _ in range(7)]  # rows Mon..Sun
    for dow, hr, c in rows:
        # postgres dow: 0=Sun..6=Sat -> reindex to 0=Mon..6=Sun
        mon_idx = (int(dow) + 6) % 7
        grid[mon_idx][int(hr)] = c
    return grid


def constellation(db: Session, topic_id: int | None, days: int = 30) -> dict:
    """Topic co-occurrence graph: nodes=topics (freq+sentiment), edges=co-mention."""
    f = _scope(topic_id, days)
    freq = (db.query(func.jsonb_array_elements_text(Post.topics).label("t"),
                     func.count(), func.coalesce(func.avg(Post.sentiment_score), 0))
            .filter(and_(*f)).group_by("t")
            .having(func.count() >= 3).order_by(func.count().desc()).limit(26).all())
    keep = {t for t, _, _ in freq}
    nodes = [{"topic": t, "freq": c, "sentiment": round(float(s), 2)} for t, c, s in freq]

    # co-occurrence: pull topics arrays, count unordered pairs within kept set
    rows = (db.query(Post.topics).filter(and_(*f))
            .filter(func.jsonb_array_length(Post.topics) >= 2).limit(4000).all())
    pair: dict = {}
    for (topics,) in rows:
        ts = sorted({t for t in (topics or []) if t in keep})
        for i in range(len(ts)):
            for j in range(i + 1, len(ts)):
                pair[(ts[i], ts[j])] = pair.get((ts[i], ts[j]), 0) + 1
    edges = [{"a": a, "b": b, "weight": w} for (a, b), w in pair.items() if w >= 2]
    edges.sort(key=lambda e: -e["weight"])
    return {"nodes": nodes, "edges": edges[:60]}


def influencer_network(db: Session, topic_id: int | None, days: int = 30) -> dict:
    """Top authors clustered by their dominant topic (co-topic tribes)."""
    f = _scope(topic_id, days, [Post.author_key != ""])
    rows = (db.query(Post.author_key, Post.author_name,
                     func.count().label("posts"),
                     func.coalesce(func.sum(func.coalesce(
                         Post.engagement["likes"].as_float(), 0)), 0).label("eng"),
                     func.coalesce(func.avg(Post.sentiment_score), 0).label("sent"),
                     func.max(Post.platform).label("platform"))
            .filter(and_(*f)).group_by(Post.author_key, Post.author_name)
            .order_by(func.sum(func.coalesce(Post.engagement["likes"].as_float(), 0)).desc())
            .limit(40).all())
    if not rows:
        return {"nodes": [], "edges": []}
    max_eng = max(float(r.eng) for r in rows) or 1
    nodes = []
    for r in rows:
        eng = float(r.eng)
        tier = "mega" if eng >= max_eng * 0.5 else "macro" if eng >= max_eng * 0.15 else "micro"
        nodes.append({"id": r.author_name or r.author_key, "platform": r.platform,
                      "posts": r.posts, "engagement": round(eng),
                      "sentiment": round(float(r.sent), 2), "tier": tier})
    return {"nodes": nodes}


def sentiment_waterfall(db: Session, topic_id: int | None, days: int = 30) -> list[dict]:
    """Daily net sentiment (pos - neg) with running cumulative."""
    f = _scope(topic_id, days)
    rows = (db.query(func.date_trunc("day", Post.posted_at).label("d"),
                     func.count().filter(Post.sentiment == "pos"),
                     func.count().filter(Post.sentiment == "neg"))
            .filter(and_(*f)).group_by("d").order_by("d").all())
    out, cum = [], 0
    for d, pos, neg in rows:
        delta = (pos or 0) - (neg or 0)
        prev = cum
        cum += delta
        out.append({"day": d.date().isoformat(), "delta": delta, "cumulative": cum,
                    "base": min(prev, cum), "up": delta >= 0})
    return out


def forecast(db: Session, topic_id: int | None, days: int = 30, horizon: int = 7) -> dict:
    """Least-squares projection of daily volume + negative-share early warning."""
    f = _scope(topic_id, days)
    rows = (db.query(func.date_trunc("day", Post.posted_at).label("d"), func.count(),
                     func.count().filter(Post.sentiment == "neg"))
            .filter(and_(*f)).group_by("d").order_by("d").all())
    if len(rows) < 4:
        return {"history": [], "projection": [], "trend": "flat", "confidence": "low"}
    vols = [c for _, c, _ in rows]
    n = len(vols)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(vols) / n
    denom = sum((x - mean_x) ** 2 for x in xs) or 1
    slope = sum((xs[i] - mean_x) * (vols[i] - mean_y) for i in range(n)) / denom
    intercept = mean_y - slope * mean_x
    resid = [vols[i] - (intercept + slope * xs[i]) for i in range(n)]
    rmse = (sum(r * r for r in resid) / n) ** 0.5
    h = min(horizon, max(3, days // 2))
    proj = []
    for i in range(1, h + 1):
        x = n - 1 + i
        val = max(0, intercept + slope * x)
        band = rmse * 1.28 * (1 + i * 0.06)
        proj.append({"step": i, "value": round(val, 1),
                     "low": round(max(0, val - band), 1), "high": round(val + band, 1)})
    pct_per_week = (slope * 7 / mean_y * 100) if mean_y else 0
    trend = "rising" if pct_per_week > 15 else "falling" if pct_per_week < -15 else "flat"
    conf = "high" if abs(pct_per_week) < 5 or rmse < mean_y * 0.4 else "medium" if n >= 10 else "low"
    return {"history": [{"day": d.date().isoformat(), "value": c} for d, c, _ in rows],
            "projection": proj, "trend": trend, "pct_per_week": round(pct_per_week, 1),
            "confidence": conf}


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
