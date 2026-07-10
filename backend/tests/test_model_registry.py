from types import SimpleNamespace

from app.models import registry
from app.models.registry import (
    delete_active_model_artifacts,
    get_active_model_state,
    save_active_model_suite,
)


def test_active_model_manifest_records_artifact_and_model_chain(tmp_path, monkeypatch) -> None:
    artifact_dir = tmp_path / "models"
    monkeypatch.setattr(registry, "MODEL_ARTIFACT_DIR", artifact_dir)
    monkeypatch.setattr(
        registry,
        "ACTIVE_MODEL_PATH",
        artifact_dir / "active_ai4i_model_suite.pkl",
    )
    monkeypatch.setattr(
        registry,
        "ACTIVE_MODEL_MANIFEST_PATH",
        artifact_dir / "model_manifest.json",
    )

    suite = SimpleNamespace(
        metrics=[
            SimpleNamespace(model_name="lightgbm-fault-classifier", model_type="classification"),
            SimpleNamespace(model_name="isolation-forest-anomaly", model_type="anomaly_detection"),
            SimpleNamespace(model_name="lightgbm-rul-regressor", model_type="regression"),
        ]
    )

    saved = save_active_model_suite(suite)
    state = get_active_model_state()

    assert saved.available is True
    assert state.available is True
    assert state.path == str(artifact_dir / "active_ai4i_model_suite.pkl")
    assert state.manifest_path == str(artifact_dir / "model_manifest.json")
    assert state.model_names == [
        "lightgbm-fault-classifier",
        "isolation-forest-anomaly",
        "lightgbm-rul-regressor",
    ]
    assert state.saved_at is not None


def test_delete_active_model_artifacts_removes_model_and_manifest(tmp_path, monkeypatch) -> None:
    artifact_dir = tmp_path / "models"
    model_path = artifact_dir / "active_ai4i_model_suite.pkl"
    manifest_path = artifact_dir / "model_manifest.json"
    artifact_dir.mkdir(parents=True)
    model_path.write_bytes(b"model")
    manifest_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(registry, "MODEL_ARTIFACT_DIR", artifact_dir)
    monkeypatch.setattr(registry, "ACTIVE_MODEL_PATH", model_path)
    monkeypatch.setattr(registry, "ACTIVE_MODEL_MANIFEST_PATH", manifest_path)

    deleted = delete_active_model_artifacts()

    assert deleted == {"artifact_deleted": True, "manifest_deleted": True}
    assert model_path.exists() is False
    assert manifest_path.exists() is False