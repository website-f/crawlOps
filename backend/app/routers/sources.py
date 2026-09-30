from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import FetchRun, Proxy, Source, StealthSession
from ..services import credentials as creds
from ..services import extension_pack
from ..services.credentials import decrypt_proxy, encrypt_proxy
from ..services.proxy_manager import proxy_manager

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("/extension.zip")
def download_extension():
    """One-click download of the browser-extension folder as a zip the operator
    unzips and loads unpacked (chrome://extensions -> Developer mode)."""
    return Response(
        content=extension_pack.build_zip(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=crawlops-connector.zip"},
    )


STEALTH_CONNECTORS = {"facebook_stealth", "instagram_stealth", "tiktok_stealth",
                      "x_stealth", "threads_stealth"}

# how each connector is connected + a one-line blurb — drives the Sources UI so the
# operator immediately sees whether a source needs a login, an API key, or nothing.
_METHODS = {
    "threads": ("api", "Official Threads API — needs a Meta token (keyword search)."),
    "youtube": ("api", "YouTube Data API key (free Google Cloud key)."),
    "factcheck": ("api", "Google Fact Check API key (free)."),
    "podcastindex": ("api", "Podcast Index API key + secret (free)."),
    "places": ("api", "Google Places API key (paid)."),
    "appstore": ("config", "App Store app IDs — no key needed."),
    "rss": ("config", "Add RSS/Atom feed URLs or RSSHub routes."),
    "telegram": ("config", "Public channel usernames — no login needed."),
    "tiktok_watch": ("watchlist", "Follow public TikTok accounts (free, via RSSHub)."),
    "threads_watch": ("watchlist", "Follow public Threads accounts (free, via RSSHub)."),
    "youtube_watch": ("watchlist", "Follow YouTube channels (free, no API key)."),
    "facebook_stealth": ("login", "Log in with an account — no public API for search."),
    "instagram_stealth": ("login", "Log in with an account — no public API for search."),
    "tiktok_stealth": ("login", "Log in with an account (or use the free watchlist)."),
    "x_stealth": ("login", "Log in with an account (X public API is paid)."),
    "threads_stealth": ("login", "Log in with an account, or use the Threads API token."),
}


def _method(connector: str) -> tuple[str, str]:
    return _METHODS.get(connector, ("keyless", "Public source — nothing to connect."))


def _account_state(platform: str, sessions: list) -> dict:
    """What the operator actually needs to know about a stealth platform: is an
    account connected, and is it usable right now? `sources.status` alone can't say
    this — a connected-but-expired account and no account at all both end up
    'dormant' with a 'needs login' message, which is what made Facebook look
    unconnected when it wasn't."""
    mine = [x for x in sessions if x.platform == platform]
    with_cookies = [x for x in mine if x.cookie_ref]
    if not with_cookies:
        return {"connected": False, "state": "none",
                "detail": "No account connected — public browsing only, which these "
                          "platforms wall off. Log in here to crawl as a real account."}
    live = [x for x in with_cookies if x.status == "ready"]
    if live:
        s = live[0]
        return {"connected": True, "state": "ready", "label": s.label,
                "detail": f"Connected as “{s.label}” — {s.daily_used}/{s.daily_cap} fetches used today."}
    reauth = [x for x in with_cookies if x.status == "needs_reauth"]
    if reauth:
        s = reauth[0]
        return {"connected": True, "state": "needs_reauth", "label": s.label,
                "detail": f"“{s.label}” is connected but its cookies expired — log in "
                          f"again to resume. Until then this platform is crawled logged-out."}
    s = with_cookies[0]
    return {"connected": True, "state": "resting", "label": s.label,
            "detail": f"“{s.label}” hit its daily cap ({s.daily_used}/{s.daily_cap}); "
                      f"the nightly job resets it."}


@router.get("")
def list_sources(db: Session = Depends(get_db)):
    sessions = db.query(StealthSession).all()
    out = []
    for s in db.query(Source).order_by(Source.tier, Source.platform).all():
        method, blurb = _method(s.connector)
        row = {"id": s.id, "platform": s.platform, "connector": s.connector, "tier": s.tier,
               "enabled": s.enabled, "status": s.status, "method": method, "blurb": blurb,
               "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
               "last_error": (s.last_error or "")[:300],
               "needs_credentials": creds.needs_credentials(s.connector),
               "missing": creds.missing_required(s),
               "configured": creds.is_configured(s)}
        if s.connector in STEALTH_CONNECTORS:
            row["account"] = _account_state(s.platform, sessions)
        out.append(row)
    return out


@router.get("/{source_id}/credentials")
def get_credentials(source_id: int, db: Session = Depends(get_db)):
    """The spec plus whether each field is set. Secrets are never returned in plain."""
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(404)
    return {"connector": s.connector, "platform": s.platform,
            "fields": creds.status_fields(s), "missing": creds.missing_required(s)}


class CredentialsIn(BaseModel):
    values: dict


@router.put("/{source_id}/credentials")
def set_credentials(source_id: int, body: CredentialsIn, db: Session = Depends(get_db)):
    """Secrets go to the encrypted blob, everything else to plain config. A blank
    secret means 'keep what is stored', so the form can submit masked fields."""
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(404)
    spec = {f["key"]: f for f in creds.spec_for(s.connector)}
    if not spec:
        raise HTTPException(400, f"{s.connector} takes no credentials")
    cfg = dict(s.config or {})
    for key, raw in body.values.items():
        f = spec.get(key)
        if not f or f["type"] == "secret":
            continue
        if f["type"] == "list":
            items = raw if isinstance(raw, list) else str(raw or "").splitlines()
            cfg[key] = [x.strip() for x in items if str(x).strip()]
        else:
            cfg[key] = str(raw or "").strip()
    s.config = cfg
    creds.write_secrets(s, {k: v for k, v in body.values.items()
                            if spec.get(k, {}).get("type") == "secret"})
    if creds.is_configured(s):
        s.enabled = True          # connecting a source is the act of turning it on
        if s.status == "dormant":
            s.status, s.last_error = "idle", None
    db.commit()
    return {"id": s.id, "enabled": s.enabled, "fields": creds.status_fields(s),
            "missing": creds.missing_required(s)}


@router.delete("/{source_id}/credentials")
def clear_credentials(source_id: int, db: Session = Depends(get_db)):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(404)
    creds.clear_secrets(s)
    cfg = dict(s.config or {})
    for f in creds.spec_for(s.connector):
        cfg.pop(f["key"], None)
    s.config = cfg
    s.status, s.last_error = "dormant", "Disconnected — add credentials to re-enable"
    db.commit()
    return {"id": s.id, "fields": creds.status_fields(s)}


@router.post("/{source_id}/toggle")
def toggle(source_id: int, db: Session = Depends(get_db)):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(404)
    s.enabled = not s.enabled
    db.commit()
    return {"id": s.id, "enabled": s.enabled}


class ConfigIn(BaseModel):
    config: dict


@router.get("/{source_id}/config")
def get_config(source_id: int, db: Session = Depends(get_db)):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(404)
    return {"connector": s.connector, "config": s.config}


@router.put("/{source_id}/config")
def set_config(source_id: int, body: ConfigIn, db: Session = Depends(get_db)):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(404)
    s.config = body.config
    db.commit()
    return {"id": s.id, "config": s.config}


@router.get("/runs")
def recent_runs(limit: int = 50, db: Session = Depends(get_db)):
    runs = db.query(FetchRun).order_by(FetchRun.id.desc()).limit(min(limit, 200)).all()
    return [{"id": r.id, "topic_id": r.topic_id, "source_id": r.source_id,
             "started_at": r.started_at.isoformat(), "found": r.found,
             "inserted": r.inserted, "error": (r.error or "")[:200]} for r in runs]


# ---- proxies ----

class ProxyIn(BaseModel):
    url: str
    tag: str = "datacenter"   # residential | datacenter
    country: str = ""


@router.get("/proxies")
def list_proxies(db: Session = Depends(get_db)):
    pool = [{"id": p.id, "url": decrypt_proxy(p.url).split("@")[-1], "tag": p.tag,
             "country": p.country, "active": p.active}
            for p in db.query(Proxy).all()]  # strip credentials before returning
    return proxy_manager.stats(pool)


@router.post("/proxies")
def add_proxy(body: ProxyIn, db: Session = Depends(get_db)):
    if body.tag not in ("residential", "datacenter"):
        raise HTTPException(400, "tag must be residential|datacenter")
    p = Proxy(url=encrypt_proxy(body.url), tag=body.tag, country=body.country)
    db.add(p)
    db.commit()
    return {"id": p.id}


@router.delete("/proxies/{proxy_id}")
def delete_proxy(proxy_id: int, db: Session = Depends(get_db)):
    p = db.get(Proxy, proxy_id)
    if p:
        db.delete(p)
        db.commit()
    return {"ok": True}


@router.get("/stealth-sessions")
def stealth_sessions(db: Session = Depends(get_db)):
    return [{"id": s.id, "platform": s.platform, "label": s.label, "status": s.status,
             "has_cookies": bool(s.cookie_ref),
             "daily_used": s.daily_used, "daily_cap": s.daily_cap,
             "last_used_at": s.last_used_at.isoformat() if s.last_used_at else None}
            for s in db.query(StealthSession).all()]


class SessionIn(BaseModel):
    platform: str
    label: str = ""
    daily_cap: int = 40
    proxy_id: int | None = None


@router.post("/stealth-sessions")
def create_session(body: SessionIn, db: Session = Depends(get_db)):
    s = StealthSession(platform=body.platform, label=body.label,
                       daily_cap=body.daily_cap, proxy_id=body.proxy_id, status="ready")
    db.add(s)
    db.commit()
    return {"id": s.id}


class CookieIn(BaseModel):
    cookies: list[dict]  # [{name, value, domain, path?}]


def _push_cookies(user_id: str, cookies: list[dict]) -> tuple[bool, str]:
    """Open the session tab, then import cookies (gated by CAMOFOX_API_KEY)."""
    import httpx
    base = settings.camofox_url.rstrip("/")
    try:
        httpx.post(f"{base}/tabs",
                   json={"url": "about:blank", "userId": user_id, "sessionKey": user_id},
                   timeout=40)
        r = httpx.post(f"{base}/sessions/{user_id}/cookies", json={"cookies": cookies},
                       headers={"Authorization": f"Bearer {settings.camofox_api_key}"}, timeout=25)
        return (200 <= r.status_code < 300), r.text[:200]
    except httpx.HTTPError as e:
        return False, str(e)


@router.post("/stealth-sessions/{sid}/cookies")
def import_cookies(sid: int, body: CookieIn, db: Session = Depends(get_db)):
    """Push auth cookies into camofox under the session's sticky userId."""
    s = db.get(StealthSession, sid)
    if not s:
        raise HTTPException(404)
    user_id = f"{s.platform}-{s.id}"
    ok, detail = _push_cookies(user_id, body.cookies)
    if ok:
        s.cookie_ref = user_id
        s.status = "ready"
        db.commit()
    return {"ok": ok, "detail": detail}


class ConnectIn(BaseModel):
    platform: str
    cookies: list[dict]
    label: str = ""


@router.post("/connect")
def connect_account(body: ConnectIn, db: Session = Depends(get_db)):
    """One-shot 'log in from your browser' target for the CrawlOps extension:
    finds or creates a session for the platform and imports the live cookies."""
    s = (db.query(StealthSession)
         .filter(StealthSession.platform == body.platform,
                 StealthSession.cookie_ref.is_(None)).first())
    if s is None:
        s = StealthSession(platform=body.platform, label=body.label or f"{body.platform} account",
                           status="ready", daily_cap=40)
        db.add(s)
        db.flush()
    user_id = f"{s.platform}-{s.id}"
    ok, detail = _push_cookies(user_id, body.cookies)
    if ok:
        s.cookie_ref = user_id
        s.status = "ready"
        if body.label:
            s.label = body.label
        db.commit()
        return {"ok": True, "session_id": s.id, "imported": len(body.cookies)}
    raise HTTPException(502, f"camofox cookie import failed: {detail}")


@router.delete("/stealth-sessions/{sid}")
def delete_session(sid: int, db: Session = Depends(get_db)):
    s = db.get(StealthSession, sid)
    if s:
        db.delete(s)
        db.commit()
    return {"ok": True}


# ---- interactive in-app login (Playwright + Camoufox live remote browser) ----

def _login_base() -> str:
    return settings.loginsvc_url.rstrip("/")


class LoginStartIn(BaseModel):
    platform: str
    proxy_id: int | None = None


@router.post("/login/start")
def login_start(body: LoginStartIn, db: Session = Depends(get_db)):
    import httpx
    proxy = None
    if body.proxy_id:
        p = db.get(Proxy, body.proxy_id)
        proxy = decrypt_proxy(p.url) if p else None
    else:
        # auto-route login through a residential proxy if one exists, so the session is
        # created from the same kind of IP the crawler will use — this is what stops
        # Meta/TikTok flagging a "suspicious login" and killing the session later.
        p = (db.query(Proxy).filter(Proxy.active.is_(True), Proxy.tag == "residential")
             .first())
        proxy = decrypt_proxy(p.url) if p else None
    try:
        r = httpx.post(f"{_login_base()}/session",
                       json={"platform": body.platform, "proxy": proxy}, timeout=90)
        r.raise_for_status()
        return {**r.json(), "via_proxy": bool(proxy)}
    except httpx.HTTPError as e:
        raise HTTPException(502, f"login service unavailable: {e}") from e


@router.get("/login/{sid}/status")
def login_status(sid: str):
    import httpx
    try:
        r = httpx.get(f"{_login_base()}/session/{sid}/status", timeout=20)
        return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(502, str(e)) from e


@router.get("/login/{sid}/frame")
def login_frame(sid: str):
    import httpx
    try:
        r = httpx.get(f"{_login_base()}/session/{sid}/frame", timeout=30)
    except httpx.HTTPError as e:
        raise HTTPException(502, str(e)) from e
    if r.status_code != 200:
        raise HTTPException(r.status_code, "frame unavailable")
    return Response(content=r.content, media_type="image/jpeg",
                   headers={"Cache-Control": "no-store"})


class _Passthrough(BaseModel):
    x: float | None = None
    y: float | None = None
    text: str | None = None
    key: str | None = None
    dy: float | None = None


@router.post("/login/{sid}/{action}")
def login_action(sid: str, action: str, body: _Passthrough):
    import httpx
    if action not in ("click", "type", "key", "scroll"):
        raise HTTPException(404)
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        r = httpx.post(f"{_login_base()}/session/{sid}/{action}", json=payload, timeout=60)
        return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(502, str(e)) from e


class LoginFinishIn(BaseModel):
    platform: str
    label: str = ""


@router.post("/login/{sid}/finish")
def login_finish(sid: str, body: LoginFinishIn, db: Session = Depends(get_db)):
    """Grab the logged-in session's cookies and import them into a crawl session."""
    import httpx
    try:
        r = httpx.post(f"{_login_base()}/session/{sid}/finish", timeout=60)
        r.raise_for_status()
        cookies = r.json().get("cookies", [])
    except httpx.HTTPError as e:
        raise HTTPException(502, f"could not capture session: {e}") from e
    if not cookies:
        raise HTTPException(400, "no cookies captured — are you logged in?")

    s = (db.query(StealthSession)
         .filter(StealthSession.platform == body.platform,
                 StealthSession.cookie_ref.is_(None)).first())
    if s is None:
        s = StealthSession(platform=body.platform, label=body.label or f"{body.platform} account",
                           status="ready", daily_cap=40)
        db.add(s)
        db.flush()
    user_id = f"{s.platform}-{s.id}"
    ok, detail = _push_cookies(user_id, cookies)
    if ok:
        s.cookie_ref, s.status = user_id, "ready"
        if body.label:
            s.label = body.label
        db.commit()
        return {"ok": True, "session_id": s.id, "imported": len(cookies)}
    raise HTTPException(502, f"cookie import failed: {detail}")


@router.delete("/login/{sid}")
def login_close(sid: str):
    import httpx
    with __import__("contextlib").suppress(Exception):
        httpx.delete(f"{_login_base()}/session/{sid}", timeout=15)
    return {"ok": True}
