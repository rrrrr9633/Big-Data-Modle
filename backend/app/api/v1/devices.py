from typing import Annotated, Any

from app.core.database import get_db
from app.repositories.maintenance_repository import ensure_prediction_model_schema, fetch_devices
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get("")
def list_devices(db: DbSession) -> list[dict[str, Any]]:
    ensure_prediction_model_schema(db)
    return fetch_devices(db)