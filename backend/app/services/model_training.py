from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, replace
from pathlib import Path

from app.models.model_suite import Ai4iModelSuite, ModelMetric, train_ai4i_model_suite
from app.models.registry import model_feature_dependencies, save_active_model_suite
from app.repositories.maintenance_repository import (
    ensure_baseline_model,
    ensure_prediction_model_schema,
    replace_model_feature_dependencies,
    upsert_model_metric,
)
from app.training_data.archive import Ai4iDailyArchive, get_default_archive, resolve_base_dataset_path
from app.training_data.schema import (
    AI4I_BASE_UDI_MAX,
    AI4I_REQUIRED_FIELDS,
    DAILY_UDI_OFFSET,
    validate_ai4i_row,
)
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelTrainingResult:
    suite: Ai4iModelSuite
    trained_rows: int
    version: str | None = None
    source_files: list[str] | None = None


def train_and_register_ai4i_model(
    db: Session,
    rows: list[dict[str, str]],
    *,
    version: str | None = None,
) -> ModelTrainingResult:
    if not rows:
        raise ValueError("AI4I 训练数据为空")

    ensure_prediction_model_schema(db)
    ensure_baseline_model(db)
    suite = train_ai4i_model_suite(rows)
    if version:
        suite = _suite_with_version(suite, version)
    resolved_version = version or next((metric.version for metric in suite.metrics if metric.version), "1.0.0")
    for metric in suite.metrics:
        upsert_model_metric(
            db,
            model_name=metric.model_name,
            model_type=metric.model_type,
            version=metric.version,
            metric_name=metric.metric_name,
            metric_value=metric.metric_value,
        )
    for dependency in model_feature_dependencies(suite):
        replace_model_feature_dependencies(
            db,
            model_name=str(dependency["model_name"]),
            version=str(dependency["version"]),
            features=list(dependency["features"]),
        )
    save_active_model_suite(suite)
    return ModelTrainingResult(suite=suite, trained_rows=len(rows), version=resolved_version)


def load_full_ai4i_training_rows(
    *,
    base_dataset_path: Path | str | None = None,
    archive: Ai4iDailyArchive | None = None,
) -> tuple[list[dict[str, str]], list[str]]:
    """Load base CSV + all materialized daily CSVs, validate fields, dedupe by UDI."""
    source_files: list[str] = []
    rows: list[dict[str, str]] = []

    base_path = Path(base_dataset_path) if base_dataset_path is not None else resolve_base_dataset_path()
    if base_path.exists():
        base_rows = _read_csv_rows(base_path)
        _validate_rows(base_rows, source=str(base_path))
        rows.extend(base_rows)
        source_files.append(str(base_path))
    else:
        logger.warning("AI4I base dataset missing: %s", base_path)

    daily_archive = archive or get_default_archive()
    for csv_path in daily_archive.list_materialized_csv_files():
        daily_rows = _read_csv_rows(csv_path)
        _validate_rows(daily_rows, source=str(csv_path))
        rows.extend(daily_rows)
        source_files.append(str(csv_path))

    deduped = _dedupe_by_udi(rows)
    if not deduped:
        raise ValueError("全量二次训练数据为空：请确认 base 数据集或已物化日归档 CSV 存在")
    return deduped, source_files


def retrain_ai4i_from_archive(
    db: Session,
    *,
    version: str,
    base_dataset_path: Path | str | None = None,
    archive: Ai4iDailyArchive | None = None,
) -> ModelTrainingResult:
    """Full retrain: base + all materialized daily files, unique job/artifact version."""
    rows, source_files = load_full_ai4i_training_rows(
        base_dataset_path=base_dataset_path,
        archive=archive,
    )
    result = train_and_register_ai4i_model(db, rows, version=version)
    return ModelTrainingResult(
        suite=result.suite,
        trained_rows=result.trained_rows,
        version=result.version,
        source_files=source_files,
    )


def _suite_with_version(suite: Ai4iModelSuite, version: str) -> Ai4iModelSuite:
    metrics = [
        replace(metric, version=version) if isinstance(metric, ModelMetric) else metric
        for metric in suite.metrics
    ]
    return Ai4iModelSuite(
        classifier=suite.classifier,
        anomaly_detector=suite.anomaly_detector,
        rul_regressor=suite.rul_regressor,
        metrics=metrics,
        feature_importance=suite.feature_importance,
    )


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [{str(k): str(v) for k, v in row.items() if k is not None} for row in csv.DictReader(handle)]


def _validate_rows(rows: list[dict[str, str]], *, source: str) -> None:
    for index, row in enumerate(rows):
        missing = [name for name in AI4I_REQUIRED_FIELDS if name not in row]
        if missing:
            # Base AI4I may omit nothing; tolerate optional mode flags if present as empty after pad
            for name in missing:
                if name in {"TWF", "HDF", "PWF", "OSF", "RNF"}:
                    row[name] = row.get(name) or "0"
                else:
                    raise ValueError(f"{source} 第 {index + 1} 行缺少字段：{', '.join(missing)}")
        try:
            validate_ai4i_row(row)
        except ValueError as exc:
            raise ValueError(f"{source} 第 {index + 1} 行无效：{exc}") from exc


def _dedupe_by_udi(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Dedupe by UDI. Daily archive UDIs use DAILY_UDI_OFFSET and do not collide with base 1..10000."""
    seen: dict[str, int] = {}
    result: list[dict[str, str]] = []
    for row in rows:
        udi = str(row.get("UDI", "")).strip()
        if udi and udi in seen:
            # Later rows (daily after base) win for the same UDI.
            result[seen[udi]] = row
            continue
        if udi:
            seen[udi] = len(result)
        result.append(row)
    return result


def assert_daily_udi_outside_base_band(udi: int | str) -> None:
    """Guard used by tests/callers: archived telemetry UDI must not sit in AI4I 1..10000."""
    value = int(udi)
    if value <= AI4I_BASE_UDI_MAX:
        raise ValueError(f"日归档 UDI={value} 落入 base 区间 1..{AI4I_BASE_UDI_MAX}")
    if value < DAILY_UDI_OFFSET:
        raise ValueError(f"日归档 UDI={value} 低于偏移 {DAILY_UDI_OFFSET}")
