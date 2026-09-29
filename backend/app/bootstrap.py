"""First-boot schema creation + seeding, safe to run from API and worker
concurrently — a Postgres advisory lock serializes the create_all race."""
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
    ("appstore", "appstore", 2),
    ("factcheck", "factcheck", 2),
    ("podcast", "podcastindex", 2),
    ("places", "places", 2),
    ("facebook", "facebook_stealth", 3),
    ("instagram", "instagram_stealth", 3),
    ("tiktok", "tiktok_stealth", 3),
    ("x", "x_stealth", 3),
]


# Lightweight additive migrations — create_all never ALTERs existing tables, so
# new columns are added here with IF NOT EXISTS (idempotent, data-preserving).
_MIGRATIONS = [
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS emotion VARCHAR(16)",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS entities JSON DEFAULT '[]'::json",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS virality INTEGER",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS risk INTEGER",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS country VARCHAR(2)",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS country_name VARCHAR(80)",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS region VARCHAR(120)",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS issue VARCHAR(60)",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS stance VARCHAR(10)",
    "CREATE INDEX IF NOT EXISTS ix_posts_emotion ON posts (emotion)",
    "CREATE INDEX IF NOT EXISTS ix_posts_country ON posts (country)",
    "CREATE INDEX IF NOT EXISTS ix_posts_issue ON posts (issue)",
    "ALTER TABLE geo_cache ADD COLUMN IF NOT EXISTS country VARCHAR(2)",
    "ALTER TABLE geo_cache ADD COLUMN IF NOT EXISTS country_name VARCHAR(80)",
    "ALTER TABLE geo_cache ADD COLUMN IF NOT EXISTS region VARCHAR(120)",
    # json -> jsonb so jsonb_* functions, containment, and equality work.
    # Guarded so the table is only rewritten once (not on every boot).
    *[f"""DO $$ BEGIN
        IF (SELECT data_type FROM information_schema.columns
            WHERE table_name='posts' AND column_name='{col}') = 'json' THEN
          EXECUTE 'ALTER TABLE posts ALTER COLUMN {col} TYPE jsonb USING {col}::jsonb';
        END IF; END $$;"""
      for col in ("topics", "entities", "locations", "media", "engagement")],
    "CREATE INDEX IF NOT EXISTS ix_posts_topics_gin ON posts USING gin (topics)",
]


def init_schema_and_seed() -> None:
    """All schema + seeding under one advisory lock on a single session, so the
    API and worker booting together never race (no duplicate-key tracebacks)."""
    from sqlalchemy.orm import Session
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:id)"), {"id": _LOCK_ID})
        try:
            Base.metadata.create_all(conn)
            for stmt in _MIGRATIONS:
                conn.execute(text(stmt))
            conn.commit()
            with Session(bind=conn) as db:  # seed on the SAME locked connection
                _seed_sources(db)
                _seed_sessions(db)
                _seed_admin(db)
                _seed_providers(db)
                db.commit()
        finally:
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
    from .config import settings
    from .models import User
    from .services.auth import hash_password
    if db.query(User).count() == 0:
        db.add(User(username=settings.admin_user,
                    password_hash=hash_password(settings.admin_password), role="admin"))
