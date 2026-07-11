from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.edge.simulation import IndustrialDeviceSimulator, SimulatedReading
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()
SimulationMode = Literal["normal", "degrading", "sudden_fault", "sensor_stuck", "sensor_drift"]


class SimulationStartIn(BaseModel):
    device_count: int = Field(default=6, ge=1, le=24)
    mode: SimulationMode = "degrading"


@dataclass
class ScenarioRuntime:
    running: bool = False
    cycle: int = 0
    mode: SimulationMode = "degrading"
    devices: dict[str, IndustrialDeviceSimulator] = field(default_factory=dict)

    def start(self, payload: SimulationStartIn) -> None:
        self.running = True
        self.cycle = 0
        self.mode = payload.mode
        self.devices = {
            f"SIM-CNC-{index + 1:03d}": IndustrialDeviceSimulator(
                device_code=f"SIM-CNC-{index + 1:03d}", seed=index + 1, mode=payload.mode
            )
            for index in range(payload.device_count)
        }

    def snapshot(self) -> dict[str, object]:
        return {
            "source": "simulation",
            "running": self.running,
            "cycle": self.cycle,
            "mode": self.mode,
            "devices": [
                {
                    "device_code": code,
                    "mode": simulator.mode,
                    "readings": _serialize_readings(simulator.next_cycle(cycle=self.cycle)),
                }
                for code, simulator in self.devices.items()
            ],
        }


def _serialize_readings(readings: dict[str, SimulatedReading]) -> dict[str, dict[str, object]]:
    return {
        name: {
            "value": reading.value,
            "quality": reading.quality,
            "status": reading.raw_status,
        }
        for name, reading in readings.items()
    }


runtime = ScenarioRuntime()


@router.get("/state")
def get_simulation_state() -> dict[str, object]:
    return runtime.snapshot()


@router.post("/start")
def start_simulation(payload: SimulationStartIn) -> dict[str, object]:
    runtime.start(payload)
    runtime.cycle = 1
    return runtime.snapshot()


@router.post("/tick")
def tick_simulation() -> dict[str, object]:
    if not runtime.running:
        raise HTTPException(status_code=409, detail="仿真场景未启动")
    runtime.cycle += 1
    return runtime.snapshot()


@router.post("/stop")
def stop_simulation() -> dict[str, object]:
    runtime.running = False
    return runtime.snapshot()
