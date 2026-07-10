from app.models.risk_rules import explain_risk
from app.schemas.timeseries import MaintenanceAdvice, PredictionResult

ACTION_MAP = {
    "low": "保持常规巡检，继续观察健康评分变化",
    "medium": "安排传感器复核并观察趋势，必要时提高采样频率",
    "high": "安排计划性停机检查关键部件，重点核查异常来源",
    "critical": "立即触发告警并执行停机排查，优先处理异常指标和快速劣化趋势",
}

REASON_LABELS = {
    "peak": "峰值异常",
    "trend": "趋势劣化",
    "volatility": "波动增强",
    "quality": "数据质量下降",
    "rotational_speed": "转速偏离",
    "torque": "转矩异常",
    "tool_wear": "刀具磨损",
    "feature_distribution": "特征分布异常",
}


def generate_maintenance_advice(result: PredictionResult) -> MaintenanceAdvice:
    reason_text = _format_reasons(result.anomaly_reasons)
    rule_text = "；".join(
        explain_risk(
            risk_level=result.risk_level,
            failure_probability=result.failure_probability,
            health_score=result.health_score,
        )
    )
    trend_text = "趋势稳定" if result.trend_factor < 0.3 else "趋势存在劣化"

    return MaintenanceAdvice(
        device_id=result.device_id,
        risk_level=result.risk_level,
        title=f"设备风险等级：{result.risk_level}",
        detail=(
            f"{rule_text}；"
            f"异常分数 {result.anomaly_score:.2f}，"
            f"{trend_text}，"
            f"主要原因：{reason_text}"
        ),
        suggested_action=_build_action(result),
    )


def _format_reasons(reasons: list[str]) -> str:
    if not reasons:
        return "未发现显著异常因子"
    return "、".join(REASON_LABELS.get(reason, reason) for reason in reasons)


def _build_action(result: PredictionResult) -> str:
    actions = [ACTION_MAP[result.risk_level]]
    if result.anomaly_score >= 0.65:
        actions.append("异常分数已超过阈值，建议复核传感器与关键机械部件")
    if result.trend_factor >= 0.5:
        actions.append("趋势劣化明显，建议缩短巡检周期")
    if result.quality_score < 0.8:
        actions.append("数据质量下降，建议先校验采集链路")
    return "；".join(actions)