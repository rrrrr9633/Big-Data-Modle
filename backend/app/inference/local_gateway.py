from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime, timezone
from time import monotonic
from typing import Any

from app.compute.features import build_feature_window
from app.core.config import settings
from app.features.schemas import WindowFeatureEvent, window_event_from_window
from app.inference.predictor import run_async_inference
from app.ingestion.http_schemas import TelemetryPayloadIn
from app.schemas.timeseries import GovernedReading

InferenceCallable = Callable[..., Any]


class LocalInferenceGateway:
    """Runs the existing model path in-process for middleware-free demonstrations."""

    def __init__(
        self,
        *,
        inference_runner: InferenceCallable = run_async_inference,
        now: Callable[[], float] = monotonic,
    ) -> None:
        self._inference_runner = inference_runner
        self._now = now
        self._last_inferred_at: dict[str, float] = {}
        self._lock = threading.Lock()

    def infer(self, payload: TelemetryPayloadIn) -> dict[str, object]:
        if not settings.local_inference_enabled:
            return {"prediction_created": False, "inference_status": "disabled"}

        feature_event = _feature_event_from_payload(payload)
        if feature_event is None:
            return {
                "prediction_created": False,
                "inference_status": "skipped",
                "reason": "缺少 AI4I 模型必需点位",
            }
        if not self._should_infer(payload.device_code):
            return {"prediction_created": False, "inference_status": "throttled"}

        forced_failure = any(reading.status == "sudden_fault" for reading in payload.readings)
        output = self._inference_runner(feature_event, forced_failure=forced_failure)
        return {
            "prediction_created": True,
            "prediction_id": output.prediction_id,
            "warning_created": output.warning_created,
            "inference_status": "completed",
        }

    def _should_infer(self, device_code: str) -> bool:
        now = self._now()
        interval = max(float(settings.local_inference_interval_seconds), 0.0)
        with self._lock:
            previous = self._last_inferred_at.get(device_code)
            if previous is not None and now - previous < interval:
                return False
            self._last_inferred_at[device_code] = now
            return True


def _feature_event_from_payload(payload: TelemetryPayloadIn) -> WindowFeatureEvent | None:
    timestamp = payload.recorded_at or datetime.now(timezone.utc)
    readings = [
        GovernedReading(
            device_id=payload.device_code,
            sensor_code=reading.sensor_code,
            timestamp=timestamp,
            value=reading.value,
            unit=reading.unit,
            normalized_value=reading.value,
            quality_score=reading.quality,
        )
        for reading in payload.readings
    ]
    window = build_feature_window(readings)
    if window is None:
        return None
    required = {
        "sensor_latest_air_temperature",
        "sensor_latest_process_temperature",
        "sensor_latest_rotational_speed",
        "sensor_latest_torque",
        "sensor_latest_tool_wear",
    }
    if not required.issubset(window.feature_values):
        return None
    return window_event_from_window(window).model_copy(update={"source": "local-direct"})


local_inference_gateway = LocalInferenceGateway()
