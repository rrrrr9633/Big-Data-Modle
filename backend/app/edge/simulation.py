from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timezone

from app.edge.contracts import EdgePointBinding, RawPointValue


@dataclass(frozen=True)
class SimulatedReading:
    value: float
    quality: float
    raw_status: str
    raw_payload: dict[str, object]


class IndustrialDeviceSimulator:
    """Repeatable CNC-like sensor behavior for integration and fault drills."""

    _BASELINE = {
        "air_temperature": 298.2,
        "process_temperature": 308.8,
        "rotational_speed": 1480.0,
        "torque": 42.0,
        "tool_wear": 18.0,
        "spindle_temperature": 42.0,
        "spindle_load": 46.0,
        "vibration_rms": 1.4,
    }

    def __init__(self, *, device_code: str, seed: int = 1, mode: str = "normal") -> None:
        self.device_code = device_code
        self.seed = seed
        self.mode = mode
        self._stuck_values: dict[str, float] | None = None

    def next_cycle(self, *, cycle: int) -> dict[str, SimulatedReading]:
        rng = random.Random(f"{self.seed}:{self.device_code}:{cycle}")
        pressure = min(max(cycle, 0) / 120.0, 1.0) if self.mode == "degrading" else 0.0
        values = {
            name: value * (1 + rng.uniform(-0.012, 0.012))
            for name, value in self._BASELINE.items()
        }
        values["tool_wear"] += 55.0 * pressure
        values["spindle_temperature"] += 30.0 * pressure
        values["process_temperature"] += 8.0 * pressure
        values["spindle_load"] += 24.0 * pressure
        values["vibration_rms"] += 4.5 * pressure
        values["rotational_speed"] *= 1 - 0.12 * pressure

        if self.mode == "sudden_fault":
            values["spindle_temperature"] += 46.0
            values["vibration_rms"] += 7.0
            values["torque"] *= 1.32
        if self.mode == "sensor_stuck":
            self._stuck_values = self._stuck_values or values.copy()
            values = self._stuck_values.copy()
        if self.mode == "sensor_drift":
            values["spindle_temperature"] += cycle * 0.25

        quality = 0.55 if self.mode in {"sensor_stuck", "sensor_drift"} else 1.0
        status = self.mode if quality < 1.0 else "good"
        return {
            name: SimulatedReading(
                value=round(value, 4),
                quality=quality,
                raw_status=status,
                raw_payload={"device_mode": self.mode, "cycle": cycle, "seed": self.seed},
            )
            for name, value in values.items()
        }


def simulated_value(binding: EdgePointBinding, *, salt: str) -> RawPointValue:
    digest = hashlib.sha256(
        f"{salt}:{binding.device_code}:{binding.point_code}:{binding.source_address}".encode()
    ).hexdigest()
    ratio = int(digest[:8], 16) / 0xFFFFFFFF
    value = _scale_value(binding, ratio)
    return RawPointValue(
        binding=binding,
        value=value,
        quality=1.0 if binding.enabled else 0.0,
        acquired_at=datetime.now(timezone.utc),
        raw_status="simulated",
        raw_payload={
            "protocol": binding.protocol,
            "source_address": binding.source_address,
            "simulation_seed": digest[:12],
        },
    )


def _scale_value(binding: EdgePointBinding, ratio: float) -> float:
    if binding.min_value is not None and binding.max_value is not None:
        return round(
            float(binding.min_value)
            + (float(binding.max_value) - float(binding.min_value)) * ratio,
            4,
        )
    return round(ratio * 100, 4)
