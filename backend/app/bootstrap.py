"""First-boot schema creation + seeding, safe to run from API and worker
concurrently — a Postgres advisory lock serializes the create_all race."""
import logging

from sqlalchemy import text

from .db import Base, SessionLocal, engine
from .models import Source  # noqa: F401 - register all models

_LOCK_ID = 0x43724F70  # 'CrOp'

DEFAULT_SOURCES = [
    ("hackernews", "hackernews", 1),
    ("reddit", "reddit", 1),
    ("bluesky", "bluesky", 1),
    ("mastodon", "mastodon", 1),
    ("news", "gdelt", 1),
    ("news", "googlenews", 1),
    ("threads", "threads", 1),
    ("youtube", "youtube", 1),
    ("telegram", "telegram", 1),
    ("arxiv", "arxiv", 1),
    ("sec", "sec", 1),
    ("wikipedia", "wikipedia", 1),
    ("github", "github", 1),
    ("stackexchange", "stackexchange", 1),
    ("clinicaltrials", "clinicaltrials", 1),
    ("news", "rss", 2),
    ("tiktok", "tiktok_watch", 2),      # free public-account watchlists via RSSHub
    ("threads", "threads_watch", 2),
    ("youtube", "youtube_watch", 2),
    ("appstore", "appstore", 2),
    ("factcheck", "factcheck", 2),
    ("podcast", "podcastindex", 2),
    ("places", "places", 2),
    ("facebook", "facebook_stealth", 3),
    ("instagram", "instagram_stealth", 3),
    ("tiktok", "tiktok_stealth", 3),
    ("x", "x_stealth", 3),
]


# Lightweight additive migrations — create_all never ALTERs existing tables, so new
# columns/indexes are declared here as data. They are applied ONLY when genuinely
# missing (checked against the catalog first): a no-op ALTER still grabs ACCESS
# EXCLUSIVE on the table to check, and on a busy DB that queues behind — and then
# blocks — every reader for the duration of the lock wait. Running DDL only when
# there's real work keeps restarts lock-free on a populated database.
_ADD_COLUMNS = [
    ("posts", "emotion", "VARCHAR(16)"),
    ("posts", "entities", "JSON DEFAULT '[]'::json"),
    ("posts", "virality", "INTEGER"),
    ("posts", "risk", "INTEGER"),
    ("posts", "country", "VARCHAR(2)"),
    ("posts", "country_name", "VARCHAR(80)"),
    ("posts", "region", "VARCHAR(120)"),
    ("sources", "secrets_enc", "TEXT DEFAULT ''"),
    ("posts", "issue", "VARCHAR(60)"),
    ("posts", "stance", "VARCHAR(10)"),
    ("geo_cache", "country", "VARCHAR(2)"),
    ("geo_cache", "country_name", "VARCHAR(80)"),
    ("geo_cache", "region", "VARCHAR(120)"),
    ("topics", "run_once", "BOOLEAN DEFAULT false"),
    ("posts", "labels", "JSONB DEFAULT '[]'::jsonb"),
    ("posts", "sentiment_locked", "BOOLEAN DEFAULT false"),
    ("posts", "custom_score", "DOUBLE PRECISION"),
    ("users", "token_version", "INTEGER NOT NULL DEFAULT 0"),
    # semantic search: per-post embedding (nomic-embed-text = 768d). Stored via raw SQL
    # (not ORM-mapped) so the hot feed path never pays to load 768 floats per post.
    ("posts", "embedding", "vector(768)"),
]
_ADD_INDEXES = [
    ("ix_posts_emotion", "CREATE INDEX ix_posts_emotion ON posts (emotion)"),
    ("ix_posts_country", "CREATE INDEX ix_posts_country ON posts (country)"),
    ("ix_posts_issue", "CREATE INDEX ix_posts_issue ON posts (issue)"),
    ("ix_posts_topics_gin", "CREATE INDEX ix_posts_topics_gin ON posts USING gin (topics)"),
    ("ix_posts_embedding", "CREATE INDEX ix_posts_embedding ON posts "
     "USING hnsw (embedding vector_cosine_ops)"),
]
# json -> jsonb so jsonb_* functions, containment, and equality work. The DO block
# only rewrites a column still typed 'json', so it is a catalog-check no-op once done.
_JSONB_MIGRATIONS = [
    f"""DO $$ BEGIN
        IF (SELECT data_type FROM information_schema.columns
            WHERE table_name='posts' AND column_name='{col}') = 'json' THEN
          EXECUTE 'ALTER TABLE posts ALTER COLUMN {col} TYPE jsonb USING {col}::jsonb';
        END IF; END $$;"""
    for col in ("topics", "entities", "locations", "media", "engagement")
]


def _existing_columns(conn) -> set:
    rows = conn.execute(text(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema='public'")).all()
    return {(t, c) for t, c in rows}


def _existing_indexes(conn) -> set:
    rows = conn.execute(text(
        "SELECT indexname FROM pg_indexes WHERE schemaname='public'")).all()
    return {r[0] for r in rows}


def init_schema_and_seed() -> None:
    """All schema + seeding under one advisory lock on a single session, so the
    API and worker booting together never race (no duplicate-key tracebacks)."""
    from sqlalchemy.orm import Session
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:id)"), {"id": _LOCK_ID})
        try:
            # pgvector must exist before create_all/migrations reference the vector type.
            # If the extension isn't installed (non-pgvector image), degrade gracefully:
            # the embedding column/index are skipped and semantic search returns 503.
            has_vector = False
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
                has_vector = True
            except Exception:  # noqa: BLE001
                conn.rollback()
            Base.metadata.create_all(conn)
            # Safety net: never let a migration queue-block readers for long. If the
            # lock can't be had quickly the DDL errors out and we retry on a later boot
            # (columns are only missing on a fresh DB, where nothing contends anyway).
            conn.execute(text("SET lock_timeout = '4s'"))
            have_cols = _existing_columns(conn)
            for table, col, ddl in _ADD_COLUMNS:
                if "vector" in ddl and not has_vector:
                    continue
                if (table, col) not in have_cols:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
            # jsonb conversion BEFORE the indexes: gin has no operator class for
            # plain json, so on a DB restored from a pre-jsonb dump the reverse
            # order fails ix_posts_topics_gin and crash-loops api + worker.
            for stmt in _JSONB_MIGRATIONS:
                conn.execute(text(stmt))
            have_idx = _existing_indexes(conn)
            for name, ddl in _ADD_INDEXES:
                if "hnsw" in ddl and not has_vector:
                    continue
                if name not in have_idx:
                    conn.execute(text(ddl))
            conn.execute(text("SET lock_timeout = 0"))  # unrestricted for seeding
            conn.commit()
            with Session(bind=conn) as db:  # seed on the SAME locked connection
                _seed_sources(db)
                _seed_sessions(db)
                _seed_admin(db)
                _seed_providers(db)
                db.commit()
        finally:
            # A failed migration leaves the transaction aborted, and every further
            # statement on it raises — including this unlock, which would then mask
            # the real error (e.g. a lock_timeout) behind a PendingRollbackError.
            # The advisory lock is session-level, so it survives the rollback.
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001 - nothing useful left to do here
                logging.getLogger("bootstrap").warning("rollback before unlock failed",
                                                       exc_info=True)
            conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": _LOCK_ID})
            conn.commit()


STEALTH_PLATFORMS = ["facebook", "instagram", "tiktok", "x", "threads"]


def _seed_sources(db) -> None:
    existing = {(s.platform, s.connector) for s in db.query(Source).all()}
    for platform, connector, tier in DEFAULT_SOURCES:
        if (platform, connector) not in existing:
            # stealth (tier 3) sources are enabled so the crawler runs as a
            # fallback when a platform has no working API; tier 2 (rss) starts
            # enabled but dormant until feeds are configured.
            db.add(Source(platform=platform, connector=connector, tier=tier, enabled=True))


def _seed_sessions(db) -> None:
    """One public-browsing stealth session per platform so the crawler has an
    identity to run under. Import real account cookies later to reach walled content."""
    from .models import StealthSession
    have = {s.platform for s in db.query(StealthSession).all()}
    for platform in STEALTH_PLATFORMS:
        if platform not in have:
            db.add(StealthSession(platform=platform, label="auto (public)",
                                  status="ready", daily_cap=40))


PROVIDER_PRESETS = [
    # (name, base_url, tier, priority) — free tiers first in rotation
    ("Groq", "https://api.groq.com/openai/v1", "free", 10),
    ("OpenRouter", "https://openrouter.ai/api/v1", "free", 20),
    ("Mistral", "https://api.mistral.ai/v1", "free", 30),
    ("HuggingFace", "https://router.huggingface.co/v1", "free", 40),
    ("DeepSeek", "https://api.deepseek.com/v1", "paid", 50),
    ("OpenAI", "https://api.openai.com/v1", "paid", 60),
]


def _seed_providers(db) -> None:
    """Preset the common providers (base_url + tier + rotation order) with NO keys,
    disabled, so the operator just adds a key + picks models in the UI. Fully editable."""
    from .models import AIProvider
    have = {p.name for p in db.query(AIProvider).all()}
    for name, base_url, tier, prio in PROVIDER_PRESETS:
        if name not in have:
            db.add(AIProvider(name=name, base_url=base_url, tier=tier, priority=prio,
                              enabled=False, api_key_enc="", task_models={}))


def _seed_admin(db) -> None:
    import logging

    from .config import settings
    from .models import User
    from .services.auth import hash_password
    if db.query(User).count() != 0:
        return
    # refuse to seed a guessable default admin — force a real password to be set
    if not settings.admin_password or settings.admin_password in ("", "crawlops-change-me", "change-me"):
        logging.getLogger("bootstrap").warning(
            "No admin seeded: ADMIN_PASSWORD is unset or the shipped default. "
            "Set a strong ADMIN_PASSWORD in the environment and restart to seed the admin.")
        return
    db.add(User(username=settings.admin_user,
                password_hash=hash_password(settings.admin_password), role="admin"))
