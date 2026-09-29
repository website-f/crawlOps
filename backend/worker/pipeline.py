"""Central pipeline: fetch -> boolean filter -> dedup -> media cache -> store ->
(concurrent) article-extract -> judge -> embed -> score -> geo -> cluster -> index.

Design (docs/ARCHITECTURE.md), tuned for throughput:
  * Phase 1 — FETCH: every enabled source is fetched CONCURRENTLY (bounded). The
    connectors only do network I/O here, never touch the DB, so parallelism is safe.
  * Phase 2 — INGEST: results are written to Postgres SERIALLY (one Session is not
    concurrency-safe). Posts land immediately as enrichment_status='pending' with
    only deterministic fields set, so the feed fills live.
  * Phase 3 — ENRICH: the expensive per-post work (full-article extraction, the LLM
    judge, embeddings) runs CONCURRENTLY (bounded); the DB apply is serial.

This removes the two historical bottlenecks: sources ran one-at-a-time, and every
post was judged by a remote LLM inline & sequentially. The catch-up drain reuses the
same concurrent path for anything deferred while providers were cooling.
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.models import FetchRun, Post, PostMetric, Source, SuppressedAuthor, Topic
from app.services import meili
from app.services.boolean_query import compile_query
from app.services.clustering import assign_cluster, vectorize
from app.services.dedup import identity_key, near_duplicate, simhash64
from app.services.gateway import GatewayUnavailable, gateway
from app.services.credentials import effective_config
from app.services.geocode import geocode
from app.services.countries import country_from_domain, country_from_url, country_name
from app.services.media_cache import cache_media
from app.services.scoring import estimate_emv, estimate_reach
from app.services.settings_store import get_setting

from .connectors import build
from .connectors.base import RawMention, fetch_text
from .prompts import build_judge_messages
from .stealth.camofox_client import LoginRequired, SelectorBroken

log = logging.getLogger("pipeline")

EMOTIONS = {"joy", "trust", "anticipation", "surprise", "fear", "anger",
            "sadness", "disgust", "neutral"}

# Concurrency caps. Fetch fans out across ~24 sources; enrich fans out across posts.
# Both are bounded so we stay polite to remote APIs and don't stampede providers.
FETCH_CONCURRENCY = 6
# Enrich concurrency keeps a local GPU model fed (overlaps embed with judge); Ollama
# queues past its own parallelism, so this is a "keep it busy" number, not a GPU cap.
ENRICH_CONCURRENCY = 8
# Per-cycle inline enrichment cap: a cold-start topic can insert thousands of posts;
# we enrich this many inline (fast, concurrent) and let catch-up drain the overflow so
# one huge topic can't monopolise the tick loop.
ENRICH_INLINE_CAP = 400
# Catch-up drains the backlog in chunks, committing after each, so a worker restart
# mid-backlog keeps the progress it made instead of rolling the whole batch back.
CATCHUP_BATCH = 300
CATCHUP_CHUNK = 40
# Near-dup recall window: how many recent posts (per topic) a new post is compared
# against. Wider = better dedup on busy topics; hamming compare is cheap.
DEDUP_WINDOW = 6000
# Full-article extraction is worth it for the news tier (headline+teaser -> full body).
ARTICLE_PLATFORMS = {"news"}
ARTICLE_MAX_CHARS = 8000
# Hosts whose links are JS redirect wrappers, not real article pages — extraction
# yields nothing, so don't waste a proxy fetch on them.
ARTICLE_SKIP_HOSTS = ("news.google.com",)
# Circuit breaker: a source that fails this many cycles in a row is skipped for a while
# instead of being hammered (mirrors the gateway's provider cooldown).
CONNECTOR_FAIL_THRESHOLD = 2
CONNECTOR_COOLDOWN_S = 300


EMBED_DIM = 768                         # nomic-embed-text; the pgvector column dimension
_embed_col_ok: bool | None = None       # cached: does posts.embedding exist? (pgvector image)


def _clamp_int(v, lo: int = 0, hi: int = 100) -> int | None:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return None


def _vec_literal(vec) -> str:
    return "[" + ",".join(f"{float(x):.6f}" for x in vec) + "]"


def _embedding_enabled(db: DbSession) -> bool:
    """True only when the pgvector `embedding` column exists — checked once, cached, so
    a non-pgvector image just skips storage instead of poisoning the transaction."""
    global _embed_col_ok
    if _embed_col_ok is None:
        try:
            _embed_col_ok = bool(db.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name='posts' AND column_name='embedding'")).first())
        except Exception:  # noqa: BLE001
            _embed_col_ok = False
    return _embed_col_ok


def _store_embedding(db: DbSession, post_id: int, vec) -> None:
    if not vec or len(vec) != EMBED_DIM or not _embedding_enabled(db):
        return
    db.execute(text("UPDATE posts SET embedding = CAST(:e AS vector) WHERE id = :i"),
               {"e": _vec_literal(vec), "i": post_id})


def _redis():
    try:
        from app.services.proxy_manager import proxy_manager
        return proxy_manager.r
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
#  Phase orchestration                                                         #
# --------------------------------------------------------------------------- #
async def run_topic(db: DbSession, topic: Topic) -> dict:
    cq = compile_query(topic.query or topic.name)
    sources = db.query(Source).filter(Source.enabled.is_(True)).all()
    if topic.platforms:
        sources = [s for s in sources if s.platform in topic.platforms]

    hidden_authors = {(s.platform, s.author_key) for s in
                      db.query(SuppressedAuthor).filter(SuppressedAuthor.mode == "hide").all()}
    cpm_table = get_setting(db, "cpm")
    issues = get_setting(db, "issues").get("list") or None
    r = _redis()

    # Build connectors serially (reads config from the DB); skip cooling-down sources.
    prepared: list[tuple[Source, object]] = []
    for source in sources:
        if r is not None:
            try:
                if r.get(f"crawl:cooldown:{source.id}"):
                    continue                         # circuit breaker: still cooling
            except Exception:  # noqa: BLE001
                pass
        # effective_config merges plain config with the source's decrypted secrets
        prepared.append((source, build(source.connector, db, effective_config(source))))

    # End the read transaction before the long concurrent fetch. Otherwise the session
    # sits "idle in transaction" for the whole fetch (tens of seconds), holding a
    # snapshot that blocks VACUUM and — worse — queues behind any startup DDL, which on
    # a deploy/restart stalls every posts read for minutes. Connectors do no shared-DB
    # work in Phase 1 (stealth uses its own session), so this is safe.
    db.commit()

    # ---- Phase 1: concurrent network fetch (NO DB access inside tasks) ----
    sem = asyncio.Semaphore(FETCH_CONCURRENCY)

    async def _fetch(connector):
        if connector is None or not connector.enabled():
            return ("dormant", connector.disabled_reason() if connector else "not implemented")
        async with sem:
            try:
                return ("ok", await connector.fetch(cq))
            except LoginRequired as e:
                return ("login", str(e))
            except SelectorBroken as e:
                return ("heal", e)
            except Exception as e:  # noqa: BLE001 — one source failing never kills the cycle
                return ("error", e)

    fetched = await asyncio.gather(*[_fetch(c) for _, c in prepared])

    # ---- Phase 2: serial ingest + FetchRun bookkeeping (DB writes serial) ----
    totals = {"found": 0, "inserted": 0}
    pairs: list[tuple[Post, RawMention]] = []          # posts to enrich this cycle
    for (source, _connector), (status, payload) in zip(prepared, fetched):
        run = FetchRun(topic_id=topic.id, source_id=source.id)
        db.add(run)
        db.commit()
        ok = False
        try:
            if status == "dormant":
                source.status = "dormant"
                source.last_error = payload
                db.commit()
                continue
            if status == "login":
                source.status = "dormant"           # needs logged-in cookies, not an error
                source.last_error = payload
                run.error = "login required"
                db.commit()
                continue
            if status == "heal":
                mentions = await _heal_and_retry(db, source, payload)
            elif status == "error":
                raise payload
            else:
                mentions = payload
            run.found = len(mentions)
            inserted, new_pairs = await _ingest(db, topic, cq, mentions, hidden_authors)
            run.inserted = inserted
            pairs.extend(new_pairs)
            totals["found"] += run.found
            totals["inserted"] += inserted
            source.status = "ok"
            source.last_error = None
            ok = True
        except Exception as e:  # noqa: BLE001
            log.warning("source %s failed: %s", source.connector, e)
            source.status = "error"
            source.last_error = str(e)[:500]
            run.error = str(e)[:500]
        finally:
            source.last_run_at = datetime.now(timezone.utc)
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        _trip_breaker(r, source.id, ok)

    # ---- Phase 3: concurrent enrichment of this cycle's new posts ----
    if pairs:
        await enrich_batch(db, topic, pairs, cpm_table, issues)

    topic.last_run_at = datetime.now(timezone.utc)
    db.commit()
    return totals


def _trip_breaker(r, source_id: int, ok: bool) -> None:
    """Track consecutive failures per source; open the breaker after the threshold."""
    if r is None:
        return
    try:
        if ok:
            r.delete(f"crawl:fails:{source_id}")
            return
        fails = r.incr(f"crawl:fails:{source_id}")
        r.expire(f"crawl:fails:{source_id}", 3600)
        if fails >= CONNECTOR_FAIL_THRESHOLD:
            r.set(f"crawl:cooldown:{source_id}", "1", ex=CONNECTOR_COOLDOWN_S)
    except Exception:  # noqa: BLE001
        pass


async def _heal_and_retry(db: DbSession, source: Source, err: SelectorBroken) -> list[RawMention]:
    log.info("%s: heuristic empty — invoking AI agent on snapshot", source.platform)
    from .stealth.agent_fallback import agent_extract
    return await agent_extract(db, source.platform, getattr(err, "snapshot", "") or "")


# --------------------------------------------------------------------------- #
#  Phase 2 — ingest (serial DB writes, deterministic fields only)             #
# --------------------------------------------------------------------------- #
async def _ingest(db: DbSession, topic: Topic, cq, mentions: list[RawMention],
                  hidden_authors: set) -> tuple[int, list[tuple[Post, RawMention]]]:
    # near-dup candidates: recent simhashes for this topic. A wider window catches
    # near-duplicates that resurface after a lull (busy topics were losing recall at
    # 2000), which keeps SoV/volume counts honest. Hamming compare is cheap.
    recent = (db.query(Post.simhash, Post.dup_group)
              .filter(Post.topic_id == topic.id, Post.simhash.isnot(None))
              .order_by(Post.id.desc()).limit(DEDUP_WINDOW).all())

    inserted = 0
    docs = []
    pairs: list[tuple[Post, RawMention]] = []
    for m in mentions:
        text_for_match = f"{m.title} {m.text}"
        if not cq.matches(text_for_match):          # central boolean AND/NOT filter
            continue
        if (m.platform, m.author_key) in hidden_authors:
            continue
        ikey = identity_key(m.platform, m.native_id)
        existing = db.query(Post).filter(Post.identity_key == ikey).first()
        if existing is not None:                     # refetch -> engagement time series
            if m.engagement and m.engagement != existing.engagement:
                existing.engagement = m.engagement
                db.add(PostMetric(post_id=existing.id, engagement=m.engagement))
                docs.append(meili.doc_from_post(existing))
            continue

        sh = simhash64(text_for_match)
        dup_group = ikey
        for other_hash, other_group in recent:
            if other_hash is not None and near_duplicate(sh, other_hash):
                dup_group = other_group or dup_group
                break
        recent.append((sh, dup_group))

        media = await cache_media(m.media) if m.media else []

        post = Post(
            identity_key=ikey, platform=m.platform, native_id=str(m.native_id)[:300],
            topic_id=topic.id, author_key=m.author_key[:300], author_name=m.author_name[:300],
            author_handle=m.author_handle[:300], author_avatar=m.author_avatar,
            author_followers=m.author_followers, author_verified=m.author_verified,
            text=m.text, title=m.title, lang=m.lang[:12], url=m.url, domain=m.domain[:200],
            posted_at=m.posted_at or datetime.now(timezone.utc),
            media=media, engagement=m.engagement, simhash=sh, dup_group=dup_group,
            enrichment_status="pending",
        )
        # deterministic geo (keyless, Radar-style): source-declared country (GDELT)
        # first, then domain/url ccTLD. AI may refine with an inferred location later.
        cc = (m.country or None) or country_from_domain(post.domain) or country_from_url(post.url)
        if cc:
            post.country, post.country_name = cc, country_name(cc)
        # deterministic reach can be set now; emv waits on the judged sentiment.
        post.reach = estimate_reach(post.platform, post.engagement, post.author_followers)
        db.add(post)
        db.flush()
        docs.append(meili.doc_from_post(post))
        pairs.append((post, m))
        inserted += 1
        if len(docs) >= 20:                          # progressive commit: feed fills live
            db.commit()
            _index_safe(docs)
            docs = []

    db.commit()
    _index_safe(docs)
    return inserted, pairs


def _index_safe(docs: list[dict]) -> None:
    if not docs:
        return
    try:
        meili.index_posts(docs)
    except Exception:  # noqa: BLE001
        log.warning("meilisearch indexing failed; posts remain in Postgres", exc_info=True)


# --------------------------------------------------------------------------- #
#  Phase 3 — enrichment (concurrent network, serial DB apply)                 #
# --------------------------------------------------------------------------- #
async def _extract_article(url: str) -> str | None:
    """Fetch and extract the full article body for a news URL, via the rotating
    proxy layer. Best-effort: any failure just leaves the RSS teaser in place."""
    if not url:
        return None
    try:
        import trafilatura
    except Exception:  # noqa: BLE001 — dependency optional; degrade to teaser
        return None
    try:
        html = await fetch_text(url, timeout=12, attempts=1, purpose="article")
    except Exception:  # noqa: BLE001
        return None
    try:
        body = trafilatura.extract(html, include_comments=False, include_tables=False,
                                   favor_recall=True)
    except Exception:  # noqa: BLE001
        return None
    return body or None


async def _judge(topic: Topic, platform: str, author: str, title: str,
                 text: str, issues) -> tuple[str, dict | None]:
    """LLM judge for one post — pure network, safe to run concurrently.
    Returns ('done', data) | ('pending', None) | ('failed', None)."""
    try:
        data = await gateway.chat_json(
            "judge",
            build_judge_messages(topic.criteria, platform, author, title, text, issues),
            max_tokens=400)
        return "done", data
    except GatewayUnavailable:
        return "pending", None
    except Exception:  # noqa: BLE001
        log.warning("judge failed for %s", title[:60], exc_info=True)
        return "failed", None


async def _enrich_fetch(topic: Topic, post: Post, m: RawMention, issues,
                        sem: asyncio.Semaphore, extract: bool = True) -> dict:
    """All network work for one post (article body, judge, embedding), bounded by
    `sem`. NO DB access — safe to run concurrently across posts."""
    async with sem:
        text = m.text or post.text or ""
        if (extract and post.platform in ARTICLE_PLATFORMS and post.url
                and not any(h in (post.domain or post.url) for h in ARTICLE_SKIP_HOSTS)):
            body = await _extract_article(post.url)
            if body and len(body) > len(text):
                text = body[:ARTICLE_MAX_CHARS]
        status, data = await _judge(
            topic, post.platform, m.author_name or m.author_handle, post.title, text, issues)
        vec = None
        try:
            vec = (await vectorize([f"{post.title} {text}"[:1000]]))[0]
        except Exception:  # noqa: BLE001
            vec = None
    return {"text": text, "status": status, "data": data, "vec": vec}


def _apply_judge(post: Post, data: dict, topic: Topic) -> None:
    post.relevance = max(0, min(100, int(data.get("relevance", 0))))
    post.sentiment = data.get("sentiment") if data.get("sentiment") in ("neg", "neu", "pos") else "neu"
    post.sentiment_score = max(-1.0, min(1.0, float(data.get("sentiment_score", 0))))
    emo = data.get("emotion")
    post.emotion = emo if emo in EMOTIONS else "neutral"
    post.lang = post.lang or (data.get("lang") or "")[:12]
    post.topics = [str(t)[:40] for t in (data.get("topics") or [])[:3]]
    post.entities = [str(e)[:60] for e in (data.get("entities") or [])[:5]]
    post.virality = _clamp_int(data.get("virality"))
    post.risk = _clamp_int(data.get("risk"))
    post.issue = (str(data.get("issue"))[:60] or None) if data.get("issue") else None
    post.stance = data.get("stance") if data.get("stance") in ("support", "oppose", "neutral") else "neutral"
    post.locations = [str(x)[:250] for x in (data.get("locations") or [])[:2]]
    post.bot_suspect = bool(data.get("spam_or_bot", False))
    threshold = topic.threshold or settings.judge_threshold_default
    if not data.get("relevant", True) or post.relevance < threshold:
        post.is_hidden = True                         # stored + auditable, not shown


async def _finalize(db: DbSession, topic: Topic, post: Post, res: dict,
                    cpm_table: dict | None) -> None:
    """Serial DB apply for one enriched post: judge fields, scoring, geo, cluster."""
    status, data = res["status"], res["data"]
    if status == "done" and data is not None:
        _apply_judge(post, data, topic)
        post.enrichment_status = "done"
    elif status == "pending":
        post.enrichment_status = "pending"            # catch-up job re-runs it
    else:
        post.enrichment_status = "failed_llm"

    post.reach = estimate_reach(post.platform, post.engagement, post.author_followers)
    post.emv = estimate_emv(post.platform, post.reach, post.sentiment, cpm_table)

    if post.locations and not post.is_hidden:
        geo = await geocode(db, post.locations[0])
        if geo:
            post.lat, post.lon = geo["lat"], geo["lon"]
            post.region, post.geo_confidence = geo["region"], geo["confidence"]
            if not post.country:  # keep the deterministic source-country if already set
                post.country, post.country_name = geo["country"], geo["country_name"]

    if not post.is_hidden and res.get("vec"):
        try:
            post.cluster_id = assign_cluster(db, topic.id, post.platform,
                                             res["vec"], post.title or post.text[:120])
        except Exception:  # noqa: BLE001
            log.warning("clustering skipped", exc_info=True)
    # persist the embedding we already computed -> semantic search + "more like this"
    if res.get("vec"):
        _store_embedding(db, post.id, res["vec"])


async def enrich_batch(db: DbSession, topic: Topic,
                       pairs: list[tuple[Post, RawMention]],
                       cpm_table: dict | None, issues) -> int:
    """Concurrently do the network-bound enrichment for a batch of new posts, then
    apply the results to the DB serially. Overflow past the cap stays 'pending'."""
    pairs = pairs[:ENRICH_INLINE_CAP]
    extract = gateway.available("judge")   # skip wasted article fetches when AI is off
    sem = asyncio.Semaphore(ENRICH_CONCURRENCY)
    results = await asyncio.gather(
        *[_enrich_fetch(topic, post, m, issues, sem, extract) for post, m in pairs],
        return_exceptions=True)
    docs, done = [], 0
    for (post, _m), res in zip(pairs, results):
        if isinstance(res, Exception):
            post.enrichment_status = "failed_llm"
            continue
        await _finalize(db, topic, post, res, cpm_table)
        if post.enrichment_status == "done":
            done += 1
        docs.append(meili.doc_from_post(post))
        if len(docs) >= 20:
            db.commit()
            _index_safe(docs)
            docs = []
    db.commit()
    _index_safe(docs)
    return done


async def catchup_enrichment(db: DbSession) -> int:
    """Re-run enrichment for posts deferred while every provider was cooling.
    Uses the same concurrent network + serial apply path as the live cycle."""
    if not gateway.available("judge"):
        return 0                                      # nothing to gain; don't burn network
    pending = (db.query(Post)
               .filter(Post.enrichment_status.in_(["pending", "failed_llm"]))
               .order_by(Post.id.desc()).limit(CATCHUP_BATCH).all())
    if not pending:
        return 0
    cpm_table = get_setting(db, "cpm")
    issues = get_setting(db, "issues").get("list") or None

    topics: dict[int, Topic | None] = {}
    triples: list[tuple[Topic, Post, RawMention]] = []
    for post in pending:
        topic = topics.get(post.topic_id)
        if post.topic_id not in topics:
            topic = db.get(Topic, post.topic_id)
            topics[post.topic_id] = topic
        if topic is None:
            post.enrichment_status = "done"           # orphaned post; stop retrying it
            continue
        m = RawMention(platform=post.platform, native_id=post.native_id,
                       text=post.text, title=post.title,
                       author_name=post.author_name, author_handle=post.author_handle)
        triples.append((topic, post, m))

    if not triples:
        db.commit()
        return 0

    sem = asyncio.Semaphore(ENRICH_CONCURRENCY)
    done = 0
    # Process in chunks, committing after each: a single end-of-run commit loses the
    # entire backlog pass if the worker restarts mid-drain. Skip article extraction on
    # the backlog path — clearing it fast matters more than re-fetching full bodies;
    # fresh posts already get full articles inline on the live path.
    for i in range(0, len(triples), CATCHUP_CHUNK):
        chunk = triples[i:i + CATCHUP_CHUNK]
        results = await asyncio.gather(
            *[_enrich_fetch(t, p, m, issues, sem, extract=False) for t, p, m in chunk],
            return_exceptions=True)
        docs = []
        for (topic, post, _m), res in zip(chunk, results):
            before = post.enrichment_status
            if isinstance(res, Exception):
                post.enrichment_status = "failed_llm"
                continue
            await _finalize(db, topic, post, res, cpm_table)
            if post.enrichment_status == "done" and before != "done":
                done += 1
                docs.append(meili.doc_from_post(post))
        db.commit()
        _index_safe(docs)
    return done


async def backfill_embeddings(db: DbSession, limit: int = 200) -> int:
    """Populate embeddings for posts enriched before we started persisting them, so the
    whole corpus (not just newly-crawled posts) is semantically searchable."""
    if not gateway.available("embed") or not _embedding_enabled(db):
        return 0
    rows = db.execute(text(
        "SELECT id, title, text FROM posts "
        "WHERE embedding IS NULL AND enrichment_status = 'done' "
        "ORDER BY id DESC LIMIT :l"), {"l": limit}).all()
    if not rows:
        return 0
    n = 0
    for i in range(0, len(rows), 32):                 # batch the embed calls
        chunk = rows[i:i + 32]
        texts = [f"{(r.title or '')} {(r.text or '')}"[:1000] for r in chunk]
        vecs = await gateway.embed(texts)
        if not vecs:
            break                                     # provider dry — resume next pass
        for r, v in zip(chunk, vecs):
            _store_embedding(db, r.id, v)
            n += 1
        db.commit()
    return n
