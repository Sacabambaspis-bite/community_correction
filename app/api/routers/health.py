"""健康检查：免鉴权。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.errors import envelope
from app.api.schemas import HealthOut

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return envelope(data=HealthOut(db=db_ok).model_dump())
