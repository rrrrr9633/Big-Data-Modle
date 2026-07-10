from typing import Annotated

from app.core.database import get_db
from app.realtime.overview import fetch_realtime_device, fetch_realtime_overview
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/overview")
def get_realtime_overview(db: DbSession) -> dict[str, object]:
    return fetch_realtime_overview(db)


@router.get("/devices/{device_code}")
def get_realtime_device(device_code: str, db: DbSession) -> dict[str, object]:
    return fetch_realtime_device(db, device_code)