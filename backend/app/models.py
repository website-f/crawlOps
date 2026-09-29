from datetime import datetime, timezone

from sqlalchemy import (JSON, BigInteger, Boolean, DateTime, Float, ForeignKey,
                        Index, Integer, String, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    query: Mapped[str] = mapped_column(Text, default="")           # boolean query
    criteria: Mapped[str] = mapped_column(Text, default="")        # natural-language judge criteria
    threshold: Mapped[int] = mapped_column(Integer, default=55)
    langs: Mapped[list] = mapped_column(JSON, default=list)
    platforms: Mapped[list] = mapped_column(JSON, default=list)    # empty = all
    schedule_minutes: Mapped[int] = mapped_column(Integer, default=30)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(40), index=True)
    connector: Mapped[str] = mapped_column(String(60))             # registry key
    tier: Mapped[int] = mapped_column(Integer, default=1)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="idle")  # idle|ok|error|dormant
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    identity_key: Mapped[str] = mapped_column(String(64), unique=True)
    platform: Mapped[str] = mapped_column(String(40), index=True)
    native_id: Mapped[str] = mapped_column(String(300))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    author_key: Mapped[str] = mapped_column(String(300), index=True, default="")
    author_name: Mapped[str] = mapped_column(String(300), default="")
    author_handle: Mapped[str] = mapped_column(String(300), default="")
    author_avatar: Mapped[str] = mapped_column(Text, default="")
    author_followers: Mapped[int | None] = mapped_column(BigInteger)
    author_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    text: Mapped[str] = mapped_column(Text, default="")
    title: Mapped[str] = mapped_column(Text, default="")
    lang: Mapped[str] = mapped_column(String(12), default="")
    url: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(String(200), default="", index=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    media: Mapped[list] = mapped_column(JSONB, default=list)
    engagement: Mapped[dict] = mapped_column(JSONB, default=dict)
    relevance: Mapped[int | None] = mapped_column(Integer)
    sentiment: Mapped[str | None] = mapped_column(String(10))      # neg|neu|pos
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    emotion: Mapped[str | None] = mapped_column(String(16), index=True)  # Plutchik
    topics: Mapped[list] = mapped_column(JSONB, default=list)
    entities: Mapped[list] = mapped_column(JSONB, default=list)
    virality: Mapped[int | None] = mapped_column(Integer)
    risk: Mapped[int | None] = mapped_column(Integer)
    issue: Mapped[str | None] = mapped_column(String(60), index=True)   # aggregate issue bucket
    stance: Mapped[str | None] = mapped_column(String(10))              # support|oppose|neutral
    locations: Mapped[list] = mapped_column(JSONB, default=list)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    country: Mapped[str | None] = mapped_column(String(2), index=True)   # ISO-2
    country_name: Mapped[str | None] = mapped_column(String(80))
    region: Mapped[str | None] = mapped_column(String(120))             # state/admin1
    geo_confidence: Mapped[float | None] = mapped_column(Float)
    simhash: Mapped[int | None] = mapped_column(BigInteger)
    dup_group: Mapped[str | None] = mapped_column(String(64), index=True)
    cluster_id: Mapped[int | None] = mapped_column(Integer, index=True)
    reach: Mapped[int | None] = mapped_column(BigInteger)
    emv: Mapped[float | None] = mapped_column(Float)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    bot_suspect: Mapped[bool] = mapped_column(Boolean, default=False)
    enrichment_status: Mapped[str] = mapped_column(String(20), default="pending")
    __table_args__ = (
        Index("ix_posts_topic_time", "topic_id", "posted_at"),
        Index("ix_posts_simhash_band", "simhash"),
    )


class PostMetric(Base):
    __tablename__ = "post_metrics"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    engagement: Mapped[dict] = mapped_column(JSON, default=dict)


class Cluster(Base):
    __tablename__ = "clusters"
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    label: Mapped[str] = mapped_column(Text, default="")
    centroid: Mapped[list] = mapped_column(JSON, default=list)
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SuppressedAuthor(Base):
    __tablename__ = "suppressed_authors"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(40))
    author_key: Mapped[str] = mapped_column(String(300))
    mode: Mapped[str] = mapped_column(String(10), default="hide")  # hide|watch
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("platform", "author_key"),)


class Proxy(Base):
    __tablename__ = "proxies"
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(Text)                          # scheme://user:pass@host:port
    tag: Mapped[str] = mapped_column(String(20), default="datacenter")  # residential|datacenter
    country: Mapped[str] = mapped_column(String(8), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class StealthSession(Base):
    __tablename__ = "stealth_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(40), index=True)
    label: Mapped[str] = mapped_column(String(120), default="")
    cookie_ref: Mapped[str] = mapped_column(String(200), default="")
    proxy_id: Mapped[int | None] = mapped_column(ForeignKey("proxies.id"))
    status: Mapped[str] = mapped_column(String(20), default="ready")  # ready|resting|dead
    daily_used: Mapped[int] = mapped_column(Integer, default=0)
    daily_cap: Mapped[int] = mapped_column(Integer, default=40)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SelectorPatch(Base):
    __tablename__ = "selector_patches"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(40), index=True)
    selectors: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(20), default="agent")  # agent|manual
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AlertRule(Base):
    __tablename__ = "alert_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="spike")   # spike|neg_sentiment
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    notify: Mapped[dict] = mapped_column(JSON, default=dict)         # {webhook, telegram, email}
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AlertEvent(Base):
    __tablename__ = "alert_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("alert_rules.id"), index=True)
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class GeoCache(Base):
    __tablename__ = "geo_cache"
    place: Mapped[str] = mapped_column(String(300), primary_key=True)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    country: Mapped[str | None] = mapped_column(String(2))
    country_name: Mapped[str | None] = mapped_column(String(80))
    region: Mapped[str | None] = mapped_column(String(120))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)


class AppSetting(Base):
    """KV config store — CPM overrides, notifier channels, thresholds."""
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BenchmarkEntity(Base):
    """A brand or competitor tracked for share-of-voice (Radar benchmark_entities)."""
    __tablename__ = "benchmark_entities"
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    is_own_brand: Mapped[bool] = mapped_column(Boolean, default=False)


class AIProvider(Base):
    """A user-managed AI provider (OpenAI-compatible). Key stored encrypted.
    `task_models` maps a pipeline task (judge|enrich|agent|embed) to a model id;
    rotation tries providers by `priority` (low first) per task."""
    __tablename__ = "ai_providers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    base_url: Mapped[str] = mapped_column(String(300))   # e.g. https://api.groq.com/openai/v1
    api_key_enc: Mapped[str] = mapped_column(Text, default="")
    task_models: Mapped[dict] = mapped_column(JSON, default=dict)  # {"judge":"llama-3.3-70b", ...}
    available_models: Mapped[list] = mapped_column(JSON, default=list)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    tier: Mapped[str] = mapped_column(String(10), default="free")  # free|paid (label only)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="admin")  # admin | analyst | viewer
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TokenUsage(Base):
    __tablename__ = "token_usage"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task: Mapped[str] = mapped_column(String(20), index=True)       # judge|enrich|agent|embed
    model: Mapped[str] = mapped_column(String(200))                 # model that actually served
    provider: Mapped[str] = mapped_column(String(40), index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    fallback_depth: Mapped[int] = mapped_column(Integer, default=0)  # 0 = primary served
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class FetchRun(Base):
    __tablename__ = "fetch_runs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    topic_id: Mapped[int] = mapped_column(Integer, index=True)
    source_id: Mapped[int] = mapped_column(Integer, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    found: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
