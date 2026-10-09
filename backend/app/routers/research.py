"""Dark-web research API — trigger a run, read the warehouse, manage seed sources.

A run takes minutes (Tor + agentic browsing), so POST /run starts it in the background
and returns a query id; the client polls GET /queries/{id}. Results live in the
topic-independent warehouse, so they survive topic deletion and a re-run serves cache.
"""
import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings as app_settings
from ..db import SessionLocal, get_db
from ..models import ResearchFinding, ResearchQuery, Topic
from ..services import research
from ..services.settings_store import get_setting, set_setting

log = logging.getLogger("research.api")
router = APIRouter(prefix="/api/research", tags=["research"])


def _q(rq: ResearchQuery) -> dict:
    return {"id": rq.id, "query_text": rq.query_text, "query_hash": rq.query_hash,
            "status": rq.status, "summary": rq.summary, "finding_count": rq.finding_count,
            "error": rq.error, "algorithm": rq.algorithm,
            "first_run_at": rq.first_run_at.isoformat() if rq.first_run_at else None,
            "last_run_at": rq.last_run_at.isoformat() if rq.last_run_at else None,
            "run_count": rq.run_count}


def _f(f: ResearchFinding) -> dict:
    return {"id": f.id, "source_url": f.source_url, "source_host": f.source_host,
            "source_type": f.source_type, "title": f.title, "text": f.text[:4000],
            "summary": f.summary, "entities": f.entities, "threat_level": f.threat_level,
            "relevance": f.relevance,
            "first_seen": f.first_seen.isoformat() if f.first_seen else None,
            "last_seen": f.last_seen.isoformat() if f.last_seen else None,
            "last_scan": f.last_scan.isoformat() if f.last_scan else None}


class RunIn(BaseModel):
    query: str | None = None
    topic_id: int | None = None
    max_sites: int = 5
    max_steps: int = 8
    force: bool = False


async def _background_run(query_text: str, max_sites: int, max_steps: int, force: bool) -> None:
    with SessionLocal() as db:
        try:
            await research.run_research(db, query_text, max_sites=max_sites,
                                        max_steps=max_steps, force=force)
        except Exception:  # noqa: BLE001
            log.exception("background research failed")


@router.post("/run")
async def run(body: RunIn, db: Session = Depends(get_db)):
    query_text = (body.query or "").strip()
    if not query_text and body.topic_id:
        t = db.get(Topic, body.topic_id)
        if t:
            query_text = t.name
    if not query_text:
        raise HTTPException(400, "provide a query or a topic_id")

    qh = research.query_hash(query_text)
    # serve cache immediately if fresh and not forced
    if not body.force:
        hit = research.cached_query(db, qh, research.FRESH_HOURS_DEFAULT)
        if hit and hit.status == "done":
            return {"started": False, "cached": True, **_q(hit)}

    # mark/clear the row so the client sees 'running' right away, then do work detached
    rq = db.query(ResearchQuery).filter(ResearchQuery.query_hash == qh).first()
    asyncio.create_task(_background_run(query_text, min(body.max_sites, research.MAX_SITES_CAP),
                                        body.max_steps, body.force))
    return {"started": True, "cached": False, "query_hash": qh,
            "id": rq.id if rq else None, "status": "running", "query_text": query_text}


@router.get("/queries")
def list_queries(limit: int = 50, db: Session = Depends(get_db)):
    rows = (db.query(ResearchQuery).order_by(ResearchQuery.last_run_at.desc())
            .limit(min(limit, 200)).all())
    return [_q(r) for r in rows]


@router.get("/queries/{qid}")
def get_query(qid: int, db: Session = Depends(get_db)):
    rq = db.get(ResearchQuery, qid)
    if not rq:
        raise HTTPException(404)
    return {**_q(rq), "findings": [_f(f) for f in research.findings_for(db, rq.id)]}


@router.get("/findings/{fid}")
def get_finding(fid: int, db: Session = Depends(get_db)):
    f = db.get(ResearchFinding, fid)
    if not f:
        raise HTTPException(404)
    return _f(f)


@router.get("/findings")
def list_findings(limit: int = 100, threat: str | None = None, db: Session = Depends(get_db)):
    """The whole warehouse, newest-seen first — independent of any query/topic."""
    q = db.query(ResearchFinding)
    if threat:
        q = q.filter(ResearchFinding.threat_level == threat)
    rows = q.order_by(ResearchFinding.last_seen.desc()).limit(min(limit, 500)).all()
    return [_f(f) for f in rows]


class SeedsIn(BaseModel):
    seeds: list[str] = []


@router.get("/seeds")
def get_seeds(db: Session = Depends(get_db)):
    return {"seeds": (get_setting(db, "darkweb") or {}).get("seeds", [])}


@router.put("/seeds")
def set_seeds(body: SeedsIn, db: Session = Depends(get_db)):
    cfg = dict(get_setting(db, "darkweb") or {})
    cfg["seeds"] = [s.strip() for s in body.seeds if s.strip()]
    set_setting(db, "darkweb", cfg)
    return {"seeds": cfg["seeds"]}


@router.get("/status")
async def status():
    """Is the dark-web tier actually up? (profile 'darkweb' running + Tor reachable.)"""
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.get(f"{app_settings.darkweb_agent_url}/health")
        return {"available": r.status_code == 200, "detail": r.json() if r.status_code == 200 else None}
    except httpx.HTTPError:
        return {"available": False,
                "detail": "dark-web tier is off — start it with: docker compose --profile darkweb up -d"}
