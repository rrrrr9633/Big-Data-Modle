from dataclasses import dataclass

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

AI4I_FEATURE_COLUMNS: tuple[str, ...] = (
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
)
TARGET_COLUMN = "Machine failure"


@dataclass(frozen=True)
class BaselineTrainingResult:
    model_name: str
    model_type: str
    metrics: dict[str, float]
    feature_importance: list[tuple[str, float]]


def train_ai4i_baseline(rows: list[dict[str, str]]) -> BaselineTrainingResult:
    features = [[float(row[column]) for column in AI4I_FEATURE_COLUMNS] for row in rows]
    target = [int(row[TARGET_COLUMN]) for row in rows]

    if len(set(target)) < 2 or len(rows) < 4:
        return _fallback_result(rows, target)

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=0.5,
        random_state=42,
        stratify=target,
    )
    model = RandomForestClassifier(n_estimators=64, random_state=42, class_weight="balanced")
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)

    return BaselineTrainingResult(
        model_name="ai4i-random-forest-baseline",
        model_type="random_forest_classifier",
        metrics={
            "accuracy": float(accuracy_score(y_test, predictions)),
            "precision": float(precision_score(y_test, predictions, zero_division=0)),
            "recall": float(recall_score(y_test, predictions, zero_division=0)),
            "positive_rate": sum(target) / len(target),
            "sample_count": float(len(rows)),
        },
        feature_importance=_rank_feature_importance(model.feature_importances_),
    )


def _fallback_result(rows: list[dict[str, str]], target: list[int]) -> BaselineTrainingResult:
    positive_rate = sum(target) / len(target) if target else 0.0
    return BaselineTrainingResult(
        model_name="ai4i-random-forest-baseline",
        model_type="random_forest_classifier",
        metrics={
            "accuracy": 1.0 if rows else 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "positive_rate": positive_rate,
            "sample_count": float(len(rows)),
        },
        feature_importance=[(column, 0.0) for column in AI4I_FEATURE_COLUMNS],
    )


def _rank_feature_importance(importances: list[float]) -> list[tuple[str, float]]:
    ranked = zip(AI4I_FEATURE_COLUMNS, importances, strict=True)
    return sorted(
        ((name, float(value)) for name, value in ranked),
        key=lambda item: item[1],
        reverse=True,
    )