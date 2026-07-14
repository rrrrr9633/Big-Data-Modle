from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.edge.simulation import IndustrialDeviceSimulator
from app.ingestion.http_schemas import TelemetryPayloadIn
from app.ingestion.mqtt_simulator import publish_payload_to_mqtt
from app.repositories.maintenance_repository import upsert_device, upsert_sensor_point

logger = logging.getLogger(__name__)

POINTS: dict[str, dict[str, object]] = {
    "air_temperature": {"name": "环境温度", "unit": "K", "min": 260, "max": 340},
    "process_temperature": {"name": "工艺温度", "unit": "K", "min": 280, "max": 380},
    "rotational_speed": {"name": "主轴转速", "unit": "rpm", "min": 0, "max": 3000},
    "torque": {"name": "扭矩", "unit": "Nm", "min": 0, "max": 120},
    "tool_wear": {"name": "刀具磨损", "unit": "min", "min": 0, "max": 300},
    "spindle_temperature": {"name": "主轴温度", "unit": "C", "min": 0, "max": 140},
    "spindle_load": {"name": "主轴负载", "unit": "%", "min": 0, "max": 100},
    "vibration_rms": {"name": "振动 RMS", "unit": "mm/s", "min": 0, "max": 20},
}


@dataclass(frozen=True)
class DeviceStreamConfig:
    device_count: int = 6
    mode: str = "degrading"
    interval_seconds: float = 1.0
    device_prefix: str = "CNC-L01"
    gateway_id: str = "edge-gateway-l01"
    factory: str = "默认工厂"
    workshop: str = "默认车间"
    production_line: str = "一号产线"


@dataclass
class DeviceStreamRuntime:
    running: bool = False
    cycle: int = 0
    config: DeviceStreamConfig = field(default_factory=DeviceStreamConfig)
    device_codes: list[str] = field(default_factory=list)
    accepted_events: int = 0
    failed_cycles: int = 0
    last_published_at: datetime | None = None
    last_error: str | None = None


class DeviceStreamSimulator:
    """Publishes CNC telemetry through MQTT exactly as an edge gateway does."""

    def __init__(self, *, publisher: Callable[..., dict[str, object]] = publish_payload_to_mqtt, provisioner: Callable[[DeviceStreamConfig, list[str]], None] | None = None) -> None:
        self._publisher = publisher
        self._provisioner = provisioner or provision_devices
        self._runtime = DeviceStreamRuntime()
        self._simulators: dict[str, IndustrialDeviceSimulator] = {}
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()

    def start(self, config: DeviceStreamConfig) -> DeviceStreamRuntime:
        self.stop()
        device_codes = [f"{config.device_prefix}-{index + 1:03d}" for index in range(config.device_count)]
        self._provisioner(config, device_codes)
        with self._lock:
            self._runtime = DeviceStreamRuntime(running=True, config=config, device_codes=device_codes)
            self._simulators = {code: IndustrialDeviceSimulator(device_code=code, seed=index + 1, mode=config.mode) for index, code in enumerate(device_codes)}
            self._stop_event = threading.Event()
        self.emit_cycle()
        self._thread = threading.Thread(target=self._run, name="device-stream-simulator", daemon=True)
        self._thread.start()
        return self.snapshot()

    def stop(self) -> DeviceStreamRuntime:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2)
        self._thread = None
        with self._lock:
            self._runtime.running = False
        return self.snapshot()

    def emit_cycle(self) -> DeviceStreamRuntime:
        with self._lock:
            if not self._runtime.running:
                return self.snapshot()
            cycle, config, simulators = self._runtime.cycle + 1, self._runtime.config, list(self._simulators.items())
        try:
            accepted = 0
            for device_code, simulator in simulators:
                readings = simulator.next_cycle(cycle=cycle)
                payload = TelemetryPayloadIn(device_code=device_code, device_name=f"数控机床 {device_code}", device_type="CNC", recorded_at=datetime.now(timezone.utc), readings=[{"sensor_code": code, "value": reading.value, "unit": str(POINTS[code]["unit"])} for code, reading in readings.items()])
                accepted += int(self._publisher(payload, gateway_id=config.gateway_id).get("accepted_events", 0))
            with self._lock:
                self._runtime.cycle = cycle
                self._runtime.accepted_events += accepted
                self._runtime.last_published_at = datetime.now(timezone.utc)
                self._runtime.last_error = None
        except Exception as exc:
            logger.exception("Device stream emission failed")
            with self._lock:
                self._runtime.failed_cycles += 1
                self._runtime.last_error = str(exc)
        return self.snapshot()

    def snapshot(self) -> DeviceStreamRuntime:
        with self._lock:
            return DeviceStreamRuntime(running=self._runtime.running, cycle=self._runtime.cycle, config=self._runtime.config, device_codes=list(self._runtime.device_codes), accepted_events=self._runtime.accepted_events, failed_cycles=self._runtime.failed_cycles, last_published_at=self._runtime.last_published_at, last_error=self._runtime.last_error)

    def _run(self) -> None:
        while not self._stop_event.wait(max(self.snapshot().config.interval_seconds, 0.1)):
            self.emit_cycle()


def provision_devices(config: DeviceStreamConfig, device_codes: list[str]) -> None:
    """Register assets before first publish so raw point validation stays unchanged."""
    with SessionLocal() as db:
        for device_code in device_codes:
            upsert_device(db, device_code=device_code, device_name=f"数控机床 {device_code}", device_type="CNC", status="online", factory=config.factory, workshop=config.workshop, production_line=config.production_line)
            for point_code, point in POINTS.items():
                upsert_sensor_point(db, device_code=device_code, sensor_code=point_code, sensor_name=str(point["name"]), unit=str(point["unit"]), sampling_frequency=f"{config.interval_seconds:g}s", protocol="mqtt", source_address=f"{device_code}/{point_code}", protocol_options={"gateway_id": config.gateway_id}, min_value=float(point["min"]), max_value=float(point["max"]), enabled=True)
        db.commit()
