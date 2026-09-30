"""JWT auth — bcrypt password hashing, bearer-token dependency.

Single-tenant team tool: users live in the users table, seeded with an admin from
env on first boot. Tokens are HS256 JWTs signed with a dedicated JWT_SECRET that
MUST be set per-deployment; signing/verifying fails closed on an unset/default key.
"""
import time

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import User

ALGO = "HS256"
TOKEN_TTL = 60 * 60 * 24 * 7  # 7 days
_bearer = HTTPBearer(auto_error=False)


# reject known-default / weak signing secrets — a public default here means anyone
# can forge an admin token (the whole API is behind this one check).
_WEAK_SECRETS = {"", "change-me", "changeme", "sk-crawlops-master-dev",
                 "crawlops-auth-sk-crawlops-master-dev", "crawlops-secret-change-me"}


def _secret() -> str:
    s = (settings.jwt_secret or "").strip()
    if not s or s in _WEAK_SECRETS or len(s) < 32:
        raise RuntimeError(
            "JWT_SECRET is unset, a known default, or shorter than 32 chars — refusing "
            "to sign/verify tokens. Set a random JWT_SECRET (e.g. `openssl rand -hex 32`) "
            "in the environment.")
    return s


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def make_token(user: User) -> str:
    payload = {"sub": user.username, "uid": user.id, "role": user.role,
               "exp": int(time.time()) + TOKEN_TTL}
    return jwt.encode(payload, _secret(), algorithm=ALGO)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _secret(), algorithms=[ALGO])


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
                 db: Session = Depends(get_db)) -> User:
    if cred is None:
        raise HTTPException(401, "not authenticated")
    try:
        payload = decode_token(cred.credentials)
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"invalid token: {e}") from e
    except RuntimeError as e:  # misconfigured signing secret — fail closed, no traceback
        raise HTTPException(503, str(e)) from e
    user = db.get(User, payload.get("uid"))
    if user is None:
        raise HTTPException(401, "user no longer exists")
    return user


def require_role(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if roles and user.role not in roles:
            raise HTTPException(403, "insufficient role")
        return user
    return dep
