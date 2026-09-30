import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .bootstrap import init_schema_and_seed
from .routers import (ai_engine, alerts, analytics, authors, auth, benchmark,
                      explore, media, posts, reports, search, settings, sources,
                      suppression, system, topics)
from .services import meili
from .services.auth import current_user

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

# the browser extension calls the API cross-origin; auth is bearer-token so this is safe
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

# public — no auth
app.include_router(auth.router)
app.include_router(media.router)

# protected — every request needs a valid bearer token
_auth = [Depends(current_user)]
for r in (topics, posts, analytics, ai_engine, sources, suppression, alerts,
          settings, explore, benchmark, reports, system, search, authors):
    app.include_router(r.router, dependencies=_auth)


@app.get("/api/health")
def health():
    return {"ok": True}
