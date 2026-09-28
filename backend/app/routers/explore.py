"""Meltwater-style faceted cross-filter explorer.

The client sends a selection across dimensions (platforms, sentiments, emotions,
countries, topics, date range). We return:
  - facets: counts per option in every dimension, each computed with the OTHER
    dimensions' filters applied but NOT its own — proper cross-filtering, so you
    always see the still-available options in a dimension you're narrowing.
  - summary: totals for the current selection (volume, sentiment split, reach, EMV).
  - timeseries: daily volume split by sentiment for the current selection.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Post

router = APIRouter(prefix="/api/explore", tags=["explore"])


class Selection(BaseModel):
    topic_id: int | None = None
    days: int = 30
    platforms: list[str] = []
    sentiments: list[str] = []
    emotions: list[str] = []
    countries: list[str] = []
    topics: list[str] = []
    search: str = ""


DIMS = {
    "platforms": Post.platform,
    "sentiments": Post.sentiment,
    "emotions": Post.emotion,
    "countries": Post.country,
}


def _base_filters(sel: Selection, exclude: str | None = None) -> list:
    f = [Post.is_hidden.is_(False)]
    if sel.topic_id:
        f.append(Post.topic_id == sel.topic_id)
    if sel.days:
        f.append(Post.posted_at >= datetime.now(timezone.utc) - timedelta(days=sel.days))
    if exclude != "platforms" and sel.platforms:
        f.append(Post.platform.in_(sel.platforms))
    if exclude != "sentiments" and sel.sentiments:
        f.append(Post.sentiment.in_(sel.sentiments))
    if exclude != "emotions" and sel.emotions:
        f.append(Post.emotion.in_(sel.emotions))
    if exclude != "countries" and sel.countries:
        f.append(Post.country.in_(sel.countries))
    if sel.topics:  # topics is a jsonb array; match any selected (@> containment)
        f.append(or_(*[Post.topics.contains([t]) for t in sel.topics]))
    if sel.search:
        f.append(Post.text.ilike(f"%{sel.search}%"))
    return f


@router.post("")
def explore(sel: Selection, db: Session = Depends(get_db)):
    # facets — each dimension counted with the others applied (cross-filter)
    facets: dict[str, list] = {}
    for name, col in DIMS.items():
        rows = (db.query(col, func.count()).filter(and_(*_base_filters(sel, exclude=name)))
                .filter(col.isnot(None)).group_by(col).order_by(func.count().desc()).all())
        facets[name] = [{"value": v, "count": c} for v, c in rows]

    # topic facet (jsonb array unnest)
    topic_rows = (db.query(func.jsonb_array_elements_text(Post.topics).label("t"), func.count())
                  .filter(and_(*_base_filters(sel, exclude="topics")))
                  .group_by("t").order_by(func.count().desc()).limit(25).all())
    facets["topics"] = [{"value": t, "count": c} for t, c in topic_rows]

    # summary for the current full selection
    full = _base_filters(sel)
    total = db.query(func.count()).filter(and_(*full)).scalar() or 0
    sent = dict(db.query(Post.sentiment, func.count()).filter(and_(*full))
                .group_by(Post.sentiment).all())
    reach = db.query(func.coalesce(func.sum(Post.reach), 0)).filter(and_(*full)).scalar()
    emv = db.query(func.coalesce(func.sum(Post.emv), 0)).filter(and_(*full)).scalar()

    # daily volume split by sentiment
    ts_rows = (db.query(func.date_trunc("day", Post.posted_at).label("d"),
                        Post.sentiment, func.count())
               .filter(and_(*full)).group_by("d", Post.sentiment).order_by("d").all())
    ts: dict[str, dict] = {}
    for d, s, c in ts_rows:
        day = d.date().isoformat()
        ts.setdefault(day, {"day": day, "pos": 0, "neu": 0, "neg": 0})
        if s in ("pos", "neu", "neg"):
            ts[day][s] = c

    return {
        "facets": facets,
        "summary": {
            "total": total,
            "sentiment": {"pos": sent.get("pos", 0), "neu": sent.get("neu", 0),
                          "neg": sent.get("neg", 0), "pending": sent.get(None, 0)},
            "reach": int(reach or 0),
            "emv": round(float(emv or 0), 2),
        },
        "timeseries": list(ts.values()),
    }
