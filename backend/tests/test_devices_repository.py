from app.repositories import maintenance_repository


def test_fetch_devices_uses_one_latest_prediction_per_device() -> None:
    source = maintenance_repository.fetch_devices.__code__.co_consts
    query = next(item for item in source if isinstance(item, str) and "FROM devices d" in item)

    assert "ROW_NUMBER() OVER" in query
    assert "PARTITION BY device_code" in query
    assert "rn = 1" in query
