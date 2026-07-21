from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class IntelligenceStatusOut(BaseModel):
    available: bool
    llm_configured: bool
    provider: str
    model: str
    simulation_running: bool
    degraded: bool
    knowledge: dict[str, Any]
    schedule: dict[str, Any]
    enabled: bool | None = None
    rag_mode: str | None = None


class QueryIn(BaseModel):
    """Accept either `question` or frontend `query`."""

    question: str | None = Field(default=None, max_length=4000)
    query: str | None = Field(default=None, max_length=4000)
    session_key: str | None = None
    user_id: str | None = None
    use_llm: bool = True

    @model_validator(mode="after")
    def resolve_question(self) -> QueryIn:
        text = (self.question or self.query or "").strip()
        if not text:
            raise ValueError("question 或 query 不能为空")
        if len(text) < 1:
            raise ValueError("question 或 query 不能为空")
        self.question = text
        return self


class ChatIn(BaseModel):
    """Accept session_key and/or numeric session_id from frontend."""

    message: str = Field(min_length=1, max_length=4000)
    session_key: str | None = None
    session_id: int | None = None
    user_id: str | None = None
    title: str | None = Field(default=None, max_length=255)

    @model_validator(mode="before")
    @classmethod
    def coerce_session_id(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw = data.get("session_id")
        if raw is None or raw == "":
            data["session_id"] = None
            return data
        if isinstance(raw, str) and raw.isdigit():
            data["session_id"] = int(raw)
        return data


class InspectionScheduleIn(BaseModel):
    enabled: bool = False
    minute_of_hour: int = Field(default=0, ge=0, le=59)
    device_limit: int = Field(default=50, ge=1, le=500)


class KnowledgeSyncIn(BaseModel):
    batch_size: int | None = Field(default=None, ge=1, le=1000)
