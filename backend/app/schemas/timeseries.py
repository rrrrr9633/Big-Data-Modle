from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["low", "medium", "high", "critical"]


class SensorReading(BaseModel):
    device_id: str
    sensor_code: str
    timestamp: datetime
    value: float | None
    unit: str | None = None


class GovernedReading(SensorReading):
    value: float
    normalized_value: float
    quality_score: float = Field(ge=0, le=1)


class GovernedReadingWindow(BaseModel):
    device_id: str
    sensor_code: str
    start_time: datetime
    end_time: datetime
    readings: list[GovernedReading]


class TimeSeriesWindow(BaseModel):
    device_id: str
    start_time: datetime
    end_time: datetime
    feature_values: dict[str, float]


class PredictionResult(BaseModel):
    device_id: str
    failure_probability: float = Field(ge=0, le=1)
    health_score: float = Field(ge=0, le=100)
    risk_level: RiskLevel
    anomaly_score: float = Field(default=0.0, ge=0, le=1)
    anomaly_reasons: list[str] = Field(default_factory=list)
    trend_factor: float = 0.0
    quality_score: float = Field(default=1.0, ge=0, le=1)
    rul_hours: float | None = None


class MaintenanceAdvice(BaseModel):
    device_id: str
    risk_level: RiskLevel
    title: str
    detail: str
    suggested_action: str