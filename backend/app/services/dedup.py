"""Exact-identity + SimHash near-duplicate detection (see docs/ALGORITHMS.md §4)."""
import hashlib
import re

_WORD = re.compile(r"[a-z0-9À-ɏ฀-๿一-鿿]+")
_NOISE = re.compile(r"https?://\S+|@\w+|#")


def identity_key(platform: str, native_id: str) -> str:
    return hashlib.sha1(f"{platform}:{native_id}".encode()).hexdigest()


def _shingles(text: str, n: int = 3):
    text = _NOISE.sub(" ", text.lower())
    words = _WORD.findall(text)
    if len(words) < n:
        return [" ".join(words)] if words else []
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


def simhash64(text: str) -> int:
    v = [0] * 64
    for sh in _shingles(text):
        h = int.from_bytes(hashlib.md5(sh.encode()).digest()[:8], "big")
        for i in range(64):
            v[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(64):
        if v[i] > 0:
            out |= 1 << i
    # store as signed 64-bit for Postgres BigInteger
    return out - (1 << 64) if out >= (1 << 63) else out


def hamming(a: int, b: int) -> int:
    return bin((a & 0xFFFFFFFFFFFFFFFF) ^ (b & 0xFFFFFFFFFFFFFFFF)).count("1")


def near_duplicate(a: int, b: int, max_distance: int = 6) -> bool:
    return hamming(a, b) <= max_distance
