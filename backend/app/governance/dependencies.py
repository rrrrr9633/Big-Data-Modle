from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DependencyImpact:
    publish_allowed: bool
    blockers: list[str]
    required_actions: list[str]
    stale_gateway_ids: list[str]


def assess_sensor_point_change(
    *,
    device_code: str,
    sensor_code: str,
    current_point: dict[str, Any],
    proposed_point: dict[str, Any],
    active_models: list[dict[str, Any]],
    gateway_configs: list[dict[str, Any]],
) -> DependencyImpact:
    blockers: list[str] = []
    required_actions: list[str] = []
    old_feature = current_point.get("feature_name")
    new_feature = proposed_point.get("feature_name", old_feature)
    feature_changed = old_feature != new_feature

    if feature_changed and old_feature:
        for model in active_models:
            if old_feature in set(model.get("features") or []):
                blockers.append(
                    "活跃模型 "
                    f"{model.get('model_name')}@{model.get('version')} 依赖旧特征 {old_feature}"
                )
        if blockers:
            required_actions.append("训练并审批使用新特征的模型版本后再发布")

    gateway_fields = {"protocol", "source_address", "protocol_options", "feature_name"}
    gateway_change = any(
        proposed_point.get(field, current_point.get(field)) != current_point.get(field)
        for field in gateway_fields
    )
    stale_gateway_ids = sorted(
        {
            str(config["gateway_id"])
            for config in gateway_configs
            if config.get("device_code") == device_code
            and config.get("point_code") == sensor_code
            and (not feature_changed or config.get("feature_name") == old_feature)
        }
    )
    if gateway_change:
        required_actions.append("重新导出并灰度发布边缘网关配置")

    return DependencyImpact(
        publish_allowed=not blockers,
        blockers=blockers,
        required_actions=required_actions,
        stale_gateway_ids=stale_gateway_ids,
    )
