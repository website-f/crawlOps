"""JWT auth — bcrypt password hashing, bearer-token dependency.

Single-tenant team tool: users live in the users table, seeded with an admin from
env on first boot. Tokens are HS256 JWTs signed with LITELLM master key derivative.
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


def _secret() -> str:
    return f"crawlops-auth-{settings.litellm_master_key}"


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
