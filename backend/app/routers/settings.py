from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.notifier import test_channels
from ..services.settings_store import all_settings, get_setting, set_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingIn(BaseModel):
    value: dict


@router.get("")
def read_all(db: Session = Depends(get_db)):
    return all_settings(db)


@router.put("/{key}")
def write(key: str, body: SettingIn, db: Session = Depends(get_db)):
    return set_setting(db, key, body.value)


@router.get("/{key}")
def read_one(key: str, db: Session = Depends(get_db)):
    return get_setting(db, key)


@router.post("/notifiers/test")
def test_notifiers(db: Session = Depends(get_db)):
    results = test_channels(db)
    return {"ok": any(results.values()) if results else False, "results": results}
