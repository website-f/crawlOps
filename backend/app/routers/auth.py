from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..services.auth import (current_user, hash_password, make_token,
                             require_role, verify_password)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class UserIn(BaseModel):
    username: str
    password: str
    role: str = "analyst"


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "invalid username or password")
    return {"token": make_token(user),
            "user": {"username": user.username, "role": user.role}}


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
