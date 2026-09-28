"""Nightly maintenance (docs/ALGORITHMS.md §5): merge drifted clusters, polish
cluster labels via the AI gateway, purge posts past the retention window."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Cluster, Post, PostMetric, Topic
from app.services import meili
from app.services.clustering import cosine
from app.services.gateway import GatewayUnavailable, gateway
from app.services.settings_store import get_setting

from .prompts import CLUSTER_LABEL_PROMPT

log = logging.getLogger("nightly")
MERGE_THRESHOLD = 0.85


def merge_clusters(db: Session, topic_id: int) -> int:
    """Greedy agglomerative merge of near-identical centroids (fixes drift)."""
    clusters = db.query(Cluster).filter(Cluster.topic_id == topic_id).all()
    merged = 0
    for i, a in enumerate(clusters):
        if a.post_count == 0:
            continue
        for b in clusters[i + 1:]:
            if b.post_count == 0:
                continue
            if cosine(a.centroid, b.centroid) >= MERGE_THRESHOLD:
                # fold b into a
                db.query(Post).filter(Post.cluster_id == b.id).update({Post.cluster_id: a.id})
                n = a.post_count + b.post_count
                a.centroid = [round((x * a.post_count + y * b.post_count) / n, 5)
                              for x, y in zip(a.centroid, b.centroid)]
                a.post_count = n
                b.post_count = 0
                merged += 1
    # drop emptied clusters
    db.query(Cluster).filter(Cluster.topic_id == topic_id, Cluster.post_count == 0).delete()
    db.commit()
    return merged


async def polish_labels(db: Session, topic_id: int, limit: int = 10) -> int:
    """Give the biggest clusters a human-readable label via the enrich model group."""
    clusters = (db.query(Cluster)
                .filter(Cluster.topic_id == topic_id, Cluster.post_count >= 3)
                .order_by(Cluster.post_count.desc()).limit(limit).all())
    done = 0
    for c in clusters:
        titles = [p.title or p.text[:100] for p in
                  db.query(Post).filter(Post.cluster_id == c.id).limit(6).all()]
        if not titles:
            continue
        try:
            data = await gateway.chat_json(
                "enrich",
                [{"role": "user", "content": CLUSTER_LABEL_PROMPT.format(posts="\n".join(f"- {t}" for t in titles))}],
                max_tokens=60)
            label = (data.get("label") or "").strip()
            if label:
                c.label = label[:180]
                done += 1
        except GatewayUnavailable:
            break  # rotation dry — try again tomorrow
        except Exception:  # noqa: BLE001
            continue
    db.commit()
    return done


def purge_retention(db: Session) -> int:
    days = int(get_setting(db, "pipeline").get("retention_days", 90))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    old = db.query(Post.id).filter(Post.posted_at < cutoff).all()
    ids = [r[0] for r in old]
    if not ids:
        return 0
    for chunk_start in range(0, len(ids), 500):
        chunk = ids[chunk_start:chunk_start + 500]
        db.query(PostMetric).filter(PostMetric.post_id.in_(chunk)).delete(synchronize_session=False)
        db.query(Post).filter(Post.id.in_(chunk)).delete(synchronize_session=False)
        db.commit()
        try:
            meili.client().index(meili.INDEX).delete_documents(chunk)
        except Exception:  # noqa: BLE001
            pass
    log.info("retention purge removed %s posts older than %sd", len(ids), days)
    return len(ids)


def recover_sessions(db: Session) -> int:
    """Daily: reset per-session usage and revive rested sessions (needs_reauth stays)."""
    from app.models import StealthSession
    rows = db.query(StealthSession).all()
    revived = 0
    for s in rows:
        s.daily_used = 0
        if s.status == "resting":
            s.status = "ready"
            revived += 1
    db.commit()
    return revived


async def run_nightly(db: Session) -> dict:
    stats = {"purged": purge_retention(db), "merged": 0, "labeled": 0,
             "sessions_revived": recover_sessions(db)}
    for topic in db.query(Topic).all():
        stats["merged"] += merge_clusters(db, topic.id)
        stats["labeled"] += await polish_labels(db, topic.id)
    # refresh cluster counts (defensive, after purge)
    for c in db.query(Cluster).all():
        c.post_count = db.query(func.count()).filter(Post.cluster_id == c.id).scalar() or 0
    db.query(Cluster).filter(Cluster.post_count == 0).delete()
    db.commit()
    log.info("nightly done: %s", stats)
    return stats
