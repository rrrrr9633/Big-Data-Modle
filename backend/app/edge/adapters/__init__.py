from __future__ import annotations

from typing import Protocol

from app.edge.adapters.cnc import CncAdapter
from app.edge.adapters.modbus import ModbusAdapter
from app.edge.adapters.opcua import OpcUaAdapter
from app.edge.adapters.s7 import S7Adapter
from app.edge.contracts import EdgePointBinding, EdgeProtocol, RawPointValue


class EdgeProtocolAdapter(Protocol):
    protocol: str

    def read(self, binding: EdgePointBinding) -> RawPointValue: ...


ADAPTERS: dict[EdgeProtocol, EdgeProtocolAdapter] = {
    "modbus": ModbusAdapter(),
    "opcua": OpcUaAdapter(),
    "s7": S7Adapter(),
    "cnc": CncAdapter(),
}


def get_adapter(protocol: EdgeProtocol) -> EdgeProtocolAdapter:
    return ADAPTERS[protocol]
