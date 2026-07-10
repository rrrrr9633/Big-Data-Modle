from __future__ import annotations

from dataclasses import dataclass

from app.ingestion.schemas import TelemetryEvent


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reason: str | None = None


def validate_telemetry_event(event: TelemetryEvent) -> ValidationResult:
    if event.value != event.value:
        return ValidationResult(valid=False, reason="value cannot be NaN")
    if not 0 <= event.quality <= 1:
        return ValidationResult(valid=False, reason="quality must be between 0 and 1")
    if not event.device_code.strip():
        return ValidationResult(valid=False, reason="device_code is required")
    if not event.point_code.strip():
        return ValidationResult(valid=False, reason="point_code is required")
    return ValidationResult(valid=True)