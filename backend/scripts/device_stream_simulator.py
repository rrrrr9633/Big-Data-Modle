"""Run a continuous CNC device stream through MQTT and the production pipeline."""
from __future__ import annotations

import argparse
import signal
from threading import Event

from app.edge.device_stream import DeviceStreamConfig, DeviceStreamSimulator


def main() -> None:
    parser = argparse.ArgumentParser(description="持续发布工业设备 MQTT 遥测流")
    parser.add_argument("--devices", type=int, default=6)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--mode", default="degrading")
    parser.add_argument("--prefix", default="CNC-L01")
    args = parser.parse_args()
    simulator = DeviceStreamSimulator()
    simulator.start(DeviceStreamConfig(device_count=args.devices, interval_seconds=args.interval, mode=args.mode, device_prefix=args.prefix))
    stopped = Event()
    signal.signal(signal.SIGINT, lambda *_args: stopped.set())
    signal.signal(signal.SIGTERM, lambda *_args: stopped.set())
    stopped.wait()
    simulator.stop()


if __name__ == "__main__":
    main()
