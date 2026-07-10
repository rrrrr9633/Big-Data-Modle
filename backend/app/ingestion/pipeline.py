from app.schemas.timeseries import SensorReading


def parse_historical_rows(rows: list[dict]) -> list[SensorReading]:
    return [SensorReading.model_validate(row) for row in rows]


def simulate_realtime_reading(reading: SensorReading) -> SensorReading:
    return reading