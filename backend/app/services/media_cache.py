"""Media cache — download post images/videos into MinIO so cards keep rendering
after the platform's signed CDN URLs expire.

Storage is kept minimal on purpose:
  * images are downscaled to <=1280px and re-encoded as WebP q80 (typically 5-15x
    smaller than the original PNG/JPEG),
  * videos are NOT stored — we keep only a compressed poster frame and let playback
    fall back to the source URL / an outbound link (a monitoring feed shows a
    thumbnail, it doesn't need to host the whole clip),
  * YouTube is skipped entirely — the card embeds the player by id."""
import asyncio
import hashlib
import io
import logging
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import httpx
from minio import Minio

from ..config import settings
from .ssrf import BlockedURL, guard_url

log = logging.getLogger("media")
BUCKET = "media"
MAX_BYTES = 60 * 1024 * 1024        # never download anything bigger than this
VIDEO_POSTER_CAP = 24 * 1024 * 1024  # only pull a video this big just to make a poster
IMG_MAX_DIM = 1280                  # downscale longest side to this
IMG_QUALITY = 80

_client: Minio | None = None


def _compress_image(body: bytes) -> tuple[bytes, str] | None:
    """Downscale + re-encode to WebP. Returns (bytes, content_type) or None on failure."""
    try:
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(body))
        im = ImageOps.exif_transpose(im)              # honor camera rotation
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.mode else "RGB")
        im.thumbnail((IMG_MAX_DIM, IMG_MAX_DIM))       # in-place, keeps aspect ratio
        buf = io.BytesIO()
        im.save(buf, format="WEBP", quality=IMG_QUALITY, method=4)
        return buf.getvalue(), "image/webp"
    except Exception:  # noqa: BLE001
        return None


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
    # YouTube isn't a file — the card embeds the player by id. Never download it.
    if m.get("youtube_id"):
        return m
    url = m.get("src_url", "")
    if not url:
        return m
    try:
        guard_url(url)   # block internal/loopback/link-local media URLs (SSRF)
    except BlockedURL:
        log.warning("media cache blocked non-public url: %s", url[:120])
        return m
    is_video = m.get("kind") == "video"
    key = hashlib.sha1(url.encode()).hexdigest()
    async with httpx.AsyncClient(timeout=45, follow_redirects=False) as http:
        r = await http.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CrawlOps/1.0)"})
        # one manual redirect hop, re-checked, so a 302 can't jump to an internal host
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
            nxt = urljoin(url, r.headers["location"])
            guard_url(nxt)
            r = await http.get(nxt, headers={"User-Agent": "Mozilla/5.0 (compatible; CrawlOps/1.0)"})
        r.raise_for_status()
        body = r.content
    if len(body) > MAX_BYTES:
        return m

    if is_video:
        # Store only a small poster; keep src_url so the card can still play/link out.
        if len(body) > VIDEO_POSTER_CAP:
            return m                                   # too big to bother posterizing
        frame = await asyncio.to_thread(_poster_frame, body)
        if frame:
            comp = await asyncio.to_thread(_compress_image, frame) or (frame, "image/jpeg")
            tkey = f"{key}.poster.webp"
            await asyncio.to_thread(client().put_object, BUCKET, tkey,
                                    io.BytesIO(comp[0]), len(comp[0]), content_type=comp[1])
            m["thumb_key"] = tkey
        return m

    # image: downscale + WebP re-encode (falls back to the original bytes on failure)
    comp = await asyncio.to_thread(_compress_image, body)
    data, ctype, ext = (comp[0], comp[1], "webp") if comp else (
        body, r.headers.get("content-type", "application/octet-stream").split(";")[0], "img")
    obj = f"{key}.{ext}"
    await asyncio.to_thread(client().put_object, BUCKET, obj,
                            io.BytesIO(data), len(data), content_type=ctype)
    m["cache_key"] = obj
    return m


def _media_keys(posts_media) -> list[str]:
    """Collect every stored object key referenced by a list of post.media lists."""
    keys: list[str] = []
    for media in posts_media:
        for m in (media or []):
            if isinstance(m, dict):
                if m.get("cache_key"):
                    keys.append(m["cache_key"])
                if m.get("thumb_key"):
                    keys.append(m["thumb_key"])
    return keys


def delete_media_objects(keys: list[str]) -> int:
    """Remove cached objects from the bucket (best-effort). Returns count attempted."""
    if not keys:
        return 0
    try:
        from minio.deleteobjects import DeleteObject
        errs = client().remove_objects(BUCKET, (DeleteObject(k) for k in set(keys)))
        list(errs)                                     # force the lazy generator to run
    except Exception:  # noqa: BLE001
        log.warning("media cleanup failed for %s keys", len(keys), exc_info=True)
    return len(set(keys))


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
