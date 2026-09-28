"""Public media proxy — served without auth so browser <img>/<video> tags work
(they cannot attach an Authorization header). Only serves cached objects by key."""
from fastapi import APIRouter, HTTPException, Response

from ..services.media_cache import stream_object

router = APIRouter(prefix="/api", tags=["media"])


@router.get("/media/{key}")
def media(key: str):
    if "/" in key or ".." in key:
        raise HTTPException(400)
    try:
        data, ctype = stream_object(key)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(404, "media not cached") from e
    return Response(content=data, media_type=ctype,
                    headers={"Cache-Control": "public, max-age=604800"})
