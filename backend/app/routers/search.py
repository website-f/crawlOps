"""Semantic + hybrid search over post embeddings (pgvector).

Embeddings are already computed during enrichment (for clustering) and persisted to
posts.embedding; here we reuse them for meaning-based search and "more like this".
Returns the same doc shape as the keyword feed so the frontend reuses PostCard.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Post
from ..services import meili
from ..services.gateway import gateway

router = APIRouter(prefix="/api/search", tags=["search"])

EMBED_DIM = 768


def _vec_literal(vec) -> str:
    return "[" + ",".join(f"{float(x):.6f}" for x in vec) + "]"


def _embedding_available(db: Session) -> bool:
    try:
        return bool(db.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='posts' AND column_name='embedding'")).first())
    except Exception:  # noqa: BLE001
        return False


def _hits_from_scored(db: Session, rows) -> dict:
    """rows: iterable of (id, score) in similarity order -> feed-shaped hits."""
    ids = [r.id for r in rows]
    scores = {r.id: round(float(r.score), 4) for r in rows}
    if not ids:
        return {"hits": [], "total": 0}
    posts = {p.id: p for p in db.query(Post).filter(Post.id.in_(ids)).all()}
    hits = []
    for pid in ids:                                   # preserve similarity ordering
        p = posts.get(pid)
        if p is None:
            continue
        doc = meili.doc_from_post(p)
        doc["score"] = scores.get(pid)
        hits.append(doc)
    return {"hits": hits, "total": len(hits)}


class SemanticIn(BaseModel):
    query: str
    topic_id: int | None = None
    limit: int = 30


@router.post("/semantic")
async def semantic(body: SemanticIn, db: Session = Depends(get_db)):
    if not body.query.strip():
        return {"hits": [], "total": 0}
    if not _embedding_available(db):
        raise HTTPException(503, "semantic search needs pgvector (use the pgvector postgres image)")
    if not gateway.available("embed"):
        raise HTTPException(503, "semantic search needs an embedding model — enable one in AI Engine")
    vecs = await gateway.embed([body.query[:1000]])
    if not vecs or len(vecs[0]) != EMBED_DIM:
        raise HTTPException(503, "embedding provider unavailable or returned the wrong dimension")
    params = {"q": _vec_literal(vecs[0]), "k": max(1, min(body.limit, 100))}
    where = ["embedding IS NOT NULL", "is_hidden = false"]
    if body.topic_id:
        where.append("topic_id = :tid")
        params["tid"] = body.topic_id
    sql = ("SELECT id, 1 - (embedding <=> CAST(:q AS vector)) AS score FROM posts WHERE "
           + " AND ".join(where) + " ORDER BY embedding <=> CAST(:q AS vector) LIMIT :k")
    return _hits_from_scored(db, db.execute(text(sql), params).all())


@router.get("/similar/{post_id}")
def similar(post_id: int, limit: int = 12, db: Session = Depends(get_db)):
    if not _embedding_available(db):
        raise HTTPException(503, "semantic search needs pgvector")
    base = db.execute(text(
        "SELECT 1 FROM posts WHERE id = :i AND embedding IS NOT NULL"), {"i": post_id}).first()
    if not base:
        raise HTTPException(404, "this post has no embedding yet — enrichment may still be pending")
    rows = db.execute(text(
        "SELECT id, 1 - (embedding <=> (SELECT embedding FROM posts WHERE id = :i)) AS score "
        "FROM posts WHERE embedding IS NOT NULL AND id <> :i AND is_hidden = false "
        "ORDER BY embedding <=> (SELECT embedding FROM posts WHERE id = :i) LIMIT :k"),
        {"i": post_id, "k": max(1, min(limit, 50))}).all()
    return _hits_from_scored(db, rows)
