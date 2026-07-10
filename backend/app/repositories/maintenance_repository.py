import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.timeseries import SensorReading


def _rows(result: Any) -> list[dict[str, Any]]:
    rows = [dict(row) for row in result.mappings()]
    for row in rows:
        for key in (
            "anomaly_reasons",
            "explanations",
            "sensor_points",
            "action_logs",
            "warning_explanation",
            "protocol_options",
            "payload",
            "impact",
            "snapshot",
        ):
            if isinstance(row.get(key), str):
                try:
                    row[key] = json.loads(row[key])
                except json.JSONDecodeError:
                    row[key] = []
    return rows


def fetch_dashboard_summary(db: Session) -> dict[str, int | float]:
    row = (
        db.execute(
            text(
                """
            SELECT
              (SELECT COUNT(*) FROM devices) AS device_total,
              (SELECT COUNT(DISTINCT device_code)
                 FROM prediction_logs
                WHERE risk_level IN ('medium', 'high', 'critical')) AS abnormal_device_total,
              (SELECT COUNT(DISTINCT device_code)
                 FROM prediction_logs
                WHERE risk_level IN ('high', 'critical')) AS high_risk_device_total,
              COALESCE((SELECT AVG(health_score) FROM prediction_logs), 0) AS average_health_score,
              (SELECT COUNT(*)
                 FROM warning_events
                WHERE DATE(created_at) = CURRENT_DATE()) AS today_warning_total
            """
            )
        )
        .mappings()
        .one()
    )
    return {
        "device_total": int(row["device_total"] or 0),
        "abnormal_device_total": int(row["abnormal_device_total"] or 0),
        "high_risk_device_total": int(row["high_risk_device_total"] or 0),
        "average_health_score": float(row["average_health_score"] or 0),
        "today_warning_total": int(row["today_warning_total"] or 0),
    }


def fetch_devices(db: Session) -> list[dict[str, Any]]:
    result = db.execute(
        text(
            """
            SELECT
              d.device_code,
              d.device_name,
              d.device_type,
              d.factory,
              d.workshop,
              d.production_line,
              d.status,
              d.created_at,
              latest.failure_probability,
              latest.health_score,
              latest.risk_level,
              latest.anomaly_score,
              latest.anomaly_reasons,
              latest.trend_factor,
              latest.quality_score,
              latest.rul_hours,
              COALESCE(
                (
                  SELECT JSON_ARRAYAGG(
                    JSON_OBJECT(
                      'sensor_code', sp.sensor_code,
                      'sensor_name', sp.sensor_name,
                      'device_code', sp.device_code,
                      'unit', sp.unit,
                      'sampling_frequency', sp.sampling_frequency,
                      'protocol', sp.protocol,
                      'source_address', sp.source_address,
                      'protocol_options', COALESCE(sp.protocol_options, JSON_OBJECT()),
                      'feature_name', sp.feature_name,
                      'quality_rule', sp.quality_rule,
                      'min_value', sp.min_value,
                      'max_value', sp.max_value,
                      'enabled', sp.enabled
                    )
                  )
                  FROM sensor_points sp
                  WHERE sp.device_code = d.device_code
                ),
                JSON_ARRAY()
              ) AS sensor_points
            FROM devices d
            LEFT JOIN (
              SELECT ranked.*
              FROM (
                SELECT
                  p.*,
                  ROW_NUMBER() OVER (
                    PARTITION BY device_code
                    ORDER BY created_at DESC, id DESC
                  ) AS rn
                FROM prediction_logs p
              ) ranked
              WHERE ranked.rn = 1
            ) latest ON d.device_code = latest.device_code
            ORDER BY d.created_at DESC
            """
        )
    )
    return _rows(result)


def fetch_predictions(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    result = db.execute(
        text(
            """
            SELECT
              p.id,
              p.device_code,
              p.feature_window_id,
              p.model_version,
              p.failure_probability,
              p.health_score,
              p.risk_level,
              p.anomaly_score,
              p.anomaly_reasons,
              p.trend_factor,
              p.quality_score,
              p.rul_hours,
              p.created_at,
              COALESCE(
                (
                  SELECT JSON_ARRAYAGG(
                    JSON_OBJECT(
                      'feature_name', e.feature_name,
                      'feature_value', e.feature_value,
                      'contribution', e.contribution
                    )
                  )
                  FROM prediction_explanations e
                  WHERE e.prediction_id = p.id
                ),
                JSON_ARRAY()
              ) AS explanations
            FROM prediction_logs p
            ORDER BY p.created_at DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )
    return _rows(result)


def fetch_warnings(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    result = db.execute(
        text(
            """
            SELECT
              w.id,
              w.prediction_id,
              w.feature_window_id,
              w.model_version,
              w.failure_probability,
              w.health_score,
              w.warning_explanation,
              w.device_code,
              w.risk_level,
              w.title,
              w.detail,
              w.suggested_action,
              CASE WHEN w.status = 'pending' THEN 'new' ELSE w.status END AS status,
              w.acknowledged_at,
              w.resolved_at,
              w.latest_action,
              w.created_at,
              COALESCE(
                (
                  SELECT JSON_ARRAYAGG(
                    JSON_OBJECT(
                      'id', l.id,
                      'warning_id', l.warning_id,
                      'from_status', l.from_status,
                      'to_status', l.to_status,
                      'operator', l.operator,
                      'note', l.note,
                      'created_at', l.created_at
                    )
                  )
                  FROM warning_action_logs l
                  WHERE l.warning_id = w.id
                ),
                JSON_ARRAY()
              ) AS action_logs
            FROM warning_events w
            ORDER BY w.created_at DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )
    return _rows(result)


def fetch_warning_by_id(db: Session, warning_id: int) -> dict[str, Any] | None:
    rows = _rows(
        db.execute(
            text(
                """
                SELECT
                  id,
                  prediction_id,
                  feature_window_id,
                  model_version,
                  failure_probability,
                  health_score,
                  warning_explanation,
                  device_code,
                  risk_level,
                  title,
                  detail,
                  suggested_action,
                  CASE WHEN status = 'pending' THEN 'new' ELSE status END AS status,
                  acknowledged_at,
                  resolved_at,
                  latest_action,
                  created_at
                FROM warning_events
                WHERE id = :warning_id
                """
            ),
            {"warning_id": warning_id},
        )
    )
    return rows[0] if rows else None


def transition_warning_status(
    db: Session,
    *,
    warning_id: int,
    from_status: str,
    to_status: str,
    operator: str,
    note: str | None,
) -> None:
    latest_action = note or f"{operator} 将预警状态从 {from_status} 更新为 {to_status}"
    db.execute(
        text(
            """
            UPDATE warning_events
            SET
              status = :to_status,
              acknowledged_at = CASE
                WHEN :to_status IN ('acknowledged', 'processing', 'resolved')
                 AND acknowledged_at IS NULL THEN CURRENT_TIMESTAMP
                ELSE acknowledged_at
              END,
              resolved_at = CASE
                WHEN :to_status IN ('resolved', 'ignored') THEN CURRENT_TIMESTAMP
                ELSE resolved_at
              END,
              latest_action = :latest_action
            WHERE id = :warning_id
            """
        ),
        {
            "warning_id": warning_id,
            "to_status": to_status,
            "latest_action": latest_action,
        },
    )
    db.execute(
        text(
            """
            INSERT INTO warning_action_logs (
              warning_id,
              from_status,
              to_status,
              operator,
              note
            )
            VALUES (
              :warning_id,
              :from_status,
              :to_status,
              :operator,
              :note
            )
            """
        ),
        {
            "warning_id": warning_id,
            "from_status": from_status,
            "to_status": to_status,
            "operator": operator,
            "note": note,
        },
    )


def readings_from_rows(rows: list[dict[str, Any]]) -> list[SensorReading]:
    return [
        SensorReading(
            device_id=str(row["device_code"]),
            sensor_code=str(row["sensor_code"]),
            timestamp=row["recorded_at"],
            value=float(row["value"]) if row["value"] is not None else None,
            unit=row.get("unit"),
        )
        for row in rows
    ]


def fetch_recent_sensor_readings(
    db: Session,
    *,
    device_code: str,
    limit: int = 60,
) -> list[SensorReading]:
    result = db.execute(
        text(
            """
            SELECT device_code, sensor_code, recorded_at, value, unit
            FROM (
              SELECT device_code, sensor_code, recorded_at, value, unit
              FROM sensor_readings
              WHERE device_code = :device_code
              ORDER BY recorded_at DESC, id DESC
              LIMIT :limit
            ) recent
            ORDER BY recorded_at ASC
            """
        ),
        {"device_code": device_code, "limit": limit},
    )
    return readings_from_rows(_rows(result))


def fetch_model_versions(db: Session) -> list[dict[str, Any]]:
    result = db.execute(
        text(
            """
            SELECT
              model_name,
              model_type,
              version,
              metric_name,
              metric_value,
              artifact_path,
              status,
              created_at
            FROM model_versions
            ORDER BY created_at DESC
            """
        )
    )
    return _rows(result)


def create_import_batch(db: Session, source_name: str, row_count: int) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO data_import_batches (source_name, row_count, status)
            VALUES (:source_name, :row_count, 'completed')
            """
        ),
        {"source_name": source_name, "row_count": row_count},
    )
    return int(result.lastrowid)


def upsert_device(
    db: Session,
    *,
    device_code: str,
    device_name: str,
    device_type: str,
    status: str,
    factory: str = "默认工厂",
    workshop: str = "默认车间",
    production_line: str = "默认产线",
) -> None:
    db.execute(
        text(
            """
            INSERT INTO devices (
              device_code,
              device_name,
              device_type,
              factory,
              workshop,
              production_line,
              status
            )
            VALUES (
              :device_code,
              :device_name,
              :device_type,
              :factory,
              :workshop,
              :production_line,
              :status
            )
            ON DUPLICATE KEY UPDATE
              device_name = VALUES(device_name),
              device_type = VALUES(device_type),
              factory = VALUES(factory),
              workshop = VALUES(workshop),
              production_line = VALUES(production_line),
              status = VALUES(status)
            """
        ),
        {
            "device_code": device_code,
            "device_name": device_name,
            "device_type": device_type,
            "factory": factory,
            "workshop": workshop,
            "production_line": production_line,
            "status": status,
        },
    )


def upsert_sensor_point(
    db: Session,
    *,
    device_code: str,
    sensor_code: str,
    sensor_name: str | None = None,
    unit: str | None,
    sampling_frequency: str = "realtime",
    protocol: str | None = None,
    source_address: str | None = None,
    protocol_options: dict[str, Any] | None = None,
    feature_name: str | None = None,
    quality_rule: str | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
    enabled: bool = True,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO sensor_points (
              sensor_code,
              sensor_name,
              device_code,
              unit,
              sampling_frequency,
              protocol,
              source_address,
              protocol_options,
              feature_name,
              quality_rule,
              min_value,
              max_value,
              enabled
            )
            VALUES (
              :sensor_code,
              :sensor_name,
              :device_code,
              :unit,
              :sampling_frequency,
              :protocol,
              :source_address,
              :protocol_options,
              :feature_name,
              :quality_rule,
              :min_value,
              :max_value,
              :enabled
            )
            ON DUPLICATE KEY UPDATE
              sensor_name = VALUES(sensor_name),
              unit = VALUES(unit),
              sampling_frequency = VALUES(sampling_frequency),
              protocol = VALUES(protocol),
              source_address = VALUES(source_address),
              protocol_options = VALUES(protocol_options),
              feature_name = VALUES(feature_name),
              quality_rule = VALUES(quality_rule),
              min_value = COALESCE(
                LEAST(sensor_points.min_value, VALUES(min_value)),
                VALUES(min_value),
                sensor_points.min_value
              ),
              max_value = COALESCE(
                GREATEST(sensor_points.max_value, VALUES(max_value)),
                VALUES(max_value),
                sensor_points.max_value
              ),
              enabled = VALUES(enabled)
            """
        ),
        {
            "sensor_code": sensor_code,
            "sensor_name": sensor_name or sensor_code.replace("_", " ").title(),
            "device_code": device_code,
            "unit": unit,
            "sampling_frequency": sampling_frequency,
            "protocol": protocol,
            "source_address": source_address,
            "protocol_options": json.dumps(protocol_options or {}, ensure_ascii=False),
            "feature_name": feature_name,
            "quality_rule": quality_rule,
            "min_value": min_value,
            "max_value": max_value,
            "enabled": enabled,
        },
    )


def disable_sensor_point(db: Session, *, device_code: str, sensor_code: str) -> None:
    db.execute(
        text(
            """
            UPDATE sensor_points
            SET enabled = FALSE
            WHERE device_code = :device_code AND sensor_code = :sensor_code
            """
        ),
        {"device_code": device_code, "sensor_code": sensor_code},
    )


def insert_master_data_change_request(
    db: Session,
    *,
    entity_type: str,
    operation: str,
    device_code: str,
    sensor_code: str | None,
    payload: dict[str, Any],
    impact: dict[str, Any],
    reason: str | None,
    requested_by: str,
    requested_role: str,
) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO master_data_change_requests (
              entity_type,
              operation,
              device_code,
              sensor_code,
              payload_json,
              impact_json,
              reason,
              requested_by,
              requested_role,
              status
            )
            VALUES (
              :entity_type,
              :operation,
              :device_code,
              :sensor_code,
              :payload_json,
              :impact_json,
              :reason,
              :requested_by,
              :requested_role,
              'pending'
            )
            """
        ),
        {
            "entity_type": entity_type,
            "operation": operation,
            "device_code": device_code,
            "sensor_code": sensor_code,
            "payload_json": json.dumps(payload, ensure_ascii=False),
            "impact_json": json.dumps(impact, ensure_ascii=False),
            "reason": reason,
            "requested_by": requested_by,
            "requested_role": requested_role,
        },
    )
    return int(result.lastrowid or 0)


def fetch_master_data_change_requests(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    result = db.execute(
        text(
            """
            SELECT
              id,
              entity_type,
              operation,
              device_code,
              sensor_code,
              payload_json AS payload,
              impact_json AS impact,
              reason,
              status,
              requested_by,
              requested_role,
              approved_by,
              approved_role,
              decision_comment,
              created_at,
              decided_at
            FROM master_data_change_requests
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )
    return _rows(result)


def fetch_master_data_change_request(db: Session, change_request_id: int) -> dict[str, Any] | None:
    result = db.execute(
        text(
            """
            SELECT
              id,
              entity_type,
              operation,
              device_code,
              sensor_code,
              payload_json AS payload,
              impact_json AS impact,
              reason,
              status,
              requested_by,
              requested_role,
              approved_by,
              approved_role,
              decision_comment,
              created_at,
              decided_at
            FROM master_data_change_requests
            WHERE id = :id
            """
        ),
        {"id": change_request_id},
    )
    rows = _rows(result)
    return rows[0] if rows else None


def mark_master_data_change_request_decision(
    db: Session,
    *,
    change_request_id: int,
    status: str,
    approved_by: str,
    approved_role: str,
    decision_comment: str | None,
) -> None:
    db.execute(
        text(
            """
            UPDATE master_data_change_requests
            SET
              status = :status,
              approved_by = :approved_by,
              approved_role = :approved_role,
              decision_comment = :decision_comment,
              decided_at = CURRENT_TIMESTAMP
            WHERE id = :id
            """
        ),
        {
            "id": change_request_id,
            "status": status,
            "approved_by": approved_by,
            "approved_role": approved_role,
            "decision_comment": decision_comment,
        },
    )


def insert_master_data_version(
    db: Session,
    *,
    change_request_id: int,
    entity_type: str,
    device_code: str,
    sensor_code: str | None,
    snapshot: dict[str, Any],
    published_by: str,
    published_role: str,
) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO master_data_versions (
              change_request_id,
              entity_type,
              device_code,
              sensor_code,
              snapshot_json,
              published_by,
              published_role
            )
            VALUES (
              :change_request_id,
              :entity_type,
              :device_code,
              :sensor_code,
              :snapshot_json,
              :published_by,
              :published_role
            )
            """
        ),
        {
            "change_request_id": change_request_id,
            "entity_type": entity_type,
            "device_code": device_code,
            "sensor_code": sensor_code,
            "snapshot_json": json.dumps(snapshot, ensure_ascii=False),
            "published_by": published_by,
            "published_role": published_role,
        },
    )
    return int(result.lastrowid or 0)


def insert_audit_log(
    db: Session,
    *,
    actor: str,
    role: str,
    action: str,
    resource: str,
    detail: dict[str, Any] | None = None,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO audit_logs (
              actor,
              role,
              action,
              resource,
              detail_json
            )
            VALUES (
              :actor,
              :role,
              :action,
              :resource,
              :detail_json
            )
            """
        ),
        {
            "actor": actor,
            "role": role,
            "action": action,
            "resource": resource,
            "detail_json": json.dumps(detail or {}, ensure_ascii=False),
        },
    )


def fetch_audit_logs(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    result = db.execute(
        text(
            """
            SELECT
              id,
              actor,
              role,
              action,
              resource,
              detail_json,
              created_at
            FROM audit_logs
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )
    return _rows(result)


def insert_sensor_reading(
    db: Session,
    *,
    device_code: str,
    sensor_code: str,
    recorded_at: datetime,
    value: float,
    unit: str | None,
    batch_id: int,
) -> None:
    upsert_sensor_point(
        db,
        device_code=device_code,
        sensor_code=sensor_code,
        unit=unit,
        min_value=value,
        max_value=value,
    )
    db.execute(
        text(
            """
            INSERT INTO sensor_readings (
              device_code,
              sensor_code,
              recorded_at,
              value,
              unit,
              batch_id
            )
            VALUES (:device_code, :sensor_code, :recorded_at, :value, :unit, :batch_id)
            """
        ),
        {
            "device_code": device_code,
            "sensor_code": sensor_code,
            "recorded_at": recorded_at,
            "value": value,
            "unit": unit,
            "batch_id": batch_id,
        },
    )


def insert_feature_window(
    db: Session,
    *,
    device_code: str,
    start_time: datetime,
    end_time: datetime,
    feature_values: dict[str, float],
) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO feature_windows (
              device_code,
              start_time,
              end_time,
              mean_value,
              std_value,
              max_value,
              min_value,
              trend_value
            )
            VALUES (
              :device_code,
              :start_time,
              :end_time,
              :mean_value,
              :std_value,
              :max_value,
              :min_value,
              :trend_value
            )
            """
        ),
        {
            "device_code": device_code,
            "start_time": start_time,
            "end_time": end_time,
            "mean_value": feature_values.get("mean", 0.0),
            "std_value": feature_values.get("std", 0.0),
            "max_value": feature_values.get("max", 0.0),
            "min_value": feature_values.get("min", 0.0),
            "trend_value": feature_values.get("trend", 0.0),
        },
    )
    return int(result.lastrowid)


def insert_prediction(
    db: Session,
    *,
    device_code: str,
    feature_window_id: int,
    model_version: str,
    failure_probability: float,
    health_score: float,
    risk_level: str,
    anomaly_score: float,
    anomaly_reasons: list[str],
    trend_factor: float,
    quality_score: float,
    rul_hours: float | None,
) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO prediction_logs (
              device_code,
              feature_window_id,
              model_version,
              failure_probability,
              health_score,
              risk_level,
              anomaly_score,
              anomaly_reasons,
              trend_factor,
              quality_score,
              rul_hours
            )
            VALUES (
              :device_code,
              :feature_window_id,
              :model_version,
              :failure_probability,
              :health_score,
              :risk_level,
              :anomaly_score,
              :anomaly_reasons,
              :trend_factor,
              :quality_score,
              :rul_hours
            )
            """
        ),
        {
            "device_code": device_code,
            "feature_window_id": feature_window_id,
            "model_version": model_version,
            "failure_probability": failure_probability,
            "health_score": health_score,
            "risk_level": risk_level,
            "anomaly_score": anomaly_score,
            "anomaly_reasons": json.dumps(anomaly_reasons, ensure_ascii=False),
            "trend_factor": trend_factor,
            "quality_score": quality_score,
            "rul_hours": rul_hours,
        },
    )
    return int(result.lastrowid)


def insert_prediction_explanations(
    db: Session,
    *,
    prediction_id: int,
    device_code: str,
    explanations: list[Any],
) -> None:
    for explanation in explanations:
        db.execute(
            text(
                """
                INSERT INTO prediction_explanations (
                  prediction_id,
                  device_code,
                  feature_name,
                  feature_value,
                  contribution
                )
                VALUES (
                  :prediction_id,
                  :device_code,
                  :feature_name,
                  :feature_value,
                  :contribution
                )
                """
            ),
            {
                "prediction_id": prediction_id,
                "device_code": device_code,
                "feature_name": explanation.feature_name,
                "feature_value": explanation.feature_value,
                "contribution": explanation.contribution,
            },
        )


def reset_training_records(db: Session) -> dict[str, int]:
    tables = [
        "prediction_explanations",
        "warning_action_logs",
        "warning_events",
        "prediction_logs",
        "feature_windows",
        "sensor_readings",
        "master_data_versions",
        "master_data_change_requests",
        "sensor_points",
        "devices",
        "data_import_batches",
        "model_versions",
    ]
    deleted: dict[str, int] = {}
    for table in tables:
        result = db.execute(text(f"DELETE FROM {table}"))
        deleted[table] = int(result.rowcount or 0)
    return deleted


def upsert_model_metric(
    db: Session,
    *,
    model_name: str,
    model_type: str,
    version: str,
    metric_name: str,
    metric_value: float,
    artifact_path: str | None = None,
    status: str = "active",
) -> None:
    db.execute(
        text(
            """
            INSERT INTO model_versions (
              model_name,
              model_type,
              version,
              metric_name,
              metric_value,
              artifact_path,
              status
            )
            VALUES (
              :model_name,
              :model_type,
              :version,
              :metric_name,
              :metric_value,
              :artifact_path,
              :status
            )
            ON DUPLICATE KEY UPDATE
              metric_value = VALUES(metric_value),
              artifact_path = VALUES(artifact_path),
              status = VALUES(status)
            """
        ),
        {
            "model_name": model_name,
            "model_type": model_type,
            "version": version,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "artifact_path": artifact_path,
            "status": status,
        },
    )


def ensure_prediction_model_schema(db: Session) -> None:
    ddl_statements = [
        "ALTER TABLE devices ADD COLUMN factory VARCHAR(128) NOT NULL DEFAULT '默认工厂'",
        "ALTER TABLE devices ADD COLUMN workshop VARCHAR(128) NOT NULL DEFAULT '默认车间'",
        "ALTER TABLE devices ADD COLUMN production_line VARCHAR(128) NOT NULL DEFAULT '默认产线'",
        """
        CREATE TABLE IF NOT EXISTS sensor_points (
          id BIGINT PRIMARY KEY AUTO_INCREMENT,
          sensor_code VARCHAR(64) NOT NULL,
          sensor_name VARCHAR(128) NOT NULL,
          device_code VARCHAR(64) NOT NULL,
          unit VARCHAR(32) NULL,
          sampling_frequency VARCHAR(64) NOT NULL DEFAULT 'realtime',
          protocol VARCHAR(64) NULL,
          source_address VARCHAR(255) NULL,
          protocol_options JSON NULL,
          feature_name VARCHAR(128) NULL,
          quality_rule VARCHAR(255) NULL,
          min_value DOUBLE NULL,
          max_value DOUBLE NULL,
          enabled BOOLEAN NOT NULL DEFAULT TRUE,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          UNIQUE KEY uk_sensor_device_code (device_code, sensor_code),
          INDEX idx_sensor_point_device (device_code),
          CONSTRAINT fk_sensor_point_device
            FOREIGN KEY (device_code) REFERENCES devices(device_code)
        )
        """,
        "ALTER TABLE sensor_points ADD COLUMN protocol VARCHAR(64) NULL",
        "ALTER TABLE sensor_points ADD COLUMN source_address VARCHAR(255) NULL",
        "ALTER TABLE sensor_points ADD COLUMN protocol_options JSON NULL",
        "ALTER TABLE sensor_points ADD COLUMN feature_name VARCHAR(128) NULL",
        "ALTER TABLE sensor_points ADD COLUMN quality_rule VARCHAR(255) NULL",
        "ALTER TABLE prediction_logs ADD COLUMN feature_window_id BIGINT NULL",
        "ALTER TABLE prediction_logs ADD COLUMN model_version VARCHAR(64) NULL",
        "ALTER TABLE prediction_logs ADD INDEX idx_prediction_window (feature_window_id)",
        "ALTER TABLE prediction_logs ADD INDEX idx_prediction_model_version (model_version)",
        "ALTER TABLE prediction_logs ADD COLUMN anomaly_score DOUBLE NOT NULL DEFAULT 0",
        "ALTER TABLE prediction_logs ADD COLUMN anomaly_reasons JSON NULL",
        "ALTER TABLE prediction_logs ADD COLUMN trend_factor DOUBLE NOT NULL DEFAULT 0",
        "ALTER TABLE prediction_logs ADD COLUMN quality_score DOUBLE NOT NULL DEFAULT 1",
        "ALTER TABLE prediction_logs ADD COLUMN rul_hours DOUBLE NULL",
        """
        CREATE TABLE IF NOT EXISTS prediction_explanations (
          id BIGINT PRIMARY KEY AUTO_INCREMENT,
          prediction_id BIGINT NOT NULL,
          device_code VARCHAR(64) NOT NULL,
          feature_name VARCHAR(128) NOT NULL,
          feature_value DOUBLE NOT NULL,
          contribution DOUBLE NOT NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          INDEX idx_explanation_prediction (prediction_id),
          INDEX idx_explanation_device_time (device_code, created_at),
          CONSTRAINT fk_explanation_prediction
            FOREIGN KEY (prediction_id) REFERENCES prediction_logs(id)
        )
        """,
        "ALTER TABLE warning_events ADD COLUMN prediction_id BIGINT NULL",
        "ALTER TABLE warning_events ADD COLUMN feature_window_id BIGINT NULL",
        "ALTER TABLE warning_events ADD COLUMN model_version VARCHAR(64) NULL",
        "ALTER TABLE warning_events ADD COLUMN failure_probability DOUBLE NULL",
        "ALTER TABLE warning_events ADD COLUMN health_score DOUBLE NULL",
        "ALTER TABLE warning_events ADD COLUMN warning_explanation JSON NULL",
        "ALTER TABLE warning_events ADD INDEX idx_warning_prediction (prediction_id)",
        "ALTER TABLE warning_events ADD INDEX idx_warning_window (feature_window_id)",
        "ALTER TABLE warning_events ADD COLUMN acknowledged_at TIMESTAMP NULL",
        "ALTER TABLE warning_events ADD COLUMN resolved_at TIMESTAMP NULL",
        "ALTER TABLE warning_events ADD COLUMN latest_action TEXT NULL",
        "UPDATE warning_events SET status = 'new' WHERE status = 'pending'",
        """
        CREATE TABLE IF NOT EXISTS warning_action_logs (
          id BIGINT PRIMARY KEY AUTO_INCREMENT,
          warning_id BIGINT NOT NULL,
          from_status VARCHAR(32) NOT NULL,
          to_status VARCHAR(32) NOT NULL,
          operator VARCHAR(64) NOT NULL,
          note TEXT NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          INDEX idx_warning_action_warning_time (warning_id, created_at),
          CONSTRAINT fk_warning_action_event FOREIGN KEY (warning_id) REFERENCES warning_events(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS master_data_change_requests (
          id BIGINT PRIMARY KEY AUTO_INCREMENT,
          entity_type VARCHAR(32) NOT NULL,
          operation VARCHAR(32) NOT NULL,
          device_code VARCHAR(64) NOT NULL,
          sensor_code VARCHAR(64) NULL,
          payload_json JSON NOT NULL,
          impact_json JSON NULL,
          reason TEXT NULL,
          status VARCHAR(32) NOT NULL DEFAULT 'pending',
          requested_by VARCHAR(64) NOT NULL,
          requested_role VARCHAR(32) NOT NULL,
          approved_by VARCHAR(64) NULL,
          approved_role VARCHAR(32) NULL,
          decision_comment TEXT NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          decided_at TIMESTAMP NULL,
          INDEX idx_master_data_change_status_time (status, created_at),
          INDEX idx_master_data_change_resource (device_code, sensor_code)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS master_data_versions (
          id BIGINT PRIMARY KEY AUTO_INCREMENT,
          change_request_id BIGINT NOT NULL,
          entity_type VARCHAR(32) NOT NULL,
          device_code VARCHAR(64) NOT NULL,
          sensor_code VARCHAR(64) NULL,
          snapshot_json JSON NOT NULL,
          published_by VARCHAR(64) NOT NULL,
          published_role VARCHAR(32) NOT NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          INDEX idx_master_data_version_resource_time (device_code, sensor_code, created_at),
          CONSTRAINT fk_master_data_version_change
            FOREIGN KEY (change_request_id) REFERENCES master_data_change_requests(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
          id BIGINT PRIMARY KEY AUTO_INCREMENT,
          actor VARCHAR(64) NOT NULL,
          role VARCHAR(32) NOT NULL,
          action VARCHAR(128) NOT NULL,
          resource VARCHAR(255) NOT NULL,
          detail_json JSON NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          INDEX idx_audit_actor_time (actor, created_at),
          INDEX idx_audit_resource_time (resource, created_at)
        )
        """,
    ]
    for statement in ddl_statements:
        try:
            db.execute(text(statement))
        except Exception:
            db.rollback()


def insert_warning(
    db: Session,
    *,
    prediction_id: int,
    feature_window_id: int,
    model_version: str,
    device_code: str,
    risk_level: str,
    failure_probability: float,
    health_score: float,
    title: str,
    detail: str,
    suggested_action: str,
    warning_explanation: list[Any],
) -> None:
    db.execute(
        text(
            """
            INSERT INTO warning_events (
              prediction_id,
              feature_window_id,
              model_version,
              failure_probability,
              health_score,
              warning_explanation,
              device_code,
              risk_level,
              title,
              detail,
              suggested_action,
              status,
              latest_action
            )
            VALUES (
              :prediction_id,
              :feature_window_id,
              :model_version,
              :failure_probability,
              :health_score,
              :warning_explanation,
              :device_code,
              :risk_level,
              :title,
              :detail,
              :suggested_action,
              'new',
              '系统生成新预警'
            )
            """
        ),
        {
            "prediction_id": prediction_id,
            "feature_window_id": feature_window_id,
            "model_version": model_version,
            "failure_probability": failure_probability,
            "health_score": health_score,
            "warning_explanation": json.dumps(warning_explanation, ensure_ascii=False),
            "device_code": device_code,
            "risk_level": risk_level,
            "title": title,
            "detail": detail,
            "suggested_action": suggested_action,
        },
    )


def ensure_baseline_model(db: Session) -> None:
    db.execute(
        text(
            """
            INSERT INTO model_versions (
              model_name,
              model_type,
              version,
              metric_name,
              metric_value,
              artifact_path,
              status
            )
            VALUES (
              'rule-baseline',
              'heuristic',
              '0.1.0',
              'accuracy_placeholder',
              0,
              NULL,
              'active'
            )
            ON DUPLICATE KEY UPDATE
              metric_value = VALUES(metric_value),
              status = VALUES(status)
            """
        )
    )
