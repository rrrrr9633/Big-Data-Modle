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

    def __init__(
        self,
        *,
        device_code: str,
        seed: int = 1,
        mode: str = "normal",
        fault_start_cycle: int = 0,
    ) -> None:
        self.device_code = device_code
        self.seed = seed
        self.mode = mode
        self.fault_start_cycle = max(fault_start_cycle, 0)
        profile_rng = random.Random(f"profile:{seed}:{device_code}")
        self._profile = {
            "thermal_bias": profile_rng.uniform(-2.5, 5.0),
            "speed_factor": profile_rng.uniform(0.91, 1.07),
            "load_factor": profile_rng.uniform(0.88, 1.16),
            "wear_bias": profile_rng.uniform(0.0, 38.0),
            "vibration_bias": profile_rng.uniform(-0.18, 0.75),
            "age_cycles": profile_rng.uniform(0.0, 48.0),
            "fault_severity": profile_rng.uniform(0.68, 1.32),
            "drift_rate": profile_rng.uniform(0.18, 0.52),
        }
        sensor_pool = ["vibration_rms", "spindle_load", "torque"]
        profile_rng.shuffle(sensor_pool)
        self._fault_sensors = {"spindle_temperature", sensor_pool[0]}
        self._stuck_values: dict[str, float] = {}

    def next_cycle(self, *, cycle: int) -> dict[str, SimulatedReading]:
        rng = random.Random(f"{self.seed}:{self.device_code}:{cycle}")
        profile = self._profile
        pressure = (
            min(max(cycle + profile["age_cycles"], 0.0) / 135.0, 1.0)
            if self.mode == "degrading"
            else 0.0
        )
        values = {
            name: value * (1 + rng.uniform(-0.012, 0.012))
            for name, value in self._BASELINE.items()
        }
        values["air_temperature"] += profile["thermal_bias"] * 0.35
        values["process_temperature"] += profile["thermal_bias"]
        values["spindle_temperature"] += profile["thermal_bias"]
        values["rotational_speed"] *= profile["speed_factor"]
        values["torque"] *= profile["load_factor"]
        values["spindle_load"] *= profile["load_factor"]
        values["tool_wear"] += profile["wear_bias"]
        values["vibration_rms"] += profile["vibration_bias"]

        values["tool_wear"] += 55.0 * pressure * profile["fault_severity"]
        values["spindle_temperature"] += 30.0 * pressure * profile["fault_severity"]
        values["process_temperature"] += 8.0 * pressure * profile["fault_severity"]
        values["spindle_load"] += 24.0 * pressure * profile["fault_severity"]
        values["vibration_rms"] += 4.5 * pressure * profile["fault_severity"]
        values["rotational_speed"] *= 1 - 0.12 * pressure * profile["fault_severity"]

        quality_by_sensor = {name: 1.0 for name in values}
        status_by_sensor = {name: "good" for name in values}
        if self.mode == "sudden_fault":
            elapsed = max(cycle - self.fault_start_cycle + 1, 0)
            progression = min(elapsed / 18.0, 1.0)
            severity = profile["fault_severity"] * progression
            values["spindle_temperature"] += 32.0 * severity
            values["vibration_rms"] += 4.8 * severity
            values["torque"] *= 1 + 0.22 * severity
            for sensor in ("spindle_temperature", "vibration_rms", "torque"):
                quality_by_sensor[sensor] = max(0.62, 1.0 - 0.28 * progression)
                status_by_sensor[sensor] = "sudden_fault" if progression > 0 else "fault_emerging"
        elif self.mode == "sensor_stuck":
            for sensor in self._fault_sensors:
                self._stuck_values.setdefault(sensor, values[sensor])
                values[sensor] = self._stuck_values[sensor]
                quality_by_sensor[sensor] = 0.45
                status_by_sensor[sensor] = "sensor_stuck"
        elif self.mode == "sensor_drift":
            drift = 5.0 + cycle * profile["drift_rate"]
            drift_scale = {
                "spindle_temperature": 1.0,
                "vibration_rms": 0.12,
                "spindle_load": 0.6,
                "torque": 0.35,
            }
            for sensor in self._fault_sensors:
                values[sensor] += drift * drift_scale[sensor]
                quality_by_sensor[sensor] = 0.55
                status_by_sensor[sensor] = "sensor_drift"

        return {
            name: SimulatedReading(
                value=round(value, 4),
                quality=quality_by_sensor[name],
                raw_status=status_by_sensor[name],
                raw_payload={
                    "device_mode": self.mode,
                    "cycle": cycle,
                    "seed": self.seed,
                    "fault_sensors": sorted(self._fault_sensors),
                },
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
