import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Post, PostMetric, SuppressedAuthor
from ..services import meili
from ..services.media_cache import _media_keys, delete_media_objects, stream_object

router = APIRouter(prefix="/api", tags=["posts"])


@router.get("/posts")
def feed(q: str = "", platform: str = "", topic_id: int | None = None,
         sentiment: str = "", emotion: str = "", lang: str = "", country: str = "",
         stance: str = "", issue: str = "", label: str = "", has_media: bool | None = None,
         min_engagement: int = 0, min_reach: int = 0,
         since_ts: int | None = None, until_ts: int | None = None,
         verified: bool | None = None, sort: str = "posted_ts:desc",
         page: int = Query(1, ge=1), per_page: int = Query(30, le=100),
         db: Session = Depends(get_db)):
    filters = ["is_hidden = false"]

    def _multi(field: str, raw: str, allowed=None):
        vals = [v.strip() for v in raw.split(",") if v.strip()
                and (allowed is None or v.strip() in allowed) and v.strip().replace("-", "").isalnum()]
        if vals:
            filters.append("(" + " OR ".join(f"{field} = '{v}'" for v in vals) + ")")

    if platform:
        _multi("platform", platform)
    if topic_id:
        filters.append(f"topic_id = {topic_id}")
    if sentiment:
        _multi("sentiment", sentiment, ("pos", "neu", "neg"))
    if emotion:
        _multi("emotion", emotion)
    if stance:
        _multi("stance", stance, ("support", "oppose", "neutral"))
    if issue:
        _multi("issue", issue)
    if country:
        _multi("country", country)
    if label:
        # tag names can have spaces — quote + escape rather than the alnum filter
        labs = [f'labels = "{v.strip().replace(chr(34), "")}"'
                for v in label.split(",") if v.strip()]
        if labs:
            filters.append("(" + " OR ".join(labs) + ")")
    if lang.isalpha() and len(lang) <= 8:
        filters.append(f"lang = '{lang}'")
    if has_media is not None:
        filters.append(f"has_media = {'true' if has_media else 'false'}")
    if min_engagement > 0:
        filters.append(f"engagement_total >= {min_engagement}")
    if min_reach > 0:
        filters.append(f"reach >= {int(min_reach)}")
    if since_ts:
        filters.append(f"posted_ts >= {int(since_ts)}")
    if until_ts:
        filters.append(f"posted_ts <= {int(until_ts)}")
    if verified is not None:
        filters.append(f"author_verified = {'true' if verified else 'false'}")

    # watch-mode suppression: exclude from analytics but keep visible -> flag only
    watch_keys = {f"{s.platform}:{s.author_key}" for s in
                  db.query(SuppressedAuthor).filter(SuppressedAuthor.mode == "watch").all()}

    if sort not in ("posted_ts:desc", "posted_ts:asc", "engagement_total:desc",
                    "relevance:desc", "reach:desc", "virality:desc", "risk:desc",
                    "custom_score:desc"):
        sort = "posted_ts:desc"
    try:
        res = meili.search(q, filters, sort, page, per_page)
    except Exception as e:  # noqa: BLE001 - meili down -> clear error, not a 500 traceback
        raise HTTPException(503, f"search unavailable: {e}") from e
    hits = res.get("hits", [])
    for h in hits:
        h["suppression_watch"] = f"{h.get('platform')}:{h.get('author_key')}" in watch_keys
    return {"hits": hits, "total": res.get("totalHits", len(hits)),
            "page": page, "per_page": per_page}


class DeleteIn(BaseModel):
    ids: list[int] | None = None          # explicit selection (bulk delete)
    topic_id: int | None = None           # or delete a whole topic's results
    platform: str | None = None           # optional filters when deleting by topic
    sentiment: str | None = None
    hidden_only: bool = False             # only purge low-relevance/hidden posts


@router.post("/posts/delete")
def bulk_delete(body: DeleteIn, db: Session = Depends(get_db)):
    """Delete posts by explicit ids, or by topic (+optional filters). Frees the DB rows,
    their cached media objects, and the search index entries. This is how storage is
    reclaimed — deleting a topic's fetched results or pruning a selection from the feed."""
    q = db.query(Post)
    if body.ids:
        q = q.filter(Post.id.in_(body.ids))
    elif body.topic_id is not None:
        q = q.filter(Post.topic_id == body.topic_id)
        if body.platform:
            q = q.filter(Post.platform == body.platform)
        if body.sentiment in ("pos", "neu", "neg"):
            q = q.filter(Post.sentiment == body.sentiment)
        if body.hidden_only:
            q = q.filter(Post.is_hidden.is_(True))
    else:
        raise HTTPException(400, "provide ids or topic_id")

    rows = q.with_entities(Post.id, Post.media).all()
    ids = [r[0] for r in rows]
    if not ids:
        return {"deleted": 0}
    keys = _media_keys([r[1] for r in rows])
    db.execute(sa_delete(PostMetric).where(PostMetric.post_id.in_(ids)))
    db.execute(sa_delete(Post).where(Post.id.in_(ids)))
    db.commit()
    meili.delete_posts(ids)
    delete_media_objects(keys)
    return {"deleted": len(ids)}


@router.get("/posts/ids")
def post_ids(topic_id: int | None = None, platform: str = "", sentiment: str = "",
             hidden_only: bool = False, limit: int = 20000, db: Session = Depends(get_db)):
    """All matching post ids (for select-all before a bulk delete)."""
    q = db.query(Post.id)
    if topic_id is not None:
        q = q.filter(Post.topic_id == topic_id)
    if platform:
        q = q.filter(Post.platform == platform)
    if sentiment in ("pos", "neu", "neg"):
        q = q.filter(Post.sentiment == sentiment)
    if hidden_only:
        q = q.filter(Post.is_hidden.is_(True))
    return {"ids": [r[0] for r in q.limit(min(limit, 50000)).all()]}


@router.get("/posts/geo")
def geo_posts(topic_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Post).filter(Post.lat.isnot(None), Post.is_hidden.is_(False))
    if topic_id:
        q = q.filter(Post.topic_id == topic_id)
    return [{"id": p.id, "lat": p.lat, "lon": p.lon, "platform": p.platform,
             "title": p.title or (p.text or "")[:120], "sentiment": p.sentiment,
             "url": p.url} for p in q.limit(3000).all()]


@router.get("/posts/export.csv")
def export_csv(topic_id: int | None = None, platform: str = "", limit: int = 5000,
               db: Session = Depends(get_db)):
    q = db.query(Post).filter(Post.is_hidden.is_(False))
    if topic_id:
        q = q.filter(Post.topic_id == topic_id)
    if platform:
        q = q.filter(Post.platform == platform)
    rows = q.order_by(Post.posted_at.desc()).limit(min(limit, 20000)).all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["platform", "posted_at", "author", "handle", "title", "text",
                "url", "lang", "sentiment", "relevance", "reach", "emv",
                "likes", "comments", "shares", "topics"])
    for p in rows:
        e = p.engagement or {}
        w.writerow([p.platform, p.posted_at.isoformat() if p.posted_at else "",
                    p.author_name, p.author_handle, p.title, (p.text or "").replace("\n", " "),
                    p.url, p.lang, p.sentiment or "", p.relevance or "", p.reach or "",
                    p.emv or "", e.get("likes", 0), e.get("comments", 0), e.get("shares", 0),
                    "; ".join(p.topics or [])])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=crawlops-{stamp}.csv"})


