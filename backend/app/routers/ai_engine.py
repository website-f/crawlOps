from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import TokenUsage
from ..services.gateway import PROVIDER_TEST_MODEL, gateway

router = APIRouter(prefix="/api/ai", tags=["ai-engine"])

PROVIDER_ORDER = ["groq", "openrouter", "mistral", "huggingface", "deepseek", "openai"]
PROVIDER_TIER = {"groq": "free", "openrouter": "free", "mistral": "free",
                 "huggingface": "free", "deepseek": "paid", "openai": "paid"}


@router.get("/providers")
def providers():
    return [{"name": p, "tier": PROVIDER_TIER[p], "test_model": PROVIDER_TEST_MODEL[p]}
            for p in PROVIDER_ORDER]


@router.post("/providers/{provider}/test")
async def test_provider(provider: str):
    return await gateway.test_provider(provider)


@router.post("/providers/test-all")
async def test_all():
    import asyncio
    return await asyncio.gather(*[gateway.test_provider(p) for p in PROVIDER_ORDER])


@router.get("/usage")
def usage(days: int = 7, db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    base = db.query(TokenUsage).filter(TokenUsage.created_at >= since)

    by_provider = (db.query(TokenUsage.provider,
                            func.sum(TokenUsage.prompt_tokens),
                            func.sum(TokenUsage.completion_tokens),
                            func.count())
                   .filter(TokenUsage.created_at >= since)
                   .group_by(TokenUsage.provider).all())
    by_task = (db.query(TokenUsage.task,
                        func.sum(TokenUsage.prompt_tokens),
                        func.sum(TokenUsage.completion_tokens),
                        func.count())
               .filter(TokenUsage.created_at >= since)
               .group_by(TokenUsage.task).all())
    daily = (db.query(func.date_trunc("day", TokenUsage.created_at).label("d"),
                      TokenUsage.provider,
                      func.sum(TokenUsage.prompt_tokens + TokenUsage.completion_tokens))
             .filter(TokenUsage.created_at >= since)
             .group_by("d", TokenUsage.provider).order_by("d").all())
    recent_fallbacks = (base.filter(TokenUsage.fallback_depth > 0)
                        .order_by(TokenUsage.created_at.desc()).limit(50).all())

    return {
        "by_provider": [{"provider": p, "prompt": int(pt or 0), "completion": int(ct or 0),
                         "calls": int(n)} for p, pt, ct, n in by_provider],
        "by_task": [{"task": t, "prompt": int(pt or 0), "completion": int(ct or 0),
                     "calls": int(n)} for t, pt, ct, n in by_task],
        "daily": [{"day": d.date().isoformat(), "provider": p, "tokens": int(tok or 0)}
                  for d, p, tok in daily],
        "fallback_events": [{"at": u.created_at.isoformat(), "task": u.task,
                             "model": u.model, "provider": u.provider}
                            for u in recent_fallbacks],
    }
