from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.edge.contracts import EdgePointBinding, RawPointValue


class OpcUaAdapter:
    protocol = "opcua"

    def __init__(self, client_factory: Callable[[str], Any] | None = None) -> None:
        self._client_factory = client_factory or _build_client

    def read(self, binding: EdgePointBinding) -> RawPointValue:
        endpoint = str(binding.protocol_options.get("endpoint") or "").strip()
        if not endpoint:
            raise ValueError("OPC UA 点位缺少 protocol_options.endpoint")
        client = self._client_factory(endpoint)
        try:
            client.connect()
            value = float(client.get_node(binding.source_address).read_value())
            return RawPointValue(
                binding=binding,
                value=value,
                quality=1.0,
                acquired_at=datetime.now(timezone.utc),
                raw_status="good",
                raw_payload={
                    "protocol": self.protocol,
                    "endpoint": endpoint,
                    "node_id": binding.source_address,
                },
            )
        finally:
            client.disconnect()


def _build_client(endpoint: str) -> Any:
    try:
        from asyncua.sync import Client
    except ImportError as exc:
        raise RuntimeError("缺少 asyncua，请安装边缘采集依赖") from exc
    return Client(url=endpoint)
