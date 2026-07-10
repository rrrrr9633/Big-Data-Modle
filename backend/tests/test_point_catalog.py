from datetime import UTC, datetime

from app.ingestion.schemas import TelemetryEvent
from app.quality.point_catalog import validate_event_against_point_catalog


class FakeDb:
    def __init__(self, row: dict[str, object] | None) -> None:
        self.row = row

    def execute(self, *_args, **_kwargs):
        return self

    def mappings(self):
        return self

    def first(self):
        return self.row


def _event(**overrides: object) -> TelemetryEvent:
    payload = {
        "event_id": "evt-001",
        "device_code": "CNC-001",
        "point_code": "spindle_temperature",
        "value": 72.5,
        "unit": "C",
        "quality": 0.98,
        "ts": datetime(2026, 7, 10, tzinfo=UTC),
        "gateway_id": "gw-01",
    }
    payload.update(overrides)
    return TelemetryEvent.model_validate(payload)


def test_point_catalog_accepts_enabled_registered_point() -> None:
    result = validate_event_against_point_catalog(
        _event(),
        FakeDb(
            {
                "device_code": "CNC-001",
                "status": "online",
                "sensor_code": "spindle_temperature",
                "unit": "C",
                "enabled": True,
                "min_value": 0,
                "max_value": 120,
            }
        ),
    )

    assert result.valid is True


def test_point_catalog_rejects_unknown_device_or_point() -> None:
    result = validate_event_against_point_catalog(_event(), FakeDb(None))

    assert result.valid is False
    assert result.reason == "device or point is not registered"


def test_point_catalog_rejects_disabled_point_unit_mismatch_and_value_range() -> None:
    disabled = validate_event_against_point_catalog(
        _event(),
        FakeDb(
            {
                "device_code": "CNC-001",
                "sensor_code": "spindle_temperature",
                "unit": "C",
                "enabled": False,
                "min_value": 0,
                "max_value": 120,
            }
        ),
    )
    unit_mismatch = validate_event_against_point_catalog(
        _event(unit="K"),
        FakeDb(
            {
                "device_code": "CNC-001",
                "sensor_code": "spindle_temperature",
                "unit": "C",
                "enabled": True,
                "min_value": 0,
                "max_value": 120,
            }
        ),
    )
    out_of_range = validate_event_against_point_catalog(
        _event(value=180),
        FakeDb(
            {
                "device_code": "CNC-001",
                "sensor_code": "spindle_temperature",
                "unit": "C",
                "enabled": True,
                "min_value": 0,
                "max_value": 120,
            }
        ),
    )

    assert disabled.reason == "point is disabled"
    assert unit_mismatch.reason == "unit mismatch: expected C, got K"
    assert out_of_range.reason == "value out of configured range"
