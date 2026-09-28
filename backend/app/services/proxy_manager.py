"""Health-scored proxy rotation with sticky sessions (docs/ALGORITHMS.md §2).

Runtime state in Redis; the proxy list itself lives in Postgres (table `proxies`).
"""
import random
import time

import redis

from ..config import settings

SCORE_START, SCORE_MAX, SCORE_MIN_USABLE = 70, 100, 30

OUTCOME_RULES = {
    "ok":         {"delta": +2,  "cooldown": 0},
    "soft_block": {"delta": -15, "cooldown": 300},    # doubled per consecutive soft block, cap 6h
    "hard_block": {"delta": -40, "cooldown": 43200},
    "net_error":  {"delta": -5,  "cooldown": 60},
}


class NoProxyAvailable(Exception):
    pass


class ProxyManager:
    def __init__(self, r: redis.Redis | None = None):
        self.r = r or redis.Redis.from_url(settings.redis_url, decode_responses=True)

    def _key(self, pid: int) -> str:
        return f"proxy:{pid}"

    def _state(self, pid: int) -> dict:
        st = self.r.hgetall(self._key(pid))
        return {
            "score": float(st.get("score", SCORE_START)),
            "cooldown_until": float(st.get("cooldown_until", 0)),
            "soft_streak": int(st.get("soft_streak", 0)),
            "last_used": float(st.get("last_used", 0)),
        }

    def acquire(self, pool: list[dict], purpose: str = "tier2",
                sticky_key: str | None = None) -> dict | None:
        """pool: [{id, url, tag}] from Postgres. Returns chosen proxy dict or None (direct).

        purpose 'stealth' requires tag=residential; 'tier2' accepts anything.
        sticky_key binds a stealth session permanently to one proxy.
        """
        if sticky_key:
            bound = self.r.get(f"sticky:{sticky_key}")
            if bound is not None:
                p = next((p for p in pool if str(p["id"]) == bound), None)
                if p and self._usable(p["id"]):
                    self._touch(p["id"])
                    return p
                # bound proxy is gone/dead -> the session must be retired with it
                self.r.delete(f"sticky:{sticky_key}")
                raise NoProxyAvailable(f"sticky proxy for {sticky_key} is dead; retire session")

        candidates = []
        now = time.time()
        for p in pool:
            if purpose == "stealth" and p.get("tag") != "residential":
                continue
            st = self._state(p["id"])
            if st["cooldown_until"] > now or st["score"] < SCORE_MIN_USABLE:
                continue
            idle_min = (now - st["last_used"]) / 60 if st["last_used"] else 60
            recency_boost = min(2.0, 1 + idle_min / 30)
            candidates.append((p, (st["score"] ** 2) * recency_boost))

        if not candidates:
            if purpose == "stealth" and not settings.allow_direct_stealth:
                raise NoProxyAvailable("no healthy residential proxy; stealth job refused")
            return None  # direct connection

        total = sum(w for _, w in candidates)
        pick = random.uniform(0, total)
        acc = 0.0
        chosen = candidates[-1][0]
        for p, w in candidates:
            acc += w
            if pick <= acc:
                chosen = p
                break
        if sticky_key:
            self.r.set(f"sticky:{sticky_key}", str(chosen["id"]))
        self._touch(chosen["id"])
        return chosen

    def report(self, pid: int, outcome: str) -> None:
        rule = OUTCOME_RULES.get(outcome, OUTCOME_RULES["net_error"])
        key = self._key(pid)
        st = self._state(pid)
        score = max(0, min(SCORE_MAX, st["score"] + rule["delta"]))
        streak = st["soft_streak"] + 1 if outcome == "soft_block" else 0
        cooldown = rule["cooldown"]
        if outcome == "soft_block":
            cooldown = min(21600, 300 * (2 ** st["soft_streak"]))
        pipe = self.r.pipeline()
        pipe.hset(key, mapping={"score": score, "soft_streak": streak,
                                "cooldown_until": time.time() + cooldown if cooldown else 0})
        pipe.hincrby(key, "blocked" if "block" in outcome else "success", 1)
        pipe.execute()
        if outcome == "hard_block":
            # kill every sticky session bound to this proxy
            for k in self.r.scan_iter("sticky:*"):
                if self.r.get(k) == str(pid):
                    self.r.delete(k)

    def _usable(self, pid: int) -> bool:
        st = self._state(pid)
        return st["cooldown_until"] <= time.time() and st["score"] >= SCORE_MIN_USABLE

    def _touch(self, pid: int) -> None:
        self.r.hset(self._key(pid), "last_used", time.time())

    def stats(self, pool: list[dict]) -> list[dict]:
        out = []
        for p in pool:
            st = self._state(p["id"])
            raw = self.r.hgetall(self._key(p["id"]))
            out.append({**p, "score": st["score"],
                        "cooling": st["cooldown_until"] > time.time(),
                        "success": int(raw.get("success", 0)),
                        "blocked": int(raw.get("blocked", 0))})
        return out


proxy_manager = ProxyManager()
