"""Custom dashboards — CRUD over user-built widget layouts. Widgets read from the
existing analytics endpoints; this just stores the layout."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Dashboard

router = APIRouter(prefix="/api/dashboards", tags=["dashboards"])


def _dump(d: Dashboard) -> dict:
    return {"id": d.id, "name": d.name, "widgets": d.widgets or []}


class DashboardIn(BaseModel):
    name: str
    widgets: list = []


@router.get("")
def list_dashboards(db: Session = Depends(get_db)):
    return [_dump(d) for d in db.query(Dashboard).order_by(Dashboard.id).all()]


@router.post("")
def create_dashboard(body: DashboardIn, db: Session = Depends(get_db)):
    d = Dashboard(name=body.name.strip()[:120] or "Untitled", widgets=body.widgets)
    db.add(d)
    db.commit()
    return _dump(d)


@router.put("/{dash_id}")
def update_dashboard(dash_id: int, body: DashboardIn, db: Session = Depends(get_db)):
    d = db.get(Dashboard, dash_id)
    if not d:
        raise HTTPException(404)
    d.name, d.widgets = body.name.strip()[:120] or d.name, body.widgets
    db.commit()
    return _dump(d)


@router.delete("/{dash_id}")
def delete_dashboard(dash_id: int, db: Session = Depends(get_db)):
    d = db.get(Dashboard, dash_id)
    if d:
        db.delete(d)
        db.commit()
    return {"ok": True}
