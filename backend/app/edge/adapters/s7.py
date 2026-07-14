from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.edge.adapters.parsing import decode_s7_value, parse_s7_address
from app.edge.contracts import EdgePointBinding, RawPointValue


class S7Adapter:
    protocol = "s7"

    def __init__(self, client_factory: Callable[[], Any] | None = None) -> None:
        self._client_factory = client_factory or _build_client

    def read(self, binding: EdgePointBinding) -> RawPointValue:
        address = parse_s7_address(binding.source_address)
        options = binding.protocol_options
        host = str(options.get("host") or "").strip()
        if not host:
            raise ValueError("S7 点位缺少 protocol_options.host")
        client = self._client_factory()
        try:
            client.connect(host, int(options.get("rack", 0)), int(options.get("slot", 1)))
            payload = client.db_read(address.db_number, address.offset, 4)
            return RawPointValue(
                binding=binding,
                value=decode_s7_value(payload, address.value_type),
                quality=1.0,
                acquired_at=datetime.now(timezone.utc),
                raw_status="good",
                raw_payload={"protocol": self.protocol, "address": binding.source_address},
            )
        finally:
            client.disconnect()


def _build_client() -> Any:
    try:
        from snap7.client import Client
    except ImportError as exc:
        raise RuntimeError("缺少 python-snap7，请安装边缘采集依赖") from exc
    return Client()
