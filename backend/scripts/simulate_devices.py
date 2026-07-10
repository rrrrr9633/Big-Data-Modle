from __future__ import annotations

import argparse
import csv
import json
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SENSOR_UNITS = {
    "air_temperature": "K",
    "process_temperature": "K",
    "rotational_speed": "rpm",
    "torque": "Nm",
    "tool_wear": "min",
}

FIELD_MAP = {
    "air_temperature": "Air temperature [K]",
    "process_temperature": "Process temperature [K]",
    "rotational_speed": "Rotational speed [rpm]",
    "torque": "Torque [Nm]",
    "tool_wear": "Tool wear [min]",
}


@dataclass(frozen=True)
class Ai4iSample:
    product_type: str
    failure: bool
    values: dict[str, float]


@dataclass
class SimulatedDevice:
    code: str
    name: str
    device_type: str
    mode: str
    cursor: int


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay AI4I rows as realtime device telemetry.")
    parser.add_argument("--csv", type=Path, default=project_root() / "ai4i2020.csv")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8000/api/v1/telemetry/readings")
    parser.add_argument("--devices", type=int, default=20)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--cycles", type=int, default=0, help="0 means run until interrupted.")
    parser.add_argument("--fault-rate", type=float, default=0.15)
    parser.add_argument("--degrade-rate", type=float, default=0.25)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_samples(csv_path: Path) -> tuple[list[Ai4iSample], list[Ai4iSample]]:
    normal: list[Ai4iSample] = []
    fault: list[Ai4iSample] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            sample = Ai4iSample(
                product_type=row.get("Type", "M") or "M",
                failure=(row.get("Machine failure") == "1"),
                values={sensor: float(row[column]) for sensor, column in FIELD_MAP.items()},
            )
            if sample.failure:
                fault.append(sample)
            else:
                normal.append(sample)
    if not normal:
        raise ValueError("AI4I CSV does not contain normal samples.")
    return normal, fault or normal


def build_devices(count: int, *, fault_rate: float, degrade_rate: float) -> list[SimulatedDevice]:
    devices: list[SimulatedDevice] = []
    fault_count = max(1, round(count * max(0.0, min(fault_rate, 1.0))))
    degrade_count = max(1, round(count * max(0.0, min(degrade_rate, 1.0)))) if count > 2 else 0
    for index in range(count):
        if index < fault_count:
            mode = "fault"
        elif index < fault_count + degrade_count:
            mode = "degrading"
        else:
            mode = "normal"
        devices.append(
            SimulatedDevice(
                code=f"SIM-{index + 1:04d}",
                name=f"设备 {index + 1:04d}",
                device_type="AI4I",
                mode=mode,
                cursor=random.randrange(0, 10_000),
            )
        )
    random.shuffle(devices)
    return devices


def jitter(value: float, ratio: float) -> float:
    return value * (1 + random.uniform(-ratio, ratio))


def evolve_values(values: dict[str, float], mode: str, cycle: int) -> dict[str, float]:
    evolved = {
        "air_temperature": jitter(values["air_temperature"], 0.002),
        "process_temperature": jitter(values["process_temperature"], 0.0025),
        "rotational_speed": jitter(values["rotational_speed"], 0.012),
        "torque": jitter(values["torque"], 0.018),
        "tool_wear": jitter(values["tool_wear"], 0.01),
    }
    if mode == "degrading":
        pressure = min(cycle / 60, 1.0)
        evolved["process_temperature"] += 4.0 * pressure
        evolved["rotational_speed"] *= 1 - 0.08 * pressure
        evolved["torque"] *= 1 + 0.12 * pressure
        evolved["tool_wear"] += 28.0 * pressure
    return evolved


def choose_sample(device: SimulatedDevice, normal: list[Ai4iSample], fault: list[Ai4iSample]) -> Ai4iSample:
    pool = fault if device.mode == "fault" else normal
    return pool[device.cursor % len(pool)]


def build_payload(device: SimulatedDevice, sample: Ai4iSample, cycle: int) -> dict[str, object]:
    values = evolve_values(sample.values, device.mode, cycle)
    return {
        "device_code": device.code,
        "device_name": device.name,
        "device_type": sample.product_type,
        "recorded_at": datetime.now(UTC).isoformat(),
        "readings": [
            {"sensor_code": sensor, "value": round(value, 4), "unit": SENSOR_UNITS[sensor]}
            for sensor, value in values.items()
        ],
    }


def post_json(endpoint: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def run() -> None:
    args = parse_args()
    normal, fault = load_samples(args.csv)
    devices = build_devices(args.devices, fault_rate=args.fault_rate, degrade_rate=args.degrade_rate)
    cycle = 0
    print(f"loaded normal={len(normal)} fault={len(fault)} devices={len(devices)}")
    try:
        while args.cycles <= 0 or cycle < args.cycles:
            for device in devices:
                sample = choose_sample(device, normal, fault)
                payload = build_payload(device, sample, cycle)
                device.cursor += 1
                if args.dry_run:
                    print(json.dumps(payload, ensure_ascii=False))
                    continue
                try:
                    result = post_json(args.endpoint, payload, args.timeout)
                    print(
                        f"{payload['device_code']} mode={device.mode} "
                        f"risk={result.get('risk_level')} "
                        f"prob={float(result.get('failure_probability', 0)):.4f} "
                        f"health={float(result.get('health_score', 0)):.1f}"
                    )
                except (HTTPError, URLError, TimeoutError) as reason:
                    print(f"{payload['device_code']} failed: {reason}")
            cycle += 1
            if args.interval > 0 and (args.cycles <= 0 or cycle < args.cycles):
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    run()