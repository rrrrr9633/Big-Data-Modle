from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.timeseries import TimeSeriesWindow


class WindowFeatureEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=128)
    device_code: str = Field(min_length=1, max_length=64)
    start_time: datetime
    end_time: datetime
    feature_values: dict[str, float]
    source: str = "tsdb"

    def to_window(self) -> TimeSeriesWindow:
        return TimeSeriesWindow(
            device_id=self.device_code,
            start_time=self.start_time,
            end_time=self.end_time,
            feature_values=self.feature_values,
        )

    def to_json_bytes(self) -> bytes:
        return self.model_dump_json().encode("utf-8")


def window_event_from_window(window: TimeSeriesWindow) -> WindowFeatureEvent:
    return WindowFeatureEvent(
        device_code=window.device_id,
        start_time=window.start_time,
        end_time=window.end_time,
        feature_values=window.feature_values,
    )


def parse_window_feature_event(raw: str | bytes | dict[str, Any]) -> WindowFeatureEvent:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        raise ValueError("窗口特征消息必须是 JSON 对象")
    return WindowFeatureEvent.model_validate(raw)
