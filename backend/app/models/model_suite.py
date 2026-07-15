from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import shap
from app.models.health_score import calculate_health_score, risk_level_from_score
from app.schemas.timeseries import PredictionResult, TimeSeriesWindow
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

AI4I_FEATURE_COLUMNS: tuple[str, ...] = (
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
)
AI4I_SENSOR_FEATURE_MAP: tuple[tuple[str, str], ...] = (
    ("Air temperature [K]", "sensor_latest_air_temperature"),
    ("Process temperature [K]", "sensor_latest_process_temperature"),
    ("Rotational speed [rpm]", "sensor_latest_rotational_speed"),
    ("Torque [Nm]", "sensor_latest_torque"),
    ("Tool wear [min]", "sensor_latest_tool_wear"),
)
TARGET_COLUMN = "Machine failure"
RUL_LABEL_SOURCE = "tool_wear_failure_proxy"


@dataclass(frozen=True)
class ModelMetric:
    model_name: str
    model_type: str
    version: str
    metric_name: str
    metric_value: float


@dataclass(frozen=True)
class RiskExplanation:
    feature_name: str
    feature_value: float
    contribution: float


@dataclass(frozen=True)
class Ai4iModelSuite:
    classifier: LGBMClassifier
    anomaly_detector: IsolationForest
    rul_regressor: LGBMRegressor
    metrics: list[ModelMetric]
    feature_importance: list[RiskExplanation]


def train_ai4i_model_suite(rows: list[dict[str, str]]) -> Ai4iModelSuite:
    x = _features_from_rows(rows)
    y = _target_from_rows(rows)
    _assert_trainable_dataset(x, y)

    metrics: list[ModelMetric] = []

    classifier, classifier_metrics = _train_lightgbm_classifier(x, y)
    metrics.extend(classifier_metrics)

    anomaly_detector, anomaly_metrics = _train_isolation_forest(x)
    metrics.extend(anomaly_metrics)

    rul_target = _rul_target_from_rows(rows, y)
    rul_regressor, rul_metrics = _train_lightgbm_rul(x, rul_target)
    metrics.extend(rul_metrics)

    feature_importance = _explain_global_importance(classifier, x)
    metrics.extend(_explanation_metrics(feature_importance))
    metrics.append(_metric("lightgbm-rul-regressor", "regression", RUL_LABEL_SOURCE, 1.0))

    return Ai4iModelSuite(
        classifier=classifier,
        anomaly_detector=anomaly_detector,
        rul_regressor=rul_regressor,
        metrics=metrics,
        feature_importance=feature_importance,
    )


def model_suite_version(suite: Ai4iModelSuite) -> str:
    return next((metric.version for metric in suite.metrics if metric.version), "unknown")


def predict_ai4i_feature_row(
    *,
    device_id: str,
    feature_values: dict[str, float],
    suite: Ai4iModelSuite,
    forced_failure: bool = False,
) -> PredictionResult:
    feature_vector = [feature_values[column] for column in AI4I_FEATURE_COLUMNS]
    probability = _predict_failure_probability(feature_vector, suite.classifier)
    anomaly_score, anomaly_reasons = _predict_anomaly(feature_vector, suite.anomaly_detector)
    quality_score = 1.0
    trend_factor = 0.0
    health_score = calculate_health_score(
        failure_probability=probability,
        anomaly_score=anomaly_score,
        trend_factor=trend_factor,
        quality_score=quality_score,
    )
    risk_level = risk_level_from_score(health_score, probability, anomaly_score)
    result = PredictionResult(
        device_id=device_id,
        failure_probability=probability,
        health_score=health_score,
        risk_level=risk_level,
        anomaly_score=anomaly_score,
        anomaly_reasons=anomaly_reasons,
        trend_factor=trend_factor,
        quality_score=quality_score,
        rul_hours=_predict_rul(feature_vector, suite.rul_regressor),
    )
    if forced_failure:
        result.failure_probability = max(result.failure_probability, 0.85)
        result.health_score = min(result.health_score, 35)
        result.risk_level = "critical"
        result.rul_hours = min(result.rul_hours or 24, 24)
    return result


def explain_ai4i_feature_row(
    *,
    feature_values: dict[str, float],
    suite: Ai4iModelSuite,
) -> list[RiskExplanation]:
    feature_vector = [feature_values[column] for column in AI4I_FEATURE_COLUMNS]
    shap_values = _positive_class_shap_values(
        shap.TreeExplainer(suite.classifier).shap_values(np.array([feature_vector]))
    )
    values = shap_values[0] if shap_values.ndim == 2 else shap_values
    explanations = [
        RiskExplanation(
            feature_name=feature,
            feature_value=float(value),
            contribution=float(contribution),
        )
        for feature, value, contribution in zip(
            AI4I_FEATURE_COLUMNS,
            feature_vector,
            values,
            strict=True,
        )
    ]
    return sorted(explanations, key=lambda item: abs(item.contribution), reverse=True)


def predict_with_model_suite(window: TimeSeriesWindow, suite: Ai4iModelSuite) -> PredictionResult:
    feature_vector = _window_vector(window)
    probability = _predict_failure_probability(feature_vector, suite.classifier)
    anomaly_score, anomaly_reasons = _predict_anomaly(feature_vector, suite.anomaly_detector)
    trend_factor = abs(window.feature_values.get("trend", 0.0)) / 2
    quality_score = window.feature_values.get("quality_mean", 1.0)
    health_score = calculate_health_score(
        failure_probability=probability,
        anomaly_score=anomaly_score,
        trend_factor=trend_factor,
        quality_score=quality_score,
    )
    risk_level = risk_level_from_score(health_score, probability, anomaly_score)

    return PredictionResult(
        device_id=window.device_id,
        failure_probability=probability,
        health_score=health_score,
        risk_level=risk_level,
        anomaly_score=anomaly_score,
        anomaly_reasons=anomaly_reasons,
        trend_factor=trend_factor,
        quality_score=quality_score,
        rul_hours=_predict_rul(feature_vector, suite.rul_regressor),
    )


def explain_prediction(window: TimeSeriesWindow, suite: Ai4iModelSuite) -> list[RiskExplanation]:
    feature_vector = _window_vector(window)
    shap_values = _positive_class_shap_values(
        shap.TreeExplainer(suite.classifier).shap_values(np.array([feature_vector]))
    )
    values = shap_values[0] if shap_values.ndim == 2 else shap_values
    explanations = [
        RiskExplanation(
            feature_name=feature,
            feature_value=float(value),
            contribution=float(contribution),
        )
        for feature, value, contribution in zip(
            AI4I_FEATURE_COLUMNS,
            feature_vector,
            values,
            strict=True,
        )
    ]
    return sorted(explanations, key=lambda item: abs(item.contribution), reverse=True)


def _train_lightgbm_classifier(
    x: np.ndarray,
    y: np.ndarray,
) -> tuple[LGBMClassifier, list[ModelMetric]]:
    model_name = "lightgbm-fault-classifier"
    x_train, x_test, y_train, y_test = _split_supervised_dataset(x, y)
    model = LGBMClassifier(
        n_estimators=120,
        learning_rate=0.06,
        num_leaves=15,
        min_child_samples=3,
        class_weight="balanced",
        random_state=42,
        verbosity=-1,
    )
    model.fit(x_train, y_train)
    predicted = model.predict(x_test)
    probabilities = model.predict_proba(x_test)[:, 1]

    return model, [
        _metric(model_name, "classification", "accuracy", accuracy_score(y_test, predicted)),
        _metric(
            model_name,
            "classification",
            "precision",
            precision_score(y_test, predicted, zero_division=0),
        ),
        _metric(
            model_name,
            "classification",
            "recall",
            recall_score(y_test, predicted, zero_division=0),
        ),
        _metric(model_name, "classification", "f1", f1_score(y_test, predicted, zero_division=0)),
        _metric(model_name, "classification", "auc", _safe_auc(y_test, probabilities)),
        _metric(model_name, "classification", "sample_count", float(len(x))),
    ]


def _train_isolation_forest(x: np.ndarray) -> tuple[IsolationForest, list[ModelMetric]]:
    model_name = "isolation-forest-anomaly"
    model = IsolationForest(
        n_estimators=150,
        contamination="auto",
        random_state=42,
    )
    model.fit(x)
    anomaly_rate = float(np.mean(model.predict(x) == -1))
    score_mean = float(np.mean(_isolation_scores(model, x)))
    return model, [
        _metric(model_name, "anomaly_detection", "anomaly_rate", anomaly_rate),
        _metric(model_name, "anomaly_detection", "score_mean", score_mean),
        _metric(model_name, "anomaly_detection", "sample_count", float(len(x))),
    ]


def _train_lightgbm_rul(
    x: np.ndarray,
    y: np.ndarray,
) -> tuple[LGBMRegressor, list[ModelMetric]]:
    model_name = "lightgbm-rul-regressor"
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.35 if len(x) >= 12 else 0.5,
        random_state=42,
    )
    model = LGBMRegressor(
        n_estimators=120,
        learning_rate=0.06,
        num_leaves=15,
        min_child_samples=3,
        random_state=42,
        verbosity=-1,
    )
    model.fit(x_train, y_train)
    predicted = model.predict(x_test)
    return model, [
        _metric(model_name, "regression", "mae", mean_absolute_error(y_test, predicted)),
        _metric(model_name, "regression", "r2", _safe_r2(y_test, predicted)),
        _metric(model_name, "regression", "sample_count", float(len(x))),
    ]


def _features_from_rows(rows: list[dict[str, str]]) -> np.ndarray:
    if not rows:
        return np.empty((0, len(AI4I_FEATURE_COLUMNS)))
    return np.array(
        [[float(row[column]) for column in AI4I_FEATURE_COLUMNS] for row in rows],
        dtype=float,
    )


def _target_from_rows(rows: list[dict[str, str]]) -> np.ndarray:
    return np.array([int(row.get(TARGET_COLUMN, "0") or 0) for row in rows], dtype=int)


def _window_vector(window: TimeSeriesWindow) -> list[float]:
    features = window.feature_values
    missing = [
        sensor_key
        for _feature_name, sensor_key in AI4I_SENSOR_FEATURE_MAP
        if sensor_key not in features
    ]
    if missing:
        raise ValueError(
            "实时特征窗口缺少 AI4I 模型必需点位：" + ", ".join(missing)
        )
    return [float(features[sensor_key]) for _feature_name, sensor_key in AI4I_SENSOR_FEATURE_MAP]


def _predict_failure_probability(feature_vector: list[float], model: LGBMClassifier) -> float:
    probability = float(model.predict_proba(np.array([feature_vector]))[0, 1])
    return _clip01(probability)


def _predict_anomaly(
    feature_vector: list[float],
    model: IsolationForest,
) -> tuple[float, list[str]]:
    score = float(_isolation_scores(model, np.array([feature_vector]))[0])
    return score, _anomaly_reasons(feature_vector, score)


def _predict_rul(feature_vector: list[float], model: LGBMRegressor) -> float:
    return round(max(1.0, float(model.predict(np.array([feature_vector]))[0])), 2)


def _rul_target_from_rows(rows: list[dict[str, str]], failures: np.ndarray) -> np.ndarray:
    wear = np.array([float(row["Tool wear [min]"]) for row in rows], dtype=float)
    max_wear = max(float(np.percentile(wear, 95)), 1.0)
    remaining_wear = np.maximum(max_wear - wear, 0.0)
    failure_penalty = np.where(failures == 1, 0.08, 1.0)
    return np.clip(remaining_wear * failure_penalty, 1.0, max_wear)


def _explain_global_importance(
    model: LGBMClassifier,
    x: np.ndarray,
) -> list[RiskExplanation]:
    shap_values = _positive_class_shap_values(shap.TreeExplainer(model).shap_values(x))
    if shap_values.ndim == 1:
        mean_abs_values = np.abs(shap_values)
    else:
        mean_abs_values = np.abs(shap_values).mean(axis=0)
    mean_values = x.mean(axis=0)
    total = float(np.sum(mean_abs_values)) or 1.0
    explanations = [
        RiskExplanation(name, float(value), float(contribution / total))
        for name, value, contribution in zip(
            AI4I_FEATURE_COLUMNS,
            mean_values,
            mean_abs_values,
            strict=True,
        )
    ]
    return sorted(explanations, key=lambda item: abs(item.contribution), reverse=True)


def _explanation_metrics(explanations: list[RiskExplanation]) -> list[ModelMetric]:
    metrics = [
        _metric("shap-risk-explainer", "explainability", "feature_count", float(len(explanations)))
    ]
    for index, explanation in enumerate(explanations[:5], start=1):
        metrics.append(
            _metric(
                "shap-risk-explainer",
                "explainability",
                f"top_{index}_{_safe_metric_name(explanation.feature_name)}",
                abs(explanation.contribution),
            )
        )
    return metrics


def _positive_class_shap_values(shap_values: Any) -> np.ndarray:
    if isinstance(shap_values, list):
        values = shap_values[-1]
    else:
        values = shap_values
    array = np.asarray(values)
    if array.ndim == 3:
        return array[:, :, -1]
    return array


def _isolation_scores(model: IsolationForest, x: np.ndarray) -> np.ndarray:
    raw_scores = model.decision_function(x)
    return np.clip(1 / (1 + np.exp(raw_scores * 8)), 0.0, 1.0)


def _anomaly_reasons(feature_vector: list[float], score: float) -> list[str]:
    _air, _process, speed, torque, wear = feature_vector
    reasons: list[str] = []
    if abs(speed - 1500) > 350:
        reasons.append("rotational_speed")
    if torque > 55:
        reasons.append("torque")
    if wear > 160:
        reasons.append("tool_wear")
    if score >= 0.55 and not reasons:
        reasons.append("feature_distribution")
    return reasons


def _assert_trainable_dataset(x: np.ndarray, y: np.ndarray) -> None:
    if len(x) < 8:
        raise ValueError("AI4I 真实模型训练至少需要 8 条样本")
    if len(set(y.tolist())) < 2:
        raise ValueError("LightGBM 故障分类训练需要同时包含正常和故障样本")


def _split_supervised_dataset(
    x: np.ndarray,
    y: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    test_size = 0.35 if len(x) >= 12 else 0.5
    return train_test_split(
        x,
        y,
        test_size=test_size,
        random_state=42,
        stratify=y,
    )


def _safe_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    if len(set(y_true.tolist())) < 2:
        return 0.0
    return float(roc_auc_score(y_true, y_score))


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) < 2:
        return 0.0
    return float(r2_score(y_true, y_pred))


def _metric(model_name: str, model_type: str, metric_name: str, value: float) -> ModelMetric:
    return ModelMetric(
        model_name=model_name,
        model_type=model_type,
        version="1.0.0",
        metric_name=metric_name,
        metric_value=float(value),
    )


def _safe_metric_name(value: str) -> str:
    return (
        value.replace(" [", "_")
        .replace("]", "")
        .replace(" ", "_")
        .replace("/", "_")
        .replace(".", "_")
        .lower()
    )


def _clip01(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)
