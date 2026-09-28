"""Alert delivery — webhook + Telegram. Channels configured in Settings, read at
send time so no redeploy is needed. Best-effort: a failing channel is logged,
never raised into the pipeline."""
import logging

import httpx
from sqlalchemy.orm import Session

from .settings_store import get_setting

log = logging.getLogger("notifier")


def notify(db: Session, title: str, body: str, payload: dict,
           channels: dict | None = None) -> dict:
    """channels overrides per-rule; falls back to global Settings notifiers."""
    cfg = channels or {}
    globals_ = get_setting(db, "notifiers")
    webhook = cfg.get("webhook_url") or globals_.get("webhook_url", "")
    tg_token = cfg.get("telegram_bot_token") or globals_.get("telegram_bot_token", "")
    tg_chat = cfg.get("telegram_chat_id") or globals_.get("telegram_chat_id", "")

    results = {}
    if webhook:
        results["webhook"] = _webhook(webhook, {"title": title, "body": body, **payload})
    if tg_token and tg_chat:
        results["telegram"] = _telegram(tg_token, tg_chat, f"*{title}*\n{body}")
    if not results:
        log.info("alert '%s' has no configured channel — logged only", title)
    return results


def _webhook(url: str, data: dict) -> bool:
    try:
        r = httpx.post(url, json=data, timeout=15, follow_redirects=False)
        return 200 <= r.status_code < 300
    except httpx.HTTPError as e:
        log.warning("webhook failed: %s", e)
        return False


def _telegram(token: str, chat_id: str, text: str) -> bool:
    try:
        r = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
                       json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                       timeout=15)
        return r.status_code == 200
    except httpx.HTTPError as e:
        log.warning("telegram failed: %s", e)
        return False


def test_channels(db: Session) -> dict:
    return notify(db, "CrawlOps test alert",
                  "If you can read this, your alert channel works.",
                  {"kind": "test"})
