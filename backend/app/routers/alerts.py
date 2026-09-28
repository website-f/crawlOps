from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AlertEvent, AlertRule, Topic

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class RuleIn(BaseModel):
    topic_id: int
    kind: str = "spike"          # spike | neg_sentiment
    config: dict = {}
    notify: dict = {}            # {webhook_url?, telegram_bot_token?, telegram_chat_id?}
    active: bool = True


def _dump(r: AlertRule) -> dict:
    return {"id": r.id, "topic_id": r.topic_id, "kind": r.kind,
            "config": r.config, "notify": r.notify, "active": r.active}


@router.get("/rules")
def list_rules(db: Session = Depends(get_db)):
    return [_dump(r) for r in db.query(AlertRule).order_by(AlertRule.id).all()]


@router.post("/rules")
def create_rule(body: RuleIn, db: Session = Depends(get_db)):
    if body.kind not in ("spike", "neg_sentiment"):
        raise HTTPException(400, "kind must be spike|neg_sentiment")
    if not db.get(Topic, body.topic_id):
        raise HTTPException(404, "topic not found")
    r = AlertRule(**body.model_dump())
    db.add(r)
    db.commit()
    return _dump(r)


@router.put("/rules/{rule_id}")
def update_rule(rule_id: int, body: RuleIn, db: Session = Depends(get_db)):
    r = db.get(AlertRule, rule_id)
    if not r:
        raise HTTPException(404)
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    db.commit()
    return _dump(r)


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    r = db.get(AlertRule, rule_id)
    if r:
        db.delete(r)
        db.commit()
    return {"ok": True}


@router.get("/events")
def list_events(limit: int = 50, db: Session = Depends(get_db)):
    rows = (db.query(AlertEvent).order_by(AlertEvent.id.desc())
            .limit(min(limit, 200)).all())
    return [{"id": e.id, "rule_id": e.rule_id, "fired_at": e.fired_at.isoformat(),
             "payload": e.payload} for e in rows]
