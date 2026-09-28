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
    ("news", "rss", 2),
    ("facebook", "facebook_stealth", 3),
    ("instagram", "instagram_stealth", 3),
    ("tiktok", "tiktok_stealth", 3),
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
    "CREATE INDEX IF NOT EXISTS ix_posts_emotion ON posts (emotion)",
    "CREATE INDEX IF NOT EXISTS ix_posts_country ON posts (country)",
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
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:id)"), {"id": _LOCK_ID})
        try:
            Base.metadata.create_all(conn)
            for stmt in _MIGRATIONS:
                conn.execute(text(stmt))
            conn.commit()
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": _LOCK_ID})
            conn.commit()

    with SessionLocal() as db:
        existing = {(s.platform, s.connector) for s in db.query(Source).all()}
        for platform, connector, tier in DEFAULT_SOURCES:
            if (platform, connector) not in existing:
                db.add(Source(platform=platform, connector=connector, tier=tier,
                              enabled=tier == 1))
        db.commit()
