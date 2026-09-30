from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Text, and_, func, text
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Cluster, Post
from ..services import ai_insights, insights
from ..services.spikes import detect_spike, hourly_counts, volume_alert

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _visible(db: Session):
    return db.query(Post).filter(Post.is_hidden.is_(False))


@router.get("/trending")
def trending(topic_id: int | None = None, hours: int = 24, min_count: int = 3,
             db: Session = Depends(get_db)):
    """What's surging right now: terms/entities appearing far more in the last `hours`
    than in the prior equal window (velocity), Meltwater-style. Uses the judge's
    already-extracted topics + entities, so it's cheap and precise."""
    now = datetime.now(timezone.utc)
    recent_start = now - timedelta(hours=max(1, min(hours, 168)))
    prior_start = recent_start - (now - recent_start)
    tfilter = "AND topic_id = :tid" if topic_id else ""
    params = {"recent_start": recent_start, "prior_start": prior_start,
              "min_count": max(1, min_count), "k": 30}
    if topic_id:
        params["tid"] = topic_id
    sql = text(f"""
        WITH terms AS (
          SELECT lower(t) AS term, fetched_at FROM posts,
                 LATERAL jsonb_array_elements_text(topics) AS t
          WHERE is_hidden = false AND fetched_at >= :prior_start {tfilter}
          UNION ALL
          SELECT lower(e) AS term, fetched_at FROM posts,
                 LATERAL jsonb_array_elements_text(entities) AS e
          WHERE is_hidden = false AND fetched_at >= :prior_start {tfilter}
        ),
        recent AS (SELECT term, count(*) c FROM terms WHERE fetched_at >= :recent_start GROUP BY term),
        prior  AS (SELECT term, count(*) c FROM terms WHERE fetched_at <  :recent_start GROUP BY term)
        SELECT r.term, r.c AS recent, COALESCE(p.c, 0) AS prior,
               round(((r.c::numeric + 1) / (COALESCE(p.c, 0) + 1)), 2) AS velocity
        FROM recent r LEFT JOIN prior p USING (term)
        WHERE r.c >= :min_count AND length(r.term) >= 2
        ORDER BY velocity DESC, recent DESC
        LIMIT :k
    """)
    try:
        rows = db.execute(sql, params).all()
    except Exception:  # noqa: BLE001 — e.g. topics/entities still json on a fresh DB
        db.rollback()
        return {"window_hours": hours, "trending": []}
    return {"window_hours": hours,
            "trending": [{"term": r.term, "recent": r.recent, "prior": r.prior,
                          "velocity": float(r.velocity),
                          "new": r.prior == 0} for r in rows]}


@router.get("/overview")
def overview(topic_id: int | None = None, days: int = 7, db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = _visible(db).filter(Post.posted_at >= since)
    if topic_id:
        q = q.filter(Post.topic_id == topic_id)

    total = q.count()
    by_sent = dict(q.with_entities(Post.sentiment, func.count()).group_by(Post.sentiment).all())
    by_platform = q.with_entities(Post.platform, func.count()).group_by(Post.platform) \
        .order_by(func.count().desc()).all()
    daily = (q.with_entities(func.date_trunc("day", Post.posted_at).label("d"),
                             Post.platform, func.count())
             .group_by("d", Post.platform).order_by("d").all())
    top_authors = (q.with_entities(Post.platform, Post.author_name, Post.author_key, func.count())
                   .filter(Post.author_key != "").group_by(Post.platform, Post.author_name, Post.author_key)
                   .order_by(func.count().desc()).limit(10).all())
    top_domains = (q.with_entities(Post.domain, func.count()).filter(Post.domain != "")
                   .group_by(Post.domain).order_by(func.count().desc()).limit(10).all())
    emv_total = q.with_entities(func.coalesce(func.sum(Post.emv), 0)).scalar()
    reach_total = q.with_entities(func.coalesce(func.sum(Post.reach), 0)).scalar()

    return {
        "total": total,
        "sentiment": {"pos": by_sent.get("pos", 0), "neu": by_sent.get("neu", 0),
                      "neg": by_sent.get("neg", 0), "pending": by_sent.get(None, 0)},
        "by_platform": [{"platform": p, "count": c} for p, c in by_platform],
        "daily": [{"day": d.date().isoformat(), "platform": p, "count": c} for d, p, c in daily],
        "top_authors": [{"platform": p, "name": n or k, "author_key": k, "count": c}
                        for p, n, k, c in top_authors],
        "top_domains": [{"domain": d, "count": c} for d, c in top_domains],
        "emv_total": round(float(emv_total or 0), 2),
        "reach_total": int(reach_total or 0),
    }


@router.get("/clusters")
def clusters(topic_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Cluster)
    if topic_id:
        q = q.filter(Cluster.topic_id == topic_id)
    return [{"id": c.id, "topic_id": c.topic_id, "label": c.label, "post_count": c.post_count}
            for c in q.order_by(Cluster.post_count.desc()).limit(30).all()]


@router.get("/spikes/{topic_id}")
def spikes(topic_id: int, db: Session = Depends(get_db)):
    counts = hourly_counts(db, topic_id)
    return {"hourly": counts, "spike": detect_spike(counts), "volume_alert": volume_alert(db, topic_id)}


def _scope(db: Session, topic_id: int | None, days: int):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = _visible(db).filter(Post.posted_at >= since)
    if topic_id:
        q = q.filter(Post.topic_id == topic_id)
    return q, since


@router.get("/geo")
def geo(topic_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    """Aggregate geolocated posts by country and by region (state) with sentiment split."""
    q, _ = _scope(db, topic_id, days)
    q = q.filter(Post.country.isnot(None))

    def split(group_cols):
        rows = (q.with_entities(*group_cols, Post.sentiment, func.count())
                .group_by(*group_cols, Post.sentiment).all())
        agg: dict = {}
        for *keys, s, c in rows:
            k = tuple(keys)
            agg.setdefault(k, {"total": 0, "pos": 0, "neu": 0, "neg": 0})
            agg[k]["total"] += c
            if s in ("pos", "neu", "neg"):
                agg[k][s] += c
        return agg

    from ..services.countries import centroid, country_name as cname
    countries = split([Post.country, Post.country_name])
    regions = split([Post.country, Post.region])
    out_countries = []
    for k, v in sorted(countries.items(), key=lambda x: -x[1]["total"]):
        cc = k[0]
        cen = centroid(cc)
        out_countries.append({"country": cc, "name": k[1] or cname(cc) or cc,
                              "lat": cen[0] if cen else None, "lon": cen[1] if cen else None, **v})
    return {
        "countries": out_countries,
        "regions": [{"country": k[0], "region": k[1], **v}
                    for k, v in sorted(regions.items(), key=lambda x: -x[1]["total"]) if k[1]][:100],
    }


@router.get("/emotions")
def emotions(topic_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    q, _ = _scope(db, topic_id, days)
    rows = (q.filter(Post.emotion.isnot(None))
            .with_entities(Post.emotion, func.count())
            .group_by(Post.emotion).order_by(func.count().desc()).all())
    return [{"emotion": e, "count": c} for e, c in rows]


@router.get("/funnel")
def sentiment_funnel(topic_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    """Sentiment conversion: reached -> engaged -> sentiment split (pos/neu/neg)."""
    q, _ = _scope(db, topic_id, days)
    total = q.count()
    with_eng = q.filter(func.cast(Post.engagement, Text) != "{}").count()
    by_sent = dict(q.with_entities(Post.sentiment, func.count()).group_by(Post.sentiment).all())
    return {
        "total": total,
        "engaged": with_eng,
        "pos": by_sent.get("pos", 0),
        "neu": by_sent.get("neu", 0),
        "neg": by_sent.get("neg", 0),
    }


@router.get("/brand-health")
def brand_health(topic_id: int | None = None, days: int = 14, db: Session = Depends(get_db)):
    return insights.brand_health(db, topic_id, days)


@router.get("/momentum")
def momentum(topic_id: int | None = None, days: int = 14, db: Session = Depends(get_db)):
    return insights.momentum_quadrant(db, topic_id, days)


@router.get("/crisis")
def crisis(topic_id: int | None = None, days: int = 14, db: Session = Depends(get_db)):
    return insights.crisis(db, topic_id, days)


@router.get("/flow")
def flow(topic_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    return insights.sentiment_flow(db, topic_id, days)


@router.get("/pyramid")
def pyramid(topic_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    return insights.author_pyramid(db, topic_id, days)


@router.get("/issues")
def issues(topic_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    """Aggregate audience & issue intelligence (no individual profiling)."""
    return {"issues": insights.issues(db, topic_id, days)}


@router.get("/anomalies")
def anomalies(topic_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    return insights.anomalies(db, topic_id, days)


@router.get("/topic-model")
def topic_model(topic_id: int | None = None, days: int = 14, db: Session = Depends(get_db)):
    return insights.topic_model(db, topic_id, days)


# ---- Data Explorer: generic aggregate pivot (dimension x measure x filters) ----

_DIM_COL = {"platform": Post.platform, "sentiment": Post.sentiment, "emotion": Post.emotion,
            "issue": Post.issue, "stance": Post.stance, "country": Post.country_name,
            "lang": Post.lang, "domain": Post.domain}


@router.get("/pivot")
def pivot(dimension: str = "platform", measure: str = "count",
          topic_id: int | None = None, days: int = 30, limit: int = 30,
          db: Session = Depends(get_db)):
    """Self-serve aggregation: group visible posts by a dimension and compute a
    measure. Aggregate rows only — the building block of the Data Explorer."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    base = [Post.is_hidden.is_(False), Post.posted_at >= since]
    if topic_id:
        base.append(Post.topic_id == topic_id)

    if dimension == "day":
        col = func.date_trunc("day", Post.posted_at)
        label_fn = lambda v: v.date().isoformat() if v else "?"  # noqa: E731
    elif dimension == "topic":
        col = func.jsonb_array_elements_text(Post.topics)
        label_fn = str
    else:
        col = _DIM_COL.get(dimension)
        if col is None:
            raise HTTPException(400, f"unknown dimension '{dimension}'")
        label_fn = lambda v: v if v is not None else "(none)"  # noqa: E731

    measures = {
        "count": func.count(),
        "reach": func.coalesce(func.sum(Post.reach), 0),
        "emv": func.coalesce(func.sum(Post.emv), 0),
        "avg_sentiment": func.coalesce(func.avg(Post.sentiment_score), 0),
        "engagement": func.coalesce(func.sum(
            func.coalesce(Post.engagement["likes"].as_float(), 0)
            + func.coalesce(Post.engagement["comments"].as_float(), 0)
            + func.coalesce(Post.engagement["shares"].as_float(), 0)), 0),
    }
    m = measures.get(measure)
    if m is None:
        raise HTTPException(400, f"unknown measure '{measure}'")

    order = col if dimension == "day" else m.desc()
    rows = (db.query(col.label("k"), m.label("v")).filter(and_(*base))
            .group_by("k").order_by(order).limit(min(limit, 200)).all())
    data = [{"key": label_fn(k), "value": round(float(v), 2)} for k, v in rows if k is not None]
    return {"dimension": dimension, "measure": measure, "rows": data}


@router.get("/heatmap")
def heatmap(topic_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    return {"grid": insights.heatmap(db, topic_id, days)}


@router.get("/constellation")
def constellation(topic_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    return insights.constellation(db, topic_id, days)


@router.get("/network")
def network(topic_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    return insights.influencer_network(db, topic_id, days)


@router.get("/waterfall")
def waterfall(topic_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    return insights.sentiment_waterfall(db, topic_id, days)


@router.get("/forecast")
def forecast(topic_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    return insights.forecast(db, topic_id, days)


@router.get("/galaxy")
def galaxy(topic_id: int | None = None, days: int = 7, db: Session = Depends(get_db)):
    return insights.galaxy(db, topic_id, days)


@router.get("/narratives")
def narratives(topic_id: int | None = None, days: int = 14, db: Session = Depends(get_db)):
    return ai_insights.narratives(db, topic_id, days)


@router.get("/discourse")
async def discourse(topic_id: int | None = None, days: int = 14, db: Session = Depends(get_db)):
    return await ai_insights.discourse_clusters(db, topic_id, days)


@router.get("/causal")
async def causal(topic_id: int | None = None, days: int = 14, db: Session = Depends(get_db)):
    return await ai_insights.causal_chains(db, topic_id, days)


@router.get("/brief")
async def brief(topic_id: int | None = None, days: int = 1, db: Session = Depends(get_db)):
    return await ai_insights.daily_brief(db, topic_id, days)
