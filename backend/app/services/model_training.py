from __future__ import annotations

from dataclasses import dataclass

from app.models.model_suite import Ai4iModelSuite, train_ai4i_model_suite
from app.models.registry import model_feature_dependencies, save_active_model_suite
from app.repositories.maintenance_repository import (
    ensure_baseline_model,
    ensure_prediction_model_schema,
    replace_model_feature_dependencies,
    upsert_model_metric,
)
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ModelTrainingResult:
    suite: Ai4iModelSuite
    trained_rows: int


def train_and_register_ai4i_model(
    db: Session,
    rows: list[dict[str, str]],
) -> ModelTrainingResult:
    if not rows:
        raise ValueError("AI4I 训练数据为空")

    ensure_prediction_model_schema(db)
    ensure_baseline_model(db)
    suite = train_ai4i_model_suite(rows)
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
    return ModelTrainingResult(suite=suite, trained_rows=len(rows))