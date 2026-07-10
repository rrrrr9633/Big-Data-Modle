from __future__ import annotations

from app.edge.adapters.modbus import ModbusAdapter
from app.edge.adapters.opcua import OpcUaAdapter
from app.edge.adapters.s7 import S7Adapter
from app.edge.contracts import EdgeAdapterConfig, EdgePointBinding
from app.edge.runner import EdgeRunner


class FakeModbusResponse:
    registers = [123]

    def isError(self) -> bool:
        return False


class FakeModbusClient:
    def __init__(self) -> None:
        self.connected = False
        self.closed = False

    def connect(self) -> bool:
        self.connected = True
        return True

    def read_holding_registers(
        self, address: int, *, count: int, device_id: int
    ) -> FakeModbusResponse:
        assert address == 0
        assert count == 1
        assert device_id == 1
        return FakeModbusResponse()

    def close(self) -> None:
        self.closed = True


def test_modbus_tcp_adapter_reads_configured_register_and_scales_value() -> None:
    client = FakeModbusClient()
    adapter = ModbusAdapter(client_factory=lambda **_options: client)
    binding = EdgePointBinding(
        device_code="CNC-001",
        point_code="spindle_temperature",
        protocol="modbus",
        source_address="holding:40001:uint16:scale=0.1",
        protocol_options={"transport": "tcp", "host": "192.168.10.5", "port": 502, "unit_id": 1},
    )

    reading = adapter.read(binding)

    assert client.connected is True
    assert client.closed is True
    assert reading.value == 12.3
    assert reading.quality == 1.0
    assert reading.raw_status == "good"


class FakeOpcNode:
    def read_value(self) -> float:
        return 37.5


class FakeOpcClient:
    def __init__(self) -> None:
        self.endpoint = ""
        self.connected = False
        self.disconnected = False

    def connect(self) -> None:
        self.connected = True

    def get_node(self, node_id: str) -> FakeOpcNode:
        assert node_id == "ns=2;s=CNC001.Spindle.Temp"
        return FakeOpcNode()

    def disconnect(self) -> None:
        self.disconnected = True


def test_opcua_adapter_reads_configured_node() -> None:
    client = FakeOpcClient()
    adapter = OpcUaAdapter(client_factory=lambda endpoint: client)
    binding = EdgePointBinding(
        device_code="CNC-001",
        point_code="spindle_temperature",
        protocol="opcua",
        source_address="ns=2;s=CNC001.Spindle.Temp",
        protocol_options={"endpoint": "opc.tcp://192.168.10.6:4840"},
    )

    reading = adapter.read(binding)

    assert client.connected is True
    assert client.disconnected is True
    assert reading.value == 37.5
    assert reading.raw_status == "good"


class FakeS7Client:
    def __init__(self) -> None:
        self.connection = None
        self.disconnected = False

    def connect(self, host: str, rack: int, slot: int) -> None:
        self.connection = (host, rack, slot)

    def db_read(self, db_number: int, offset: int, size: int) -> bytes:
        assert (db_number, offset, size) == (1, 0, 4)
        return b"\x41\x48\x00\x00"

    def disconnect(self) -> None:
        self.disconnected = True


def test_s7_adapter_reads_configured_db_float() -> None:
    client = FakeS7Client()
    adapter = S7Adapter(client_factory=lambda: client)
    binding = EdgePointBinding(
        device_code="CNC-001",
        point_code="axis_x",
        protocol="s7",
        source_address="DB1.DBD0:float",
        protocol_options={"host": "192.168.10.7", "rack": 0, "slot": 1},
    )

    reading = adapter.read(binding)

    assert client.connection == ("192.168.10.7", 0, 1)
    assert client.disconnected is True
    assert reading.value == 12.5
    assert reading.raw_status == "good"


def test_edge_runner_collects_and_publishes_loaded_gateway_config() -> None:
    config = EdgeAdapterConfig.model_validate(
        {
            "gateway": {
                "gateway_id": "gateway-cnc-001",
                "mqtt_topic": "factory/a/workshop/b/line/c/machine/CNC-001/telemetry",
            },
            "points": [],
            "payload_schema": ["event_id"],
            "runtime_contract": {},
        }
    )
    calls: list[object] = []
    runner = EdgeRunner(
        config,
        collector=lambda loaded: calls.append(loaded.gateway.gateway_id) or ["event"],
        publisher=lambda events, gateway: (
            calls.append((events, gateway.mqtt_topic)) or {"status": "accepted"}
        ),
    )

    result = runner.run_once()

    assert result == {"status": "accepted"}
    assert calls == ["gateway-cnc-001", (["event"], config.gateway.mqtt_topic)]
