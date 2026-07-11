from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.models.model_suite import AI4I_FEATURE_COLUMNS, Ai4iModelSuite

MODEL_ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "models"
ACTIVE_MODEL_PATH = MODEL_ARTIFACT_DIR / "active_ai4i_model_suite.pkl"
ACTIVE_MODEL_MANIFEST_PATH = MODEL_ARTIFACT_DIR / "model_manifest.json"


@dataclass(frozen=True)
class ActiveModelState:
    available: bool
    path: str | None
    manifest_path: str | None = None
    saved_at: str | None = None
    model_names: list[str] | None = None


def save_active_model_suite(suite: Ai4iModelSuite) -> ActiveModelState:
    MODEL_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    with ACTIVE_MODEL_PATH.open("wb") as file:
        pickle.dump(suite, file)

    manifest = _build_manifest(suite)
    ACTIVE_MODEL_MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return _state_from_manifest(manifest)


def load_active_model_suite() -> Ai4iModelSuite:
    if not ACTIVE_MODEL_PATH.exists():
        raise FileNotFoundError("当前没有 active 真模型，请先导入 AI4I CSV 完成训练")
    with ACTIVE_MODEL_PATH.open("rb") as file:
        loaded = pickle.load(file)
    if not isinstance(loaded, Ai4iModelSuite):
        raise TypeError("active 模型产物类型不正确")
    return loaded


def get_active_model_state() -> ActiveModelState:
    if not ACTIVE_MODEL_PATH.exists():
        return ActiveModelState(available=False, path=None)
    if not ACTIVE_MODEL_MANIFEST_PATH.exists():
        return ActiveModelState(available=True, path=str(ACTIVE_MODEL_PATH))
    return _state_from_manifest(_read_manifest())


def delete_active_model_artifacts() -> dict[str, bool]:
    deleted = {
        "artifact_deleted": False,
        "manifest_deleted": False,
    }
    if ACTIVE_MODEL_PATH.exists():
        ACTIVE_MODEL_PATH.unlink()
        deleted["artifact_deleted"] = True
    if ACTIVE_MODEL_MANIFEST_PATH.exists():
        ACTIVE_MODEL_MANIFEST_PATH.unlink()
        deleted["manifest_deleted"] = True
    return deleted


def model_feature_dependencies(suite: Ai4iModelSuite) -> list[dict[str, object]]:
    models = list(dict.fromkeys((metric.model_name, metric.version) for metric in suite.metrics))
    return [
        {
            "model_name": model_name,
            "version": version,
            "features": list(AI4I_FEATURE_COLUMNS),
        }
        for model_name, version in models
    ]


def _build_manifest(suite: Any) -> dict[str, Any]:
    metrics = getattr(suite, "metrics", [])
    model_names = list(dict.fromkeys(str(metric.model_name) for metric in metrics))
    model_types = {
        str(metric.model_name): str(metric.model_type)
        for metric in metrics
        if hasattr(metric, "model_name") and hasattr(metric, "model_type")
    }
    return {
        "available": True,
        "saved_at": datetime.now(UTC).isoformat(),
        "artifact_path": str(ACTIVE_MODEL_PATH),
        "manifest_path": str(ACTIVE_MODEL_MANIFEST_PATH),
        "model_names": model_names,
        "model_types": model_types,
        "feature_dependencies": model_feature_dependencies(suite),
        "pipeline": [
            "设备数据接入层",
            "数据标准化",
            "原始读数入库",
            "滑动窗口聚合",
            "模型推理",
            "健康评分融合",
            "SHAP 解释",
            "预警生成",
        ],
    }


def _read_manifest() -> dict[str, Any]:
    return json.loads(ACTIVE_MODEL_MANIFEST_PATH.read_text(encoding="utf-8"))


def _state_from_manifest(manifest: dict[str, Any]) -> ActiveModelState:
    return ActiveModelState(
        available=bool(manifest.get("available", True)),
        path=str(manifest.get("artifact_path") or ACTIVE_MODEL_PATH),
        manifest_path=str(manifest.get("manifest_path") or ACTIVE_MODEL_MANIFEST_PATH),
        saved_at=str(manifest["saved_at"]) if manifest.get("saved_at") else None,
        model_names=list(manifest.get("model_names") or []),
    )
