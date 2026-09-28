import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .bootstrap import init_schema_and_seed
from .routers import (ai_engine, alerts, analytics, explore, posts, settings,
                      sources, suppression, topics)
from .services import meili

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_schema_and_seed()
    try:
        meili.ensure_index()
    except Exception:  # noqa: BLE001 - meili may still be starting; worker retries too
        logging.getLogger("main").warning("meilisearch not ready at startup")
    yield


app = FastAPI(title="CrawlOps", lifespan=lifespan)

app.include_router(topics.router)
app.include_router(posts.router)
app.include_router(analytics.router)
app.include_router(ai_engine.router)
app.include_router(sources.router)
app.include_router(suppression.router)
app.include_router(alerts.router)
app.include_router(settings.router)
app.include_router(explore.router)


@app.get("/api/health")
def health():
    return {"ok": True}
