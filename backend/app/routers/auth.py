from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..services import loginguard
from ..services.auth import (current_user, hash_password, make_token,
                             require_role, verify_password)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


class LoginIn(BaseModel):
    username: str
    password: str


class UserIn(BaseModel):
    username: str
    password: str
    role: str = "analyst"


class ChangePwIn(BaseModel):
    old_password: str
    new_password: str


class ResetPwIn(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    if loginguard.is_locked(ip, body.username):
        raise HTTPException(429, "too many login attempts — try again in a few minutes")
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        loginguard.record_failure(ip, body.username)
        raise HTTPException(401, "invalid username or password")
    loginguard.clear(ip, body.username)
    return {"token": make_token(user),
            "user": {"username": user.username, "role": user.role}}


@router.post("/change-password")
def change_password(body: ChangePwIn, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(400, "current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(400, "new password must be at least 8 characters")
    user.password_hash = hash_password(body.new_password)
    user.token_version = (user.token_version or 0) + 1  # revoke every other session
    db.commit()
    return {"token": make_token(user)}   # fresh token so the caller stays signed in


@router.post("/users/{uid}/reset-password")
def reset_password(uid: int, body: ResetPwIn, _: User = Depends(require_role("admin")),
                   db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "no such user")
    if len(body.password) < 8:
        raise HTTPException(400, "password must be at least 8 characters")
    u.password_hash = hash_password(body.password)
    u.token_version = (u.token_version or 0) + 1   # sign the user out everywhere
    db.commit()
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"username": user.username, "role": user.role}


@router.get("/users")
def list_users(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return [{"id": u.id, "username": u.username, "role": u.role}
            for u in db.query(User).order_by(User.id).all()]


@router.post("/users")
def create_user(body: UserIn, _: User = Depends(require_role("admin")),
                db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(400, "username taken")
    u = User(username=body.username, password_hash=hash_password(body.password),
             role=body.role)
    db.add(u)
    db.commit()
    return {"id": u.id, "username": u.username, "role": u.role}


@router.delete("/users/{uid}")
def delete_user(uid: int, actor: User = Depends(require_role("admin")),
                db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if u and u.id != actor.id:  # can't delete yourself
        db.delete(u)
        db.commit()
    return {"ok": True}
