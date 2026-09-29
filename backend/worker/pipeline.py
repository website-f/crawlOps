"""Central pipeline: fetch -> boolean filter -> dedup -> media cache -> judge ->
score -> geo -> cluster -> store -> index (docs/ARCHITECTURE.md)."""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.models import FetchRun, Post, PostMetric, Source, SuppressedAuthor, Topic
from app.services import meili
from app.services.boolean_query import compile_query
from app.services.clustering import assign_cluster, vectorize
from app.services.dedup import identity_key, near_duplicate, simhash64
from app.services.gateway import GatewayUnavailable, gateway
from app.services.geocode import geocode
from app.services.countries import country_from_domain, country_from_url, country_name
from app.services.media_cache import cache_media
from app.services.scoring import estimate_emv, estimate_reach
from app.services.settings_store import get_setting

from .connectors import build
from .connectors.base import ROUND_DELAY_S, RawMention
from .prompts import build_judge_messages
from .stealth.camofox_client import LoginRequired, SelectorBroken

log = logging.getLogger("pipeline")

EMOTIONS = {"joy", "trust", "anticipation", "surprise", "fear", "anger",
            "sadness", "disgust", "neutral"}


def _clamp_int(v, lo: int = 0, hi: int = 100) -> int | None:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return None


async def run_topic(db: DbSession, topic: Topic) -> dict:
    cq = compile_query(topic.query or topic.name)
    sources = db.query(Source).filter(Source.enabled.is_(True)).all()
    if topic.platforms:
        sources = [s for s in sources if s.platform in topic.platforms]

    hidden_authors = {(s.platform, s.author_key) for s in
                      db.query(SuppressedAuthor).filter(SuppressedAuthor.mode == "hide").all()}
    cpm_table = get_setting(db, "cpm")
    issues = get_setting(db, "issues").get("list") or None

    totals = {"found": 0, "inserted": 0}
    for source in sources:
        run = FetchRun(topic_id=topic.id, source_id=source.id)
        db.add(run)
        db.commit()
        try:
            connector = build(source.connector, db, source.config)
            if connector is None or not connector.enabled():
                source.status = "dormant"
                source.last_error = connector.disabled_reason() if connector else "not implemented"
                db.commit()
                continue
            try:
                mentions = await connector.fetch(cq)
            except LoginRequired as e:
                # not an error — the platform needs logged-in cookies for this session
                source.status = "dormant"
                source.last_error = str(e)
                run.error = "login required"
                db.commit()
                continue
            except SelectorBroken as e:
                mentions = await _heal_and_retry(db, source, e)
            run.found = len(mentions)
            inserted = await _ingest(db, topic, cq, mentions, hidden_authors, cpm_table, issues)
            run.inserted = inserted
            totals["found"] += run.found
            totals["inserted"] += inserted
            source.status = "ok"
            source.last_error = None
        except Exception as e:  # noqa: BLE001 — one source failing never kills the cycle
            log.warning("source %s failed: %s", source.connector, e)
            source.status = "error"
            source.last_error = str(e)[:500]
            run.error = str(e)[:500]
        finally:
            source.last_run_at = datetime.now(timezone.utc)
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        await asyncio.sleep(ROUND_DELAY_S)

    topic.last_run_at = datetime.now(timezone.utc)
    db.commit()
    return totals


async def _heal_and_retry(db: DbSession, source: Source, err: SelectorBroken) -> list[RawMention]:
    log.info("%s: heuristic empty — invoking AI agent on snapshot", source.platform)
    from .stealth.agent_fallback import agent_extract
    return await agent_extract(db, source.platform, getattr(err, "snapshot", "") or "")


async def _ingest(db: DbSession, topic: Topic, cq, mentions: list[RawMention],
                  hidden_authors: set, cpm_table: dict | None = None,
                  issues: list | None = None) -> int:
    # near-dup candidates: recent simhashes for this topic
    recent = (db.query(Post.simhash, Post.dup_group)
              .filter(Post.topic_id == topic.id, Post.simhash.isnot(None))
              .order_by(Post.id.desc()).limit(2000).all())

    inserted = 0
    docs = []
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
        )
        # deterministic geo (keyless, Radar-style): source-declared country (GDELT)
        # first, then domain/url ccTLD. AI may refine with an inferred location later.
        cc = (m.country or None) or country_from_domain(post.domain) or country_from_url(post.url)
        if cc:
            post.country, post.country_name = cc, country_name(cc)
        await _enrich(db, topic, post, m, cpm_table, issues)
        db.add(post)
        db.flush()
        docs.append(meili.doc_from_post(post))
        inserted += 1
        if len(docs) >= 10:                          # progressive commit: feed fills live
            db.commit()
            _index_safe(docs)
            docs = []

    db.commit()
    _index_safe(docs)
    return inserted


def _index_safe(docs: list[dict]) -> None:
    if not docs:
        return
    try:
        meili.index_posts(docs)
    except Exception:  # noqa: BLE001
        log.warning("meilisearch indexing failed; posts remain in Postgres", exc_info=True)


async def _enrich(db: DbSession, topic: Topic, post: Post, m: RawMention,
                  cpm_table: dict | None = None, issues: list | None = None) -> None:
    """LLM judge + deterministic scoring. Degrades to 'pending' when rotation is dry."""
    try:
        data = await gateway.chat_json(
            "judge",
            build_judge_messages(topic.criteria, m.platform,
                                 m.author_name or m.author_handle, m.title, m.text, issues),
            max_tokens=400)
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
        post.enrichment_status = "done"
        threshold = topic.threshold or settings.judge_threshold_default
        if not data.get("relevant", True) or post.relevance < threshold:
            post.is_hidden = True                     # stored + auditable, not shown
    except GatewayUnavailable:
        post.enrichment_status = "pending"            # catch-up job re-runs it
    except Exception:  # noqa: BLE001
        log.warning("judge failed for %s", post.identity_key, exc_info=True)
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

    if not post.is_hidden:
        try:
            vec = (await vectorize([f"{post.title} {post.text}"[:1000]]))[0]
            post.cluster_id = assign_cluster(db, topic.id, post.platform, vec,
                                             post.title or post.text[:120])
        except Exception:  # noqa: BLE001
            log.warning("clustering skipped", exc_info=True)


async def catchup_enrichment(db: DbSession) -> int:
    """Re-run judge for posts deferred while every provider was cooling."""
    pending = (db.query(Post)
               .filter(Post.enrichment_status.in_(["pending", "failed_llm"]))
               .order_by(Post.id.desc()).limit(200).all())
    if not pending:
        return 0
    cpm_table = get_setting(db, "cpm")
    issues = get_setting(db, "issues").get("list") or None
    done = 0
    for post in pending:
        topic = db.get(Topic, post.topic_id)
        if topic is None:
            post.enrichment_status = "done"
            continue
        m = RawMention(platform=post.platform, native_id=post.native_id,
                       text=post.text, title=post.title,
                       author_name=post.author_name, author_handle=post.author_handle)
        before = post.enrichment_status
        await _enrich(db, topic, post, m, cpm_table, issues)
        if post.enrichment_status == "done" and before != "done":
            done += 1
            try:
                meili.index_posts([meili.doc_from_post(post)])
            except Exception:  # noqa: BLE001
                pass
        elif post.enrichment_status == "pending":
            break  # rotation still dry — stop burning the loop
    db.commit()
    return done
