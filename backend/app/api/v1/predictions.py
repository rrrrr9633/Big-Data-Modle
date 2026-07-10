from typing import Annotated, Any

from app.core.database import get_db
from app.repositories.maintenance_repository import (
    ensure_prediction_model_schema,
    fetch_predictions,
)
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
PredictionLimit = Annotated[int, Query(ge=1, le=500)]


@router.get("")
def list_predictions(db: DbSession, limit: PredictionLimit = 100) -> list[dict[str, Any]]:
    ensure_prediction_model_schema(db)
    return fetch_predictions(db, limit=limit)
