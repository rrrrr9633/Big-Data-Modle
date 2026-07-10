from typing import Annotated

from app.core.database import get_db
from app.repositories.maintenance_repository import fetch_dashboard_summary
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/summary")
def get_dashboard_summary(db: DbSession) -> dict[str, int | float]:
    return fetch_dashboard_summary(db)
