import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .bootstrap import init_schema_and_seed
from .config import settings as app_settings
from .routers import (ai_engine, alerts, analytics, authors, auth, benchmark,
                      dashboards, explore, media, posts, reports, scoring, search,
                      settings, sources, suppression, system, topics, workflow)
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

# CORS_ORIGINS allowlists browser origins (comma-separated); "*" = any (dev default).
# Tokens are bearer (not cookies) and the extension bypasses CORS via host_permissions,
# so restricting this to the real frontend origin in prod loses nothing.
_cors = [o.strip() for o in app_settings.cors_origins.split(",") if o.strip()] or ["*"]
app.add_middleware(CORSMiddleware, allow_origins=_cors, allow_methods=["*"],
                   allow_headers=["*"], allow_credentials=False)

# public — no auth
app.include_router(auth.router)
app.include_router(media.router)

# protected — every request needs a valid bearer token
_auth = [Depends(current_user)]
for r in (topics, posts, analytics, ai_engine, sources, suppression, alerts,
          settings, explore, benchmark, reports, system, search, authors, workflow,
          scoring, dashboards):
    app.include_router(r.router, dependencies=_auth)


@app.get("/api/health")
def health():
    return {"ok": True}
