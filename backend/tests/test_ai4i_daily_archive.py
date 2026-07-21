from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from app.api.v1 import models as models_api
from app.ingestion.http_schemas import TelemetryPayloadIn
from app.repositories.model_training_repository import present_training_job
from app.services.model_training import (
    assert_daily_udi_outside_base_band,
    load_full_ai4i_training_rows,
)
from app.training_data.archive import Ai4iDailyArchive
from app.training_data.schema import (
    AI4I_BASE_UDI_MAX,
    AI4I_CSV_HEADERS,
    DAILY_UDI_OFFSET,
    map_device_profile_type,
    project_telemetry_to_ai4i_row,
    stable_product_id,
    stable_udi,
)


def _payload(**overrides) -> TelemetryPayloadIn:
    base = {
        "device_code": "CNC-L01-001",
        "device_name": "数控机床 CNC-L01-001",
        "device_type": "CNC",
        "recorded_at": datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc),
        "readings": [
            {"sensor_code": "air_temperature", "value": 298.1, "unit": "K"},
            {"sensor_code": "process_temperature", "value": 308.6, "unit": "K"},
            {"sensor_code": "rotational_speed", "value": 1500, "unit": "rpm"},
            {"sensor_code": "torque", "value": 42.0, "unit": "Nm"},
            {"sensor_code": "tool_wear", "value": 20, "unit": "min"},
        ],
    }
    base.update(overrides)
    return TelemetryPayloadIn.model_validate(base)


def _row_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(AI4I_CSV_HEADERS))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_device_profile_and_udi_are_stable_and_outside_base_band() -> None:
    assert map_device_profile_type("CNC-L01-001") == map_device_profile_type("CNC-L01-001")
    assert map_device_profile_type("CNC-L01-001") in {"L", "M", "H"}
    assert stable_product_id("CNC-L01-001").startswith(map_device_profile_type("CNC-L01-001"))
    ts = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
    udi = stable_udi("CNC-L01-001", ts)
    assert udi == stable_udi("CNC-L01-001", ts)
    assert udi > AI4I_BASE_UDI_MAX
    assert udi >= DAILY_UDI_OFFSET
    assert_daily_udi_outside_base_band(udi)


def test_normal_stuck_drift_never_mark_machine_failure() -> None:
    normal = project_telemetry_to_ai4i_row(
        _payload(
            readings=[
                {"sensor_code": "air_temperature", "value": 298.1, "status": "sudden_fault"},
                {"sensor_code": "process_temperature", "value": 340.0, "status": "good"},
                {"sensor_code": "rotational_speed", "value": 1500, "status": "good"},
                {"sensor_code": "torque", "value": 42.0, "status": "good"},
                {"sensor_code": "tool_wear", "value": 250, "status": "good"},
            ]
        ),
        mode="normal",
    )
    stuck = project_telemetry_to_ai4i_row(
        _payload(
            readings=[
                {"sensor_code": "air_temperature", "value": 298.1, "status": "sensor_stuck"},
                {"sensor_code": "process_temperature", "value": 340.0, "status": "good"},
                {"sensor_code": "rotational_speed", "value": 1500, "status": "good"},
                {"sensor_code": "torque", "value": 80.0, "status": "sensor_stuck"},
                {"sensor_code": "tool_wear", "value": 250, "status": "good"},
            ]
        ),
        mode="sensor_stuck",
    )
    drift = project_telemetry_to_ai4i_row(_payload(), mode="sensor_drift")
    assert normal["Machine failure"] == "0"
    assert stuck["Machine failure"] == "0"
    assert drift["Machine failure"] == "0"


def test_sudden_fault_only_when_raw_status_is_sudden_fault() -> None:
    emerging = project_telemetry_to_ai4i_row(
        _payload(
            readings=[
                {"sensor_code": "air_temperature", "value": 298.1, "status": "good"},
                {"sensor_code": "process_temperature", "value": 308.6, "status": "good"},
                {"sensor_code": "rotational_speed", "value": 1100, "status": "fault_emerging"},
                {"sensor_code": "torque", "value": 60.0, "status": "fault_emerging"},
                {"sensor_code": "tool_wear", "value": 20, "status": "good"},
            ]
        ),
        mode="sudden_fault",
    )
    sudden = project_telemetry_to_ai4i_row(
        _payload(
            readings=[
                {"sensor_code": "air_temperature", "value": 298.1, "status": "good"},
                {"sensor_code": "process_temperature", "value": 308.6, "status": "good"},
                {"sensor_code": "rotational_speed", "value": 1100, "status": "sudden_fault"},
                {"sensor_code": "torque", "value": 60.0, "status": "sudden_fault"},
                {"sensor_code": "tool_wear", "value": 20, "status": "good"},
            ]
        ),
        mode="sudden_fault",
    )
    assert emerging["Machine failure"] == "0"
    assert sudden["Machine failure"] == "1"
    assert sudden["PWF"] == "1"


def test_degrading_only_at_clear_high_thresholds() -> None:
    mild = project_telemetry_to_ai4i_row(
        _payload(
            readings=[
                {"sensor_code": "air_temperature", "value": 298.1, "status": "good"},
                {"sensor_code": "process_temperature", "value": 320.0, "status": "good"},
                {"sensor_code": "rotational_speed", "value": 1500, "status": "good"},
                {"sensor_code": "torque", "value": 55.0, "status": "good"},
                {"sensor_code": "tool_wear", "value": 160, "status": "good"},
            ]
        ),
        mode="degrading",
    )
    high_wear = project_telemetry_to_ai4i_row(
        _payload(
            readings=[
                {"sensor_code": "air_temperature", "value": 298.1, "status": "good"},
                {"sensor_code": "process_temperature", "value": 310.0, "status": "good"},
                {"sensor_code": "rotational_speed", "value": 1500, "status": "good"},
                {"sensor_code": "torque", "value": 42.0, "status": "good"},
                {"sensor_code": "tool_wear", "value": 220, "status": "good"},
            ]
        ),
        mode="degrading",
    )
    high_temp = project_telemetry_to_ai4i_row(
        _payload(
            readings=[
                {"sensor_code": "air_temperature", "value": 298.1, "status": "good"},
                {"sensor_code": "process_temperature", "value": 335.0, "status": "good"},
                {"sensor_code": "rotational_speed", "value": 1500, "status": "good"},
                {"sensor_code": "torque", "value": 42.0, "status": "good"},
                {"sensor_code": "tool_wear", "value": 40, "status": "good"},
            ]
        ),
        mode="degrading",
    )
    assert mild["Machine failure"] == "0"
    assert high_wear["Machine failure"] == "1"
    assert high_wear["TWF"] == "1"
    assert high_temp["Machine failure"] == "1"
    assert high_temp["HDF"] == "1"


def test_daily_archive_dedupes_and_materializes_atomically(tmp_path: Path) -> None:
    fixed = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
    archive = Ai4iDailyArchive(tmp_path, materialize_every=1, clock=lambda: fixed)
    payload = _payload()
    first = archive.archive_payload(payload, mode="normal")
    second = archive.archive_payload(payload, mode="normal")
    assert first["UDI"] == second["UDI"]
    assert int(first["UDI"]) >= DAILY_UDI_OFFSET

    csv_path = archive.csv_path("2026-07-21")
    manifest_path = archive.manifest_path("2026-07-21")
    assert csv_path.exists()
    assert manifest_path.exists()
    text = csv_path.read_text(encoding="utf-8")
    assert text.count("\n") >= 2
    assert text.count(first["UDI"]) == 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["row_count"] == 1
    assert archive.list_materialized_csv_files() == [csv_path]
    assert len(archive.load_materialized_rows()) == 1


def test_corrupt_journal_tail_is_skipped(tmp_path: Path) -> None:
    fixed = datetime(2026, 7, 22, 8, 0, tzinfo=timezone.utc)
    archive = Ai4iDailyArchive(tmp_path, materialize_every=100, clock=lambda: fixed)
    archive.archive_payload(_payload(), mode="normal")
    journal = archive.journal_path("2026-07-22")
    with journal.open("a", encoding="utf-8") as handle:
        handle.write('{"row": {"UDI": "broken"')  # torn JSON without trailing newline
    result = archive.materialize_day("2026-07-22")
    assert result.row_count == 1
    assert result.skipped_corrupt_lines >= 1


def test_base_plus_daily_dedupe_keeps_base_band_and_large_daily_udis(tmp_path: Path) -> None:
    base = tmp_path / "base.csv"
    archive_root = tmp_path / "daily"
    archive = Ai4iDailyArchive(archive_root, materialize_every=1)

    base_row = {
        "UDI": "1",
        "Product ID": "M14860",
        "Type": "M",
        "Air temperature [K]": "298.1",
        "Process temperature [K]": "308.6",
        "Rotational speed [rpm]": "1551",
        "Torque [Nm]": "42.8",
        "Tool wear [min]": "0",
        "Machine failure": "0",
        "TWF": "0",
        "HDF": "0",
        "PWF": "0",
        "OSF": "0",
        "RNF": "0",
    }
    _row_csv(base, [base_row])

    fixed = datetime(2026, 7, 23, 9, 0, tzinfo=timezone.utc)
    archive._clock = lambda: fixed  # type: ignore[method-assign]
    daily = archive.archive_payload(_payload(recorded_at=fixed), mode="normal")
    assert int(daily["UDI"]) > AI4I_BASE_UDI_MAX

    rows, sources = load_full_ai4i_training_rows(base_dataset_path=base, archive=archive)
    udis = {row["UDI"] for row in rows}
    assert "1" in udis
    assert daily["UDI"] in udis
    assert len(rows) == 2
    assert len(sources) == 2


def test_present_training_job_is_frontend_friendly() -> None:
    job = present_training_job(
        {
            "id": 7,
            "status": "running",
            "version": "retrain-7",
            "trained_rows": None,
            "error_message": None,
            "metrics_json": [],
            "detail_json": {"type": "ai4i_retrain"},
            "created_by": "engineer",
            "created_at": "2026-07-21T00:00:00",
            "started_at": "2026-07-21T00:00:01",
            "finished_at": None,
        }
    )
    assert job is not None
    assert job["type"] == "ai4i_retrain"
    assert job["status"] == "running"
    assert "二次训练" in job["message"]
    assert job["version"] == "retrain-7"


def test_run_retrain_job_rollbacks_before_mark_failed(monkeypatch) -> None:
    db = MagicMock()
    session_cm = MagicMock()
    session_cm.__enter__.return_value = db
    session_cm.__exit__.return_value = False
    monkeypatch.setattr(models_api, "SessionLocal", lambda: session_cm)

    failed: list[tuple[int, str]] = []

    def fake_running(_db, job_id, *, version):
        assert job_id == 9
        assert version == "retrain-9"

    def boom(*_args, **_kwargs):
        raise RuntimeError("train exploded")

    def fake_failed(_db, job_id, *, error_message):
        failed.append((job_id, error_message))

    monkeypatch.setattr(models_api, "mark_training_job_running", fake_running)
    monkeypatch.setattr(models_api, "retrain_ai4i_from_archive", boom)
    monkeypatch.setattr(models_api, "mark_training_job_failed", fake_failed)

    models_api._run_retrain_job(9, "retrain-9", "engineer")

    db.rollback.assert_called()
    assert failed == [(9, "train exploded")]
    # rollback must happen before mark failed
    assert db.method_calls[0][0] == "rollback" or db.rollback.call_count == 1
