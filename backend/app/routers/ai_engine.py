from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AIProvider, TokenUsage
from ..services.crypto import decrypt, encrypt, mask
from ..services.gateway import gateway

router = APIRouter(prefix="/api/ai", tags=["ai-engine"])

TASKS = ["judge", "enrich", "agent", "embed"]


class ProviderIn(BaseModel):
    name: str
    base_url: str
    api_key: str = ""              # blank on edit = keep existing
    task_models: dict = {}         # {"judge":"model-id", ...}
    available_models: list = []
    priority: int = 100
    enabled: bool = True
    tier: str = "free"


def _dump(p: AIProvider) -> dict:
    return {"id": p.id, "name": p.name, "base_url": p.base_url,
            "key_hint": mask(decrypt(p.api_key_enc)), "has_key": bool(p.api_key_enc),
            "task_models": p.task_models or {}, "available_models": p.available_models or [],
            "priority": p.priority, "enabled": p.enabled, "tier": p.tier}


@router.get("/providers")
def list_providers(db: Session = Depends(get_db)):
    rows = db.query(AIProvider).order_by(AIProvider.priority, AIProvider.id).all()
    return {"providers": [_dump(p) for p in rows], "tasks": TASKS}


@router.post("/providers")
def create_provider(body: ProviderIn, db: Session = Depends(get_db)):
    p = AIProvider(name=body.name, base_url=body.base_url,
                   api_key_enc=encrypt(body.api_key), task_models=body.task_models,
                   available_models=body.available_models, priority=body.priority,
                   enabled=body.enabled, tier=body.tier)
    db.add(p)
    db.commit()
    return _dump(p)


@router.put("/providers/{pid}")
def update_provider(pid: int, body: ProviderIn, db: Session = Depends(get_db)):
    p = db.get(AIProvider, pid)
    if not p:
        raise HTTPException(404)
    p.name, p.base_url = body.name, body.base_url
    p.task_models, p.available_models = body.task_models, body.available_models
    p.priority, p.enabled, p.tier = body.priority, body.enabled, body.tier
    if body.api_key:  # only overwrite the key when a new one is supplied
        p.api_key_enc = encrypt(body.api_key)
    db.commit()
    return _dump(p)


@router.delete("/providers/{pid}")
def delete_provider(pid: int, db: Session = Depends(get_db)):
    p = db.get(AIProvider, pid)
    if p:
        db.delete(p)
        db.commit()
    return {"ok": True}


class TestIn(BaseModel):
    base_url: str
    api_key: str = ""
    model: str
    provider_id: int | None = None   # to reuse a stored key when api_key blank


@router.post("/providers/test")
async def test_provider(body: TestIn, db: Session = Depends(get_db)):
    key = body.api_key
    if not key and body.provider_id:
        p = db.get(AIProvider, body.provider_id)
        key = decrypt(p.api_key_enc) if p else ""
    if not key:
        return {"ok": False, "error": "no API key"}
    return await gateway.test_provider(body.base_url, key, body.model)


class ModelsIn(BaseModel):
    base_url: str
    api_key: str = ""
    provider_id: int | None = None


@router.post("/providers/models")
async def fetch_models(body: ModelsIn, db: Session = Depends(get_db)):
    key = body.api_key
    if not key and body.provider_id:
        p = db.get(AIProvider, body.provider_id)
        key = decrypt(p.api_key_enc) if p else ""
    if not key:
        return {"models": [], "error": "no API key"}
    return {"models": await gateway.list_models(body.base_url, key)}


@router.get("/usage")
def usage(days: int = 7, db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    by_provider = (db.query(TokenUsage.provider, func.sum(TokenUsage.prompt_tokens),
                            func.sum(TokenUsage.completion_tokens), func.count())
                   .filter(TokenUsage.created_at >= since)
                   .group_by(TokenUsage.provider).all())
    by_task = (db.query(TokenUsage.task, func.sum(TokenUsage.prompt_tokens),
                        func.sum(TokenUsage.completion_tokens), func.count())
               .filter(TokenUsage.created_at >= since).group_by(TokenUsage.task).all())
    daily = (db.query(func.date_trunc("day", TokenUsage.created_at).label("d"),
                      TokenUsage.provider,
                      func.sum(TokenUsage.prompt_tokens + TokenUsage.completion_tokens))
             .filter(TokenUsage.created_at >= since)
             .group_by("d", TokenUsage.provider).order_by("d").all())
    return {
        "by_provider": [{"provider": p, "prompt": int(pt or 0), "completion": int(ct or 0),
                         "calls": int(n)} for p, pt, ct, n in by_provider],
        "by_task": [{"task": t, "prompt": int(pt or 0), "completion": int(ct or 0),
                     "calls": int(n)} for t, pt, ct, n in by_task],
        "daily": [{"day": d.date().isoformat(), "provider": p, "tokens": int(tok or 0)}
                  for d, p, tok in daily],
    }
