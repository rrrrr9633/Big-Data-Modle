from datetime import UTC, datetime

from app.ingestion.schemas import TelemetryEvent
from app.realtime import device_snapshot


class FakeRedis:
    def __init__(self) -> None:
        self.hsets: list[tuple[str, dict[str, object]]] = []
        self.sets: list[tuple[str, str, int | None]] = []
        self.expires: list[tuple[str, int]] = []
        self.closed = False

    def hset(self, key: str, *, mapping: dict[str, object]) -> None:
        self.hsets.append((key, mapping))

    def set(self, key: str, value: str, *, ex: int | None = None) -> None:
        self.sets.append((key, value, ex))

    def expire(self, key: str, seconds: int) -> None:
        self.expires.append((key, seconds))

    def close(self) -> None:
        self.closed = True


def test_update_device_snapshot_sets_ttl_for_latest_and_online(monkeypatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr(device_snapshot, "create_redis_client", lambda: redis)
    monkeypatch.setattr(device_snapshot.settings, "redis_latest_snapshot_ttl_seconds", 300)
    monkeypatch.setattr(device_snapshot.settings, "redis_online_ttl_seconds", 120)

    device_snapshot.update_device_snapshot(
        TelemetryEvent(
            device_code="CNC-001",
            point_code="spindle_temperature",
            value=72.5,
            unit="C",
            quality=0.98,
            ts=datetime(2026, 7, 10, 10, 0, tzinfo=UTC),
            event_id="evt-001",
            gateway_id="gw-01",
        )
    )

    assert redis.hsets[0][0] == "device:CNC-001:latest"
    assert redis.sets == [("device:CNC-001:online", "1", 120)]
    assert redis.expires == [("device:CNC-001:latest", 300)]
    assert redis.closed is True
