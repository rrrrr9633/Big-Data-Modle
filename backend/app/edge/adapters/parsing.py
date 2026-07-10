from __future__ import annotations

import re
import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class ModbusAddress:
    area: str
    offset: int
    value_type: str
    scale: float


@dataclass(frozen=True)
class S7Address:
    db_number: int
    offset: int
    value_type: str


def parse_modbus_address(source_address: str) -> ModbusAddress:
    parts = [part.strip() for part in source_address.split(":") if part.strip()]
    if len(parts) < 3:
        raise ValueError("Modbus 地址必须为 area:address:type[:scale=value]")
    area, address_text, value_type = parts[:3]
    if area not in {"coil", "discrete", "holding", "input"}:
        raise ValueError(f"不支持的 Modbus 区域：{area}")
    address = int(address_text)
    offset = address - 40001 if area == "holding" and address >= 40001 else address
    scale = 1.0
    for part in parts[3:]:
        if part.startswith("scale="):
            scale = float(part.removeprefix("scale="))
    if value_type not in {"int16", "uint16", "int32", "uint32", "float32"}:
        raise ValueError(f"不支持的 Modbus 数据类型：{value_type}")
    return ModbusAddress(area=area, offset=offset, value_type=value_type, scale=scale)


def decode_modbus_registers(registers: list[int], value_type: str, scale: float = 1.0) -> float:
    needed = 2 if value_type in {"int32", "uint32", "float32"} else 1
    if len(registers) < needed:
        raise ValueError(f"Modbus 返回寄存器不足：需要 {needed}，实际 {len(registers)}")
    raw = b"".join(
        int(register).to_bytes(2, byteorder="big", signed=False) for register in registers[:needed]
    )
    formats = {"int16": ">h", "uint16": ">H", "int32": ">i", "uint32": ">I", "float32": ">f"}
    return round(float(struct.unpack(formats[value_type], raw)[0]) * scale, 6)


def parse_s7_address(source_address: str) -> S7Address:
    match = re.fullmatch(
        r"DB(\d+)\.DBD(\d+):(float|int32|uint32)", source_address.strip(), re.IGNORECASE
    )
    if not match:
        raise ValueError("S7 地址必须为 DB<编号>.DBD<偏移>:float|int32|uint32")
    return S7Address(
        db_number=int(match.group(1)),
        offset=int(match.group(2)),
        value_type=match.group(3).lower(),
    )


def decode_s7_value(payload: bytes, value_type: str) -> float:
    formats = {"float": ">f", "int32": ">i", "uint32": ">I"}
    if len(payload) != 4:
        raise ValueError(f"S7 返回字节数错误：期望 4，实际 {len(payload)}")
    return round(float(struct.unpack(formats[value_type], payload)[0]), 6)
