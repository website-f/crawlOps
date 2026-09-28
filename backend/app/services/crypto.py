"""Symmetric encryption for provider API keys at rest (Fernet/AES-128-CBC+HMAC).

The Fernet key is derived from SECRET_KEY (env). Rotating SECRET_KEY invalidates
stored keys — they must be re-entered. Keys are never returned to the client in
plaintext; the UI only ever sees a masked hint.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from ..config import settings

_fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest()))


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken:
        return ""


def mask(plaintext: str) -> str:
    """A safe hint for the UI: last 4 chars only."""
    if not plaintext:
        return ""
    return f"…{plaintext[-4:]}" if len(plaintext) > 4 else "…"
