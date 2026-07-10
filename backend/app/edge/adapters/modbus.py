from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.edge.adapters.parsing import decode_modbus_registers, parse_modbus_address
from app.edge.contracts import EdgePointBinding, RawPointValue


class ModbusAdapter:
    protocol = "modbus"

    def __init__(self, client_factory: Callable[..., Any] | None = None) -> None:
        self._client_factory = client_factory or _build_client

    def read(self, binding: EdgePointBinding) -> RawPointValue:
        address = parse_modbus_address(binding.source_address)
        options = binding.protocol_options
        client = self._client_factory(**options)
        try:
            if not client.connect():
                raise RuntimeError("无法连接 Modbus 设备")
            response = _read_registers(client, address, int(options.get("unit_id", 1)))
            if response.isError():
                raise RuntimeError(f"Modbus 读取失败：{response}")
            value = decode_modbus_registers(response.registers, address.value_type, address.scale)
            return RawPointValue(
                binding=binding,
                value=value,
                quality=1.0,
                acquired_at=datetime.now(UTC),
                raw_status="good",
                raw_payload={"protocol": self.protocol, "address": binding.source_address},
            )
        finally:
            client.close()


def _read_registers(client: Any, address, unit_id: int) -> Any:
    count = 2 if address.value_type in {"int32", "uint32", "float32"} else 1
    if address.area == "holding":
        reader = client.read_holding_registers
    elif address.area == "input":
        reader = client.read_input_registers
    else:
        raise ValueError(f"{address.area} 不支持数值寄存器读取")
    return reader(address.offset, count=count, device_id=unit_id)


def _build_client(**options: Any) -> Any:
    transport = str(options.get("transport") or "tcp").lower()
    try:
        if transport == "tcp":
            from pymodbus.client import ModbusTcpClient

            return ModbusTcpClient(
                host=str(options["host"]),
                port=int(options.get("port", 502)),
                timeout=float(options.get("timeout_seconds", 3)),
            )
        if transport == "rtu":
            from pymodbus.client import ModbusSerialClient

            return ModbusSerialClient(
                port=str(options["serial_port"]),
                baudrate=int(options.get("baudrate", 9600)),
                parity=str(options.get("parity", "N")),
                stopbits=int(options.get("stopbits", 1)),
                bytesize=int(options.get("bytesize", 8)),
                timeout=float(options.get("timeout_seconds", 3)),
            )
    except ImportError as exc:
        raise RuntimeError("缺少 pymodbus，请安装边缘采集依赖") from exc
    raise ValueError(f"不支持的 Modbus 传输方式：{transport}")
