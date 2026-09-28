from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import BenchmarkEntity, Topic
from ..services import insights

router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])


class EntityIn(BaseModel):
    topic_id: int
    name: str
    keywords: list[str] = []
    is_own_brand: bool = False


def _dump(e: BenchmarkEntity) -> dict:
    return {"id": e.id, "topic_id": e.topic_id, "name": e.name,
            "keywords": e.keywords, "is_own_brand": e.is_own_brand}


@router.get("/entities")
def list_entities(topic_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(BenchmarkEntity)
    if topic_id:
        q = q.filter(BenchmarkEntity.topic_id == topic_id)
    return [_dump(e) for e in q.order_by(BenchmarkEntity.id).all()]


@router.post("/entities")
def create_entity(body: EntityIn, db: Session = Depends(get_db)):
    if not db.get(Topic, body.topic_id):
        raise HTTPException(404, "topic not found")
    e = BenchmarkEntity(**body.model_dump())
    db.add(e)
    db.commit()
    return _dump(e)


@router.put("/entities/{eid}")
def update_entity(eid: int, body: EntityIn, db: Session = Depends(get_db)):
    e = db.get(BenchmarkEntity, eid)
    if not e:
        raise HTTPException(404)
    for k, v in body.model_dump().items():
        setattr(e, k, v)
    db.commit()
    return _dump(e)


@router.delete("/entities/{eid}")
def delete_entity(eid: int, db: Session = Depends(get_db)):
    e = db.get(BenchmarkEntity, eid)
    if e:
        db.delete(e)
        db.commit()
    return {"ok": True}


def _entities(db: Session, topic_id: int | None) -> list[BenchmarkEntity]:
    q = db.query(BenchmarkEntity)
    if topic_id:
        q = q.filter(BenchmarkEntity.topic_id == topic_id)
    return q.all()


@router.get("/sov")
def share_of_voice(topic_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    ents = _entities(db, topic_id)
    if not ents:
        return {"entities": [], "days": []}
    return insights.share_of_voice(db, topic_id, ents, days)


@router.get("/compare")
def compare(topic_id: int | None = None, days: int = 14, db: Session = Depends(get_db)):
    return insights.benchmark_compare(db, topic_id, _entities(db, topic_id), days)
