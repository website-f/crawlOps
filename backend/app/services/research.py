"""Dark-web research warehouse + orchestration (StealthMole-style).

Pipeline for one research run:
  normalize+hash query -> cache check (fresh? serve) -> discover .onion (Ahmia + seeds)
  -> per site: browser-use agent over Tor -> upsert findings (dedup, bump last_seen/scan)
  -> judge threat level -> embed -> link to the query -> write an AI summary.

The warehouse (research_queries / research_findings / research_query_findings) is
deliberately NOT tied to topics, so deleting a topic never loses harvested intel and
re-researching the same query reuses it. See models.py.
"""
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (ResearchFinding, ResearchQuery, ResearchQueryFinding)
from .gateway import GatewayUnavailable, gateway
from .settings_store import get_setting

log = logging.getLogger("research")

FRESH_HOURS_DEFAULT = 24          # a query re-run within this window serves cache
EMBED_DIM = 768
MAX_SITES_CAP = 8                 # per run, to bound Tor + agent cost
AGENT_TIMEOUT = 320


# ---- query identity (StealthMole: search_id = sha256(normalized query)) ----
def normalize_query(q: str) -> str:
    """Lowercased, de-punctuated, unique sorted tokens — so 'Acme Corp' and
    'corp  acme' collapse to the same cache key."""
    toks = sorted(set(re.findall(r"[\w]+", (q or "").lower())))
    return " ".join(toks)


def query_hash(q: str) -> str:
    return hashlib.sha256(normalize_query(q).encode()).hexdigest()


# ---- IOC extraction (works even before the LLM runs) ----
_IOC = {
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "onion": re.compile(r"\b[a-z2-7]{16,56}\.onion\b"),
    "btc": re.compile(r"\b(?:bc1[ac-hj-np-z02-9]{11,71}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b"),
    "eth": re.compile(r"\b0x[a-fA-F0-9]{40}\b"),
    "telegram": re.compile(r"(?:t\.me/|@)[A-Za-z]\w{3,31}\b"),
    "domain": re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b"),
}


def extract_iocs(txt: str) -> list[dict]:
    out, seen = [], set()
    for kind, rx in _IOC.items():
        for m in rx.findall(txt or "")[:40]:
            v = m if isinstance(m, str) else m[0]
            if kind == "domain" and v.endswith(".onion"):
                continue  # already captured as onion
            key = (kind, v.lower())
            if key in seen:
                continue
            seen.add(key)
            out.append({"type": kind, "value": v})
    return out[:60]


# ---- discovery ----
async def discover_onions(terms: str, limit: int) -> list[str]:
    """Ahmia (clearnet index of .onion) for the query + any operator seed list."""
    urls: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True,
                                     headers={"User-Agent": "Mozilla/5.0"}) as c:
            r = await c.get(f"{settings.ahmia_url}/search/", params={"q": terms})
            if r.status_code == 200:
                for h in re.findall(r"[a-z2-7]{20,56}\.onion", r.text):
                    u = f"http://{h}/"
                    if u not in urls:
                        urls.append(u)
    except httpx.HTTPError as e:
        log.warning("ahmia discovery failed: %s", e)
    return urls[:limit]


def seed_urls(db: Session) -> list[str]:
    cfg = get_setting(db, "darkweb") or {}
    return [u.strip() for u in (cfg.get("seeds") or []) if u.strip()]


# ---- warehouse upsert ----
def _finding_hash(url: str, textbody: str) -> str:
    return hashlib.sha256(f"{url}|{(textbody or '')[:500]}".encode()).hexdigest()


def upsert_finding(db: Session, *, source_url: str, title: str, body: str, summary: str,
                   iocs: list, threat: str | None, relevance: int | None,
                   source_type: str = "onion") -> ResearchFinding:
    fh = _finding_hash(source_url, body)
    host = (re.search(r"[a-z2-7]{16,56}\.onion", source_url) or [None])
    host = host.group(0) if hasattr(host, "group") else (source_url.split("/")[2] if "//" in source_url else "")
    now = datetime.now(timezone.utc)
    f = db.query(ResearchFinding).filter(ResearchFinding.finding_hash == fh).first()
    if f:                                   # re-seen: bump stamps, keep first_seen
        f.last_seen = now
        f.last_scan = now
        if summary:
            f.summary = summary[:2000]
        if iocs:
            f.entities = iocs
        if threat:
            f.threat_level = threat
        if relevance is not None:
            f.relevance = relevance
    else:
        f = ResearchFinding(
            finding_hash=fh, source_url=source_url, source_type=source_type,
            source_host=host or "", title=(title or "")[:500], text=(body or "")[:8000],
            summary=(summary or "")[:2000], entities=iocs or [], threat_level=threat,
            relevance=relevance, first_seen=now, last_seen=now, last_scan=now)
        db.add(f)
    db.flush()
    return f


def link_finding(db: Session, query_id: int, finding_id: int, score: float | None) -> None:
    exists = db.get(ResearchQueryFinding, (query_id, finding_id))
    if exists:
        exists.seen_at = datetime.now(timezone.utc)
        if score is not None:
            exists.score = score
    else:
        db.add(ResearchQueryFinding(query_id=query_id, finding_id=finding_id, score=score))


def _store_embedding(db: Session, finding_id: int, vec) -> None:
    if not vec or len(vec) != EMBED_DIM:
        return
    lit = "[" + ",".join(f"{float(x):.6f}" for x in vec) + "]"
    try:
        db.execute(text("UPDATE research_findings SET embedding = CAST(:e AS vector) WHERE id = :i"),
                   {"e": lit, "i": finding_id})
    except Exception:  # noqa: BLE001 - non-pgvector image; skip silently
        db.rollback()


# ---- cache ----
def cached_query(db: Session, qh: str, fresh_hours: int) -> ResearchQuery | None:
    rq = db.query(ResearchQuery).filter(ResearchQuery.query_hash == qh).first()
    if rq and rq.status == "done" and rq.last_run_at:
        if rq.last_run_at >= datetime.now(timezone.utc) - timedelta(hours=fresh_hours):
            return rq
    return rq if (rq and rq.status == "running") else None


def findings_for(db: Session, query_id: int, limit: int = 100) -> list[ResearchFinding]:
    rows = (db.query(ResearchFinding)
            .join(ResearchQueryFinding, ResearchQueryFinding.finding_id == ResearchFinding.id)
            .filter(ResearchQueryFinding.query_id == query_id)
            .order_by(ResearchFinding.last_seen.desc()).limit(limit).all())
    return rows


# ---- threat classification (one small judge call per finding) ----
async def _classify(query: str, body: str) -> tuple[str | None, int | None]:
    try:
        data = await gateway.chat_json("judge", [{"role": "user", "content":
            f"Dark-web page excerpt below. For the monitoring subject '{query}', reply ONLY "
            f'JSON: {{"threat_level":"low|medium|high|critical","relevance":0-100}}.\n\n'
            f"{(body or '')[:2500]}"}], max_tokens=200)
        tl = str(data.get("threat_level", "")).lower()
        tl = tl if tl in ("low", "medium", "high", "critical") else None
        rel = data.get("relevance")
        rel = max(0, min(100, int(rel))) if isinstance(rel, (int, float)) else None
        return tl, rel
    except (GatewayUnavailable, ValueError, KeyError):
        return None, None


def _agent_llm() -> dict | None:
    """DeepSeek (or whatever is set for the 'agent' task) creds for browser-use."""
    provs = gateway._providers_for("agent")
    if not provs:
        return None
    p = provs[0]
    return {"base_url": p["base_url"], "api_key": p["key"], "model": p["model"]}


async def _run_agent(url: str, query: str, llm: dict, max_steps: int) -> dict:
    async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as c:
        r = await c.post(f"{settings.darkweb_agent_url}/research",
                         json={"url": url, "query": query, "llm": llm, "max_steps": max_steps})
        r.raise_for_status()
        return r.json()


async def run_research(db: Session, query_text: str, *, max_sites: int = 5,
                       max_steps: int = 8, force: bool = False,
                       fresh_hours: int = FRESH_HOURS_DEFAULT) -> dict:
    """Orchestrate one research run, honouring the cache unless force=True."""
    qh = query_hash(query_text)
    rq = db.query(ResearchQuery).filter(ResearchQuery.query_hash == qh).first()

    if rq and not force:
        hit = cached_query(db, qh, fresh_hours)
        if hit:
            fs = findings_for(db, hit.id)
            return {"cached": True, "status": hit.status, "query_id": hit.id,
                    "summary": hit.summary, "finding_count": len(fs)}

    now = datetime.now(timezone.utc)
    if rq is None:
        rq = ResearchQuery(query_hash=qh, query_text=query_text, algorithm="darkweb",
                           status="running", first_run_at=now, last_run_at=now, run_count=0)
        db.add(rq)
        db.flush()
    rq.status = "running"
    rq.last_run_at = now
    rq.run_count = (rq.run_count or 0) + 1
    rq.error = None
    db.commit()

    llm = _agent_llm()
    if not llm:
        rq.status = "error"
        rq.error = "no AI provider configured for the 'agent' task (set one in AI Engine)"
        db.commit()
        return {"cached": False, "status": "error", "error": rq.error, "query_id": rq.id}

    try:
        found = await discover_onions(query_text, max_sites * 2)
        sites = (seed_urls(db) + found)[:min(max_sites, MAX_SITES_CAP)]
        n_findings = 0
        for url in sites:
            try:
                res = await _run_agent(url, query_text, llm, max_steps)
            except httpx.HTTPError as e:
                log.warning("agent call failed for %s: %s", url[:60], e)
                continue
            if not res.get("ok"):
                continue
            agent_findings = res.get("findings") or []
            # if the agent found nothing structured but deemed the site relevant,
            # keep a single summary-level finding so the site is still on the radar
            if not agent_findings and res.get("relevant"):
                agent_findings = [{"title": "", "text": res.get("summary", ""),
                                   "url": url, "iocs": []}]
            for af in agent_findings:
                body = (af.get("text") or "").strip()
                if len(body) < 8:
                    continue
                iocs = extract_iocs(body)
                for extra in (af.get("iocs") or []):
                    if extra and {"type": "reported", "value": str(extra)[:120]} not in iocs:
                        iocs.append({"type": "reported", "value": str(extra)[:120]})
                threat, relevance = await _classify(query_text, body)
                f = upsert_finding(db, source_url=af.get("url") or url,
                                   title=af.get("title", ""), body=body,
                                   summary=res.get("summary", ""), iocs=iocs,
                                   threat=threat, relevance=relevance)
                link_finding(db, rq.id, f.id, float(relevance) if relevance else None)
                try:
                    vecs = await gateway.embed([f"{f.title} {body}"[:1000]])
                    if vecs:
                        _store_embedding(db, f.id, vecs[0])
                except Exception:  # noqa: BLE001
                    pass
                n_findings += 1
            db.commit()

        fs = findings_for(db, rq.id)
        rq.finding_count = len(fs)
        rq.summary = await _summarize(query_text, fs)
        rq.status = "done"
        rq.last_run_at = datetime.now(timezone.utc)
        db.commit()
        return {"cached": False, "status": "done", "query_id": rq.id,
                "summary": rq.summary, "finding_count": rq.finding_count,
                "sites_checked": len(sites)}
    except Exception as e:  # noqa: BLE001
        log.exception("research run failed")
        rq.status = "error"
        rq.error = str(e)[:500]
        db.commit()
        return {"cached": False, "status": "error", "error": rq.error, "query_id": rq.id}


async def _summarize(query: str, findings: list[ResearchFinding]) -> str:
    if not findings:
        return "No dark-web findings for this query in the sources checked."
    joined = "\n".join(f"- {f.source_host}: {(f.summary or f.text)[:200]}" for f in findings[:15])
    try:
        out, _ = await gateway.chat("agent", [{"role": "user", "content":
            f"Write a 3-4 sentence threat-intel brief for the subject '{query}' from these "
            f"dark-web findings. Be factual, note any credentials/leaks/mentions.\n\n{joined}"}],
            max_tokens=400)
        return (out or "").strip()[:2000]
    except GatewayUnavailable:
        return f"{len(findings)} finding(s) harvested; AI summary unavailable."
