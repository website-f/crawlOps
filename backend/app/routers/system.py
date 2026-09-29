"""Crawl Ops / System Health — one place to see whether the crawler is healthy.

Aggregates what already gets recorded (fetch_runs, posts.enrichment_status,
token_usage, the proxy scorer, the circuit-breaker Redis keys) into per-connector
reliability, enrichment backlog, proxy health, and throughput. Read-only.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import FetchRun, Post, Proxy, Source, TokenUsage
from ..services.proxy_manager import proxy_manager

router = APIRouter(prefix="/api/system", tags=["system"])


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = max(0, min(len(values) - 1, int(round((p / 100.0) * (len(values) - 1)))))
    return round(values[k], 2)


def _redis():
    try:
        return proxy_manager.r
    except Exception:  # noqa: BLE001
        return None


@router.get("/crawl")
def crawl_health(hours: int = 24, db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(hours=max(1, min(hours, 168)))
    r = _redis()

    sources = {s.id: s for s in db.query(Source).all()}
    runs = (db.query(FetchRun)
            .filter(FetchRun.started_at >= since)
            .order_by(FetchRun.id.desc()).all())

    # ---- per-connector reliability ----
    agg: dict[int, dict] = {}
    for run in runs:
        a = agg.setdefault(run.source_id, {"runs": 0, "errors": 0, "found": 0,
                                           "inserted": 0, "lat": []})
        a["runs"] += 1
        if run.error:
            a["errors"] += 1
        a["found"] += run.found or 0
        a["inserted"] += run.inserted or 0
        if run.finished_at and run.started_at:
            a["lat"].append((run.finished_at - run.started_at).total_seconds())

    connectors = []
    for sid, s in sources.items():
        a = agg.get(sid, {"runs": 0, "errors": 0, "found": 0, "inserted": 0, "lat": []})
        cooling = False
        if r is not None:
            try:
                cooling = bool(r.get(f"crawl:cooldown:{sid}"))
            except Exception:  # noqa: BLE001
                cooling = False
        ok_runs = a["runs"] - a["errors"]
        connectors.append({
            "id": sid, "platform": s.platform, "connector": s.connector,
            "tier": s.tier, "enabled": s.enabled, "status": s.status,
            "cooling": cooling,
            "runs": a["runs"], "errors": a["errors"],
            "success_rate": round(100 * ok_runs / a["runs"], 1) if a["runs"] else None,
            "found": a["found"], "inserted": a["inserted"],
            "p50_latency_s": _pct(a["lat"], 50), "p95_latency_s": _pct(a["lat"], 95),
            "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
            "last_error": (s.last_error or "")[:200] or None,
        })
    connectors.sort(key=lambda c: (c["success_rate"] if c["success_rate"] is not None else 101,
                                   -c["runs"]))

    # ---- enrichment backlog ----
    status_rows = (db.query(Post.enrichment_status, func.count(Post.id))
                   .group_by(Post.enrichment_status).all())
    backlog = {k or "unknown": v for k, v in status_rows}

    # ---- throughput ----
    def _inserted_since(delta: timedelta) -> int:
        t = datetime.now(timezone.utc) - delta
        return (db.query(func.count(Post.id)).filter(Post.fetched_at >= t).scalar()) or 0

    throughput = {
        "posts_1h": _inserted_since(timedelta(hours=1)),
        "posts_24h": _inserted_since(timedelta(hours=24)),
        "total_posts": (db.query(func.count(Post.id)).scalar()) or 0,
    }

    # ---- proxy pool health ----
    pool = [{"id": p.id, "url": p.url.split("@")[-1], "tag": p.tag,
             "country": p.country, "active": p.active}
            for p in db.query(Proxy).all()]
    try:
        proxies = proxy_manager.stats(pool)
    except Exception:  # noqa: BLE001
        proxies = pool

    # ---- AI usage (last window) ----
    ai_rows = (db.query(TokenUsage.provider, TokenUsage.task, func.count(TokenUsage.id),
                        func.coalesce(func.sum(TokenUsage.prompt_tokens), 0),
                        func.coalesce(func.sum(TokenUsage.completion_tokens), 0))
               .filter(TokenUsage.created_at >= since)
               .group_by(TokenUsage.provider, TokenUsage.task).all())
    ai_usage = [{"provider": p, "task": t, "calls": c,
                 "prompt_tokens": int(pt), "completion_tokens": int(ct)}
                for p, t, c, pt, ct in ai_rows]

    # ---- headline rollup ----
    total_runs = sum(a["runs"] for a in agg.values())
    total_errors = sum(a["errors"] for a in agg.values())
    summary = {
        "window_hours": max(1, min(hours, 168)),
        "sources_total": len(sources),
        "sources_enabled": sum(1 for s in sources.values() if s.enabled),
        "sources_cooling": sum(1 for c in connectors if c["cooling"]),
        "sources_error": sum(1 for s in sources.values() if s.status == "error"),
        "runs": total_runs,
        "run_success_rate": round(100 * (total_runs - total_errors) / total_runs, 1)
        if total_runs else None,
        "enrichment_pending": backlog.get("pending", 0) + backlog.get("failed_llm", 0),
        "proxies_active": sum(1 for p in pool if p["active"]),
        "proxies_total": len(pool),
    }

    return {"summary": summary, "connectors": connectors, "backlog": backlog,
            "throughput": throughput, "proxies": proxies, "ai_usage": ai_usage}
