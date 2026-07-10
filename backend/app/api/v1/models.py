from typing import Annotated, Any

from app.core.database import get_db
from app.models.registry import (
    ActiveModelState,
    delete_active_model_artifacts,
    get_active_model_state,
)
from app.repositories.maintenance_repository import (
    fetch_model_versions,
    reset_training_records,
)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/active")
def get_active_model() -> ActiveModelState:
    return get_active_model_state()


@router.get("")
def list_model_versions(db: DbSession) -> list[dict[str, Any]]:
    return fetch_model_versions(db)


@router.delete("/active")
def reset_active_model(db: DbSession) -> dict[str, object]:
    deleted_records = reset_training_records(db)
    deleted_artifacts = delete_active_model_artifacts()
    db.commit()
    return {
        "status": "reset",
        "deleted_records": deleted_records,
        **deleted_artifacts,
    }