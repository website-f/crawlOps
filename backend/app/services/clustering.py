"""Incremental story clustering (docs/ALGORITHMS.md §5).

Embeddings via gateway 'embed' group; hashed-TF-IDF fallback keeps clustering
alive with zero AI providers configured.
"""
import hashlib
import math
import re

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Cluster
from .gateway import gateway
from .scoring import NEWS_PLATFORMS

DIM = 256
_WORD = re.compile(r"[a-zà-ɏ0-9]{3,}")


def tfidf_vector(text: str) -> list[float]:
    """Hashed bag-of-words with log damping — crude but provider-free."""
    v = [0.0] * DIM
    words = _WORD.findall(text.lower())[:400]
    for w in words:
        h = int.from_bytes(hashlib.md5(w.encode()).digest()[:4], "big")
        v[h % DIM] += 1.0
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [round(x / norm, 5) for x in v]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


async def vectorize(texts: list[str]) -> list[list[float]]:
    vecs = await gateway.embed([t[:1000] for t in texts])
    if vecs is not None:
        return vecs
    return [tfidf_vector(t) for t in texts]


def assign_cluster(db: Session, topic_id: int, platform: str,
                   vec: list[float], title: str) -> int:
    """Join nearest centroid above threshold, else found a new cluster."""
    threshold = settings.cluster_sim_news if platform in NEWS_PLATFORMS else settings.cluster_sim_social
    best, best_sim = None, 0.0
    for c in db.query(Cluster).filter(Cluster.topic_id == topic_id).all():
        sim = cosine(vec, c.centroid)
        if sim > best_sim:
            best, best_sim = c, sim
    if best is not None and best_sim >= threshold:
        n = best.post_count
        best.centroid = [round((c * n + v) / (n + 1), 5) for c, v in zip(best.centroid, vec)]
        best.post_count = n + 1
        db.flush()
        return best.id
    c = Cluster(topic_id=topic_id, label=title[:180], centroid=vec, post_count=1)
    db.add(c)
    db.flush()
    return c.id
