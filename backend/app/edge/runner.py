from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import Any

from app.edge.contracts import EdgeAdapterConfig, EdgeGatewayConfig
from app.edge.publisher import publish_events
from app.edge.runtime import collect_live_once

logger = logging.getLogger(__name__)


class EdgeRunner:
    def __init__(
        self,
        config: EdgeAdapterConfig,
        *,
        collector: Callable[[EdgeAdapterConfig], list[Any]] = collect_live_once,
        publisher: Callable[[list[Any], EdgeGatewayConfig], Any] | None = None,
    ) -> None:
        self.config = config
        self._collector = collector
        self._publisher = publisher or self._publish

    def run_once(self) -> Any:
        events = self._collector(self.config)
        return self._publisher(events, self.config.gateway)

    def run_forever(self, *, stop_event: Event, interval_seconds: float) -> None:
        while not stop_event.is_set():
            try:
                self.run_once()
            except Exception:
                logger.exception("边缘采集周期失败，等待下一周期")
            stop_event.wait(interval_seconds)

    def _publish(self, events: list[Any], gateway: EdgeGatewayConfig) -> Any:
        return publish_events(events, gateway=gateway, mode=gateway.publish_mode)


def load_config(path: str | Path) -> EdgeAdapterConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return EdgeAdapterConfig.model_validate(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="工业边缘采集运行器")
    parser.add_argument("config", help="edge-adapter-config.v1 JSON 文件")
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    runner = EdgeRunner(load_config(args.config))
    if args.once:
        print(json.dumps(runner.run_once().model_dump(mode="json"), ensure_ascii=False))
        return
    runner.run_forever(stop_event=Event(), interval_seconds=max(args.interval_seconds, 0.1))


if __name__ == "__main__":
    main()
