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
    active: Mapped[bool] = mapped_column(Boolean, default=True)   # auto-run on schedule
    run_once: Mapped[bool] = mapped_column(Boolean, default=False)  # queued single "Run now"
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
    # secrets (API keys/tokens) encrypted with the SECRET_KEY-derived Fernet key;
    # non-secret settings stay in `config`. See services/credentials.py.
    secrets_enc: Mapped[str] = mapped_column(Text, default="")
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
    custom_score: Mapped[float | None] = mapped_column(Float)       # team impact score
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    bot_suspect: Mapped[bool] = mapped_column(Boolean, default=False)
    enrichment_status: Mapped[str] = mapped_column(String(20), default="pending")
    labels: Mapped[list] = mapped_column(JSONB, default=list)       # user tags (workflow)
    sentiment_locked: Mapped[bool] = mapped_column(Boolean, default=False)  # manual override
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
    # bumped on every password change -> invalidates all previously-issued tokens
    token_version: Mapped[int] = mapped_column(Integer, default=0)
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


class Tag(Base):
    """A colored label operators apply to posts (Meltwater-style workflow tagging)."""
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    color: Mapped[str] = mapped_column(String(16), default="#2a78d6")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SavedView(Base):
    """A named feed filter set (Meltwater 'saved search' / custom category)."""
    __tablename__ = "saved_views"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    params: Mapped[dict] = mapped_column(JSON, default=dict)   # {q, platforms, sentiments, ...}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Dashboard(Base):
    """A user-built dashboard: an ordered list of widgets over the analytics endpoints."""
    __tablename__ = "dashboards"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    widgets: Mapped[list] = mapped_column(JSON, default=list)  # [{id,type,title,topic_id,days}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------------------
# Dark-web research warehouse (StealthMole-style). Deliberately NOT tied to the
# topic lifecycle: findings are harvested intel that must survive a topic being
# deleted and be reusable when the same query is researched again. The query-hash
# cache mirrors StealthMole's search_id = sha256(normalized query).
# ---------------------------------------------------------------------------
class ResearchQuery(Base):
    """One row per distinct normalized research query = the cache key. Re-running
    the same query hits this row; if it's fresh, findings are served from the
    warehouse instead of re-crawling Tor."""
    __tablename__ = "research_queries"
    id: Mapped[int] = mapped_column(primary_key=True)
    query_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # sha256(normalized)
    query_text: Mapped[str] = mapped_column(Text, default="")
    algorithm: Mapped[str] = mapped_column(String(20), default="darkweb")  # darkweb|camofox
    status: Mapped[str] = mapped_column(String(20), default="idle")  # idle|running|done|error
    summary: Mapped[str] = mapped_column(Text, default="")           # AI brief over the findings
    finding_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    first_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)


class ResearchFinding(Base):
    """A harvested intel node. Topic-independent and deduped by content hash so a
    re-crawl updates last_seen/last_scan in place instead of duplicating. Carries
    StealthMole's first_seen / last_seen / last_scan stamps."""
    __tablename__ = "research_findings"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    finding_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # sha256(source_url|text)
    source_url: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(16), default="onion", index=True)  # onion|web
    source_host: Mapped[str] = mapped_column(String(120), default="", index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text, default="")
    lang: Mapped[str] = mapped_column(String(12), default="")
    entities: Mapped[list] = mapped_column(JSONB, default=list)   # extracted IOCs [{type,value}]
    threat_level: Mapped[str | None] = mapped_column(String(12))  # low|medium|high|critical
    relevance: Mapped[int | None] = mapped_column(Integer)        # 0-100 from the judge
    summary: Mapped[str] = mapped_column(Text, default="")
    raw_meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    last_scan: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchQueryFinding(Base):
    """Link table: which query surfaced which finding, and how strongly. Deleting a
    topic (hence its query link) never deletes the finding itself."""
    __tablename__ = "research_query_findings"
    query_id: Mapped[int] = mapped_column(ForeignKey("research_queries.id", ondelete="CASCADE"),
                                          primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("research_findings.id", ondelete="CASCADE"),
                                            primary_key=True)
    score: Mapped[float | None] = mapped_column(Float)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
