"""Login brute-force guard: per-IP + per-username fixed-window failure counters in
Redis, with a lockout. Fails OPEN if Redis is unavailable — a cache outage must
never lock every operator out of the product."""
import logging

import redis

from ..config import settings

log = logging.getLogger("loginguard")

WINDOW_S = 900        # 15-minute window
MAX_PER_IP = 25       # generous — a shared office NAT is one IP
MAX_PER_USER = 8      # attempts against a single account before lockout

_client: redis.Redis | None = None


def _r() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, socket_timeout=1,
                                 socket_connect_timeout=1)
    return _client


def _key_ip(ip: str) -> str:
    return f"lg:ip:{ip or 'unknown'}"


def _key_user(username: str) -> str:
    return f"lg:user:{(username or '').lower()}"


def is_locked(ip: str, username: str) -> bool:
    try:
        r = _r()
        ipn = int(r.get(_key_ip(ip)) or 0)
        un = int(r.get(_key_user(username)) or 0)
        return ipn >= MAX_PER_IP or un >= MAX_PER_USER
    except Exception:  # noqa: BLE001 - redis down -> fail open
        return False


def record_failure(ip: str, username: str) -> None:
    try:
        r = _r()
        for key in (_key_ip(ip), _key_user(username)):
            n = r.incr(key)
            if n == 1:
                r.expire(key, WINDOW_S)
    except Exception:  # noqa: BLE001
        pass


def clear(ip: str, username: str) -> None:
    try:
        _r().delete(_key_ip(ip), _key_user(username))
    except Exception:  # noqa: BLE001
        pass
