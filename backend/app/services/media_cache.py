"""Media cache — download post images/videos into MinIO so cards keep rendering
after the platform's signed CDN URLs expire. Video gets an ffmpeg poster frame."""
import hashlib
import io
import logging
import subprocess
import tempfile
from pathlib import Path

import httpx
from minio import Minio

from ..config import settings

log = logging.getLogger("media")
BUCKET = "media"
MAX_BYTES = 60 * 1024 * 1024  # skip anything bigger than 60MB

_client: Minio | None = None


def client() -> Minio:
    global _client
    if _client is None:
        endpoint = settings.minio_url.replace("http://", "").replace("https://", "")
        _client = Minio(endpoint, access_key=settings.minio_root_user,
                        secret_key=settings.minio_root_password,
                        secure=settings.minio_url.startswith("https"))
        if not _client.bucket_exists(BUCKET):
            _client.make_bucket(BUCKET)
    return _client


async def cache_media(items: list[dict]) -> list[dict]:
    """items: [{kind: image|video, src_url, ...}] -> adds cache_key (+ thumb_key for video)."""
    out = []
    for m in items[:6]:
        try:
            cached = await _cache_one(dict(m))
        except Exception:  # noqa: BLE001
            log.warning("media cache failed: %s", m.get("src_url", "")[:120])
            cached = dict(m)  # keep original URL as fallback
        out.append(cached)
    return out


async def _cache_one(m: dict) -> dict:
    url = m.get("src_url", "")
    if not url:
        return m
    key = hashlib.sha1(url.encode()).hexdigest()
    ext = "mp4" if m.get("kind") == "video" else "img"
    obj = f"{key}.{ext}"
    async with httpx.AsyncClient(timeout=45, follow_redirects=True) as http:
        r = await http.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CrawlOps/1.0)"})
        r.raise_for_status()
        body = r.content
    if len(body) > MAX_BYTES:
        return m
    ctype = r.headers.get("content-type", "application/octet-stream").split(";")[0]
    client().put_object(BUCKET, obj, io.BytesIO(body), len(body), content_type=ctype)
    m["cache_key"] = obj
    if m.get("kind") == "video":
        thumb = _poster_frame(body)
        if thumb:
            tkey = f"{key}.poster.jpg"
            client().put_object(BUCKET, tkey, io.BytesIO(thumb), len(thumb), content_type="image/jpeg")
            m["thumb_key"] = tkey
    return m


def _poster_frame(video_bytes: bytes) -> bytes | None:
    try:
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "in.mp4"
            dst = Path(td) / "out.jpg"
            src.write_bytes(video_bytes)
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(src), "-vframes", "1", "-q:v", "4", str(dst)],
                capture_output=True, timeout=60, check=True)
            return dst.read_bytes()
    except Exception:  # noqa: BLE001
        return None


def stream_object(key: str):
    """Used by the API media proxy endpoint."""
    resp = client().get_object(BUCKET, key)
    try:
        content_type = resp.headers.get("Content-Type", "application/octet-stream")
        data = resp.read()
    finally:
        resp.close()
        resp.release_conn()
    return data, content_type
