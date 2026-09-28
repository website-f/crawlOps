from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import FetchRun, Proxy, Source, StealthSession
from ..services.proxy_manager import proxy_manager

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("")
def list_sources(db: Session = Depends(get_db)):
    return [{"id": s.id, "platform": s.platform, "connector": s.connector, "tier": s.tier,
             "enabled": s.enabled, "status": s.status,
             "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
             "last_error": (s.last_error or "")[:300]}
            for s in db.query(Source).order_by(Source.tier, Source.platform).all()]


@router.post("/{source_id}/toggle")
def toggle(source_id: int, db: Session = Depends(get_db)):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(404)
    s.enabled = not s.enabled
    db.commit()
    return {"id": s.id, "enabled": s.enabled}


class ConfigIn(BaseModel):
    config: dict


@router.get("/{source_id}/config")
def get_config(source_id: int, db: Session = Depends(get_db)):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(404)
    return {"connector": s.connector, "config": s.config}


@router.put("/{source_id}/config")
def set_config(source_id: int, body: ConfigIn, db: Session = Depends(get_db)):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(404)
    s.config = body.config
    db.commit()
    return {"id": s.id, "config": s.config}


@router.get("/runs")
def recent_runs(limit: int = 50, db: Session = Depends(get_db)):
    runs = db.query(FetchRun).order_by(FetchRun.id.desc()).limit(min(limit, 200)).all()
    return [{"id": r.id, "topic_id": r.topic_id, "source_id": r.source_id,
             "started_at": r.started_at.isoformat(), "found": r.found,
             "inserted": r.inserted, "error": (r.error or "")[:200]} for r in runs]


# ---- proxies ----

class ProxyIn(BaseModel):
    url: str
    tag: str = "datacenter"   # residential | datacenter
    country: str = ""


@router.get("/proxies")
def list_proxies(db: Session = Depends(get_db)):
    pool = [{"id": p.id, "url": p.url.split("@")[-1], "tag": p.tag,
             "country": p.country, "active": p.active}
            for p in db.query(Proxy).all()]  # strip credentials before returning
    return proxy_manager.stats(pool)


@router.post("/proxies")
def add_proxy(body: ProxyIn, db: Session = Depends(get_db)):
    if body.tag not in ("residential", "datacenter"):
        raise HTTPException(400, "tag must be residential|datacenter")
    p = Proxy(url=body.url, tag=body.tag, country=body.country)
    db.add(p)
    db.commit()
    return {"id": p.id}


@router.delete("/proxies/{proxy_id}")
def delete_proxy(proxy_id: int, db: Session = Depends(get_db)):
    p = db.get(Proxy, proxy_id)
    if p:
        db.delete(p)
        db.commit()
    return {"ok": True}


@router.get("/stealth-sessions")
def stealth_sessions(db: Session = Depends(get_db)):
    return [{"id": s.id, "platform": s.platform, "label": s.label, "status": s.status,
             "daily_used": s.daily_used, "daily_cap": s.daily_cap,
             "last_used_at": s.last_used_at.isoformat() if s.last_used_at else None}
            for s in db.query(StealthSession).all()]
