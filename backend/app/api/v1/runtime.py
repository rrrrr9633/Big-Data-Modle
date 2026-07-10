from __future__ import annotations

import socket
from collections.abc import Callable
from typing import Annotated, Any

from app.core.config import settings
from app.core.database import engine
from app.models.registry import get_active_model_state
from app.ops.backup_status import get_backup_status
from app.ops.emqx import get_emqx_status
from app.ops.kafka_lag import get_streams_status
from app.ops.observability import get_observability_status
from app.ops.supervision import get_supervision_status
from app.quality.idempotency import create_redis_client
from app.security.auth import CurrentUser
from app.security.policies import require_permission
from app.tsdb.client import tsdb_connection
from fastapi import APIRouter, Depends
from sqlalchemy import text

router = APIRouter()


OpsUser = Annotated[CurrentUser, Depends(require_permission("ops.read"))]


@router.get("/diagnostics")
def get_runtime_diagnostics(_user: OpsUser) -> dict[str, Any]:
    return build_runtime_diagnostics()


@router.get("/streams")
def get_runtime_streams(_user: OpsUser) -> dict[str, Any]:
    return get_streams_status()


@router.get("/emqx")
def get_runtime_emqx(_user: OpsUser) -> dict[str, Any]:
    return get_emqx_status()


@router.get("/backups")
def get_runtime_backups(_user: OpsUser) -> dict[str, Any]:
    return get_backup_status()


@router.get("/observability")
def get_runtime_observability(_user: OpsUser) -> dict[str, Any]:
    return get_observability_status()


@router.get("/supervision")
def get_runtime_supervision(_user: OpsUser) -> dict[str, Any]:
    return get_supervision_status()


def build_runtime_diagnostics() -> dict[str, Any]:
    dependencies = [_check_mysql(), _check_tsdb(), _check_redis(), _check_kafka(), _check_mqtt()]
    stream_consumers = _stream_consumer_states()
    model_state = get_active_model_state()
    production_gaps = _production_gaps(dependencies, stream_consumers, model_state.available)
    operations_readiness = build_operations_readiness(
        dependencies=dependencies,
        stream_consumers=stream_consumers,
        active_model_available=model_state.available,
    )
    return {
        "status": "ready" if not production_gaps else "degraded",
        "ingress": {
            "primary": "mqtt",
            "mqtt_topic": settings.mqtt_telemetry_topic,
            "raw_topic": settings.kafka_telemetry_raw_topic,
            "broker": f"{settings.mqtt_broker_host}:{settings.mqtt_broker_port}",
        },
        "dependencies": dependencies,
        "stream_consumers": stream_consumers,
        "active_model": {
            "available": model_state.available,
            "saved_at": getattr(model_state, "saved_at", None),
            "model_names": getattr(model_state, "model_names", None) or [],
        },
        "operations_readiness": operations_readiness,
        "production_gaps": production_gaps,
    }


def build_operations_readiness(
    *,
    dependencies: list[dict[str, Any]],
    stream_consumers: list[dict[str, Any]],
    active_model_available: bool,
) -> list[dict[str, Any]]:
    dependency_ok = all(item["status"] == "ok" for item in dependencies)
    consumers_ok = all(item["enabled"] for item in stream_consumers)
    auth_secret_ok = (
        not settings.auth_enabled or settings.auth_token_secret != "change-me-in-production"
    )
    return [
        {
            "area": "security",
            "status": "ok" if auth_secret_ok and settings.auth_enabled else "warning",
            "items": [
                "AUTH_TOKEN_SECRET 已更换"
                if auth_secret_ok
                else "AUTH_TOKEN_SECRET 仍为默认值，必须更换",
                "AUTH_ENABLED 已开启"
                if settings.auth_enabled
                else "AUTH_ENABLED 未开启，生产环境必须启用登录鉴权",
            ],
        },
        {
            "area": "streaming",
            "status": "ok" if dependency_ok and consumers_ok else "warning",
            "items": [
                "外部依赖连接正常" if dependency_ok else "存在不可用外部依赖",
                "后台消费者全部启用" if consumers_ok else "存在未启用后台消费者",
            ],
        },
        {
            "area": "model",
            "status": "ok" if active_model_available else "warning",
            "items": [
                "active 模型可用"
                if active_model_available
                else "active 模型缺失，推理链路不能形成生产预测",
                "仍需现场历史数据训练、阈值标定、漂移监测和误报复核",
            ],
        },
        {
            "area": "backup",
            "status": "warning",
            "items": [
                "需要为 MySQL 配置定时备份和恢复演练",
                "需要为 TimescaleDB 配置时序数据保留、压缩和备份策略",
                "需要为 Kafka topic 配置保留周期、磁盘告警和重放策略",
            ],
        },
        {
            "area": "supervision",
            "status": "warning",
            "items": [
                "需要用 systemd / supervisor / Docker restart policy 守护 FastAPI 与消费者进程",
                "需要接入 EMQX、Kafka、Redis、TSDB、MySQL 指标告警",
                "需要把 audit_logs、应用日志和消费者错误日志纳入日志审计",
            ],
        },
    ]


def _production_gaps(
    dependencies: list[dict[str, Any]],
    stream_consumers: list[dict[str, Any]],
    active_model_available: bool,
) -> list[str]:
    gaps = [
        f"{item['name']} 连接不可用：{item.get('detail') or item.get('status')}"
        for item in dependencies
        if item["status"] != "ok"
    ]
    gaps.extend(f"{item['name']} 消费者未启用" for item in stream_consumers if not item["enabled"])
    if not active_model_available:
        gaps.append("active 模型未训练，推理链路不能形成生产预测")
    return gaps


def _stream_consumer_states() -> list[dict[str, Any]]:
    return [
        {
            "name": "mqtt-to-kafka",
            "enabled": settings.mqtt_to_kafka_enabled,
            "source": "MQTT",
            "target": settings.kafka_telemetry_raw_topic,
            "group_id": settings.mqtt_client_id,
            "responsibility": "订阅 EMQX 工厂遥测主题并写入 Kafka raw topic",
        },
        {
            "name": "raw-telemetry",
            "enabled": settings.raw_telemetry_consumer_enabled,
            "source": settings.kafka_telemetry_raw_topic,
            "target": settings.kafka_telemetry_cleaned_topic,
            "group_id": settings.kafka_raw_group_id,
            "responsibility": "解析、清洗、幂等、点位目录校验并隔离异常遥测",
        },
        {
            "name": "cleaned-telemetry",
            "enabled": settings.cleaned_telemetry_consumer_enabled,
            "source": settings.kafka_telemetry_cleaned_topic,
            "target": "TimescaleDB / Redis",
            "group_id": settings.kafka_cleaned_group_id,
            "responsibility": "写入 TSDB 历史点位并更新 Redis 实时快照",
        },
        {
            "name": "feature-window",
            "enabled": settings.feature_consumer_enabled,
            "source": settings.kafka_telemetry_cleaned_topic,
            "target": settings.kafka_features_windowed_topic,
            "group_id": settings.kafka_feature_group_id,
            "responsibility": "按设备构建特征窗口并发布窗口事件",
        },
        {
            "name": "async-inference",
            "enabled": settings.inference_consumer_enabled,
            "source": settings.kafka_features_windowed_topic,
            "target": (
                f"{settings.kafka_predictions_created_topic} / "
                f"{settings.kafka_warnings_created_topic}"
            ),
            "group_id": settings.kafka_inference_group_id,
            "responsibility": "执行模型推理，生成预测日志和预警事件",
        },
    ]


def _check_mysql() -> dict[str, str]:
    return _safe_check("mysql", _ping_mysql)


def _check_tsdb() -> dict[str, str]:
    return _safe_check("tsdb", _ping_tsdb)


def _check_redis() -> dict[str, str]:
    return _safe_check("redis", _ping_redis)


def _check_kafka() -> dict[str, str]:
    return _safe_check("kafka", _ping_kafka)


def _check_mqtt() -> dict[str, str]:
    return _safe_check("mqtt", _ping_mqtt)


def _safe_check(name: str, probe: Callable[[], None]) -> dict[str, str]:
    try:
        probe()
    except Exception as exc:
        return {"name": name, "status": "error", "detail": str(exc)}
    return {"name": name, "status": "ok"}


def _ping_mysql() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def _ping_tsdb() -> None:
    with tsdb_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")


def _ping_redis() -> None:
    client = create_redis_client()
    try:
        client.ping()
    finally:
        client.close()


def _ping_kafka() -> None:
    try:
        from kafka import KafkaAdminClient
    except ImportError as exc:
        raise RuntimeError("kafka-python is not installed") from exc
    client = KafkaAdminClient(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        api_version=tuple(int(part) for part in settings.kafka_api_version.split(".")),
        request_timeout_ms=3000,
    )
    try:
        client.list_topics()
    finally:
        client.close()


def _ping_mqtt() -> None:
    with socket.create_connection(
        (settings.mqtt_broker_host, settings.mqtt_broker_port),
        timeout=3,
    ):
        return None
