from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import Text, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Cluster, Post
from ..services import ai_insights, insights
from ..services.spikes import detect_spike, hourly_counts, volume_alert

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _visible(db: Session):
    return db.query(Post).filter(Post.is_hidden.is_(False))


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
