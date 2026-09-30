"""Worker entrypoint — 30s tick scheduler.

Single-flight per topic via a Redis lock (OpenMagpie's SingleFlight pattern):
crashes can't stack runs, and a second worker replica is safe.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import redis

from app.bootstrap import init_schema_and_seed
from app.config import settings
from app.db import SessionLocal
from app.models import Topic
from app.services import meili

from .alerts_engine import evaluate_topic_alerts
from .nightly import run_nightly
from .pipeline import backfill_embeddings, catchup_enrichment, run_topic

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("worker")

TICK_SECONDS = 30
LOCK_TTL = 600


async def tick(r: redis.Redis) -> None:
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        # A topic runs if it auto-runs on schedule AND is due, OR if it was manually
        # queued via "Run now" (run_once) — which fires exactly once even when the
        # topic is paused (active=False), so a paused topic never crawls on its own.
        topics = db.query(Topic).all()
        due = [t for t in topics
               if t.run_once
               or (t.active and (t.last_run_at is None
                                 or t.last_run_at < now - timedelta(minutes=t.schedule_minutes)))]
        for topic in due:
            lock_key = f"lock:topic:{topic.id}"
            if not r.set(lock_key, "1", nx=True, ex=LOCK_TTL):
                continue
            try:
                log.info("running topic %s (%s)%s", topic.id, topic.name,
                         " [run-now]" if topic.run_once else "")
                totals = await run_topic(db, topic)
                log.info("topic %s: found=%s inserted=%s", topic.id,
                         totals["found"], totals["inserted"])
                fired = evaluate_topic_alerts(db, topic.id)
                if fired:
                    log.info("topic %s: %s alert(s) fired", topic.id, fired)
            finally:
                if topic.run_once:                    # consume the one-off request
                    topic.run_once = False
                    db.commit()
                r.delete(lock_key)


async def main() -> None:
    init_schema_and_seed()  # advisory-locked — safe against the API racing it
    for attempt in range(30):
        try:
            meili.ensure_index()
            break
        except Exception:  # noqa: BLE001
            log.info("waiting for meilisearch (%s)", attempt)
            await asyncio.sleep(2)

    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    # a killed container never reaches its finally: — clear orphaned topic locks.
    # (safe with the default single worker replica; scale-out needs owner-tagged locks)
    for k in r.scan_iter("lock:topic:*"):
        r.delete(k)
    last_catchup = 0.0
    log.info("worker up — tick every %ss", TICK_SECONDS)
    while True:
        try:
            await tick(r)
            if time.monotonic() - last_catchup > settings.enrich_catchup_minutes * 60:
                with SessionLocal() as db:
                    n = await catchup_enrichment(db)
                    if n:
                        log.info("catch-up enriched %s posts", n)
                    # once the judge backlog is drained, backfill embeddings for older
                    # posts so the whole corpus becomes semantically searchable
                    if n == 0:
                        b = await backfill_embeddings(db)
                        if b:
                            log.info("backfilled %s embeddings", b)
                last_catchup = time.monotonic()
            await maybe_nightly(r)
        except Exception:  # noqa: BLE001
            log.exception("tick failed")
        await asyncio.sleep(TICK_SECONDS)


async def maybe_nightly(r: redis.Redis) -> None:
    """Run maintenance once per UTC day. A Redis day-marker makes it idempotent."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # nx=True: only the first worker to see a new day claims the run
    if r.set("nightly:done", day, nx=True) or r.get("nightly:done") != day:
        r.set("nightly:done", day)
        with SessionLocal() as db:
            await run_nightly(db)


if __name__ == "__main__":
    asyncio.run(main())
