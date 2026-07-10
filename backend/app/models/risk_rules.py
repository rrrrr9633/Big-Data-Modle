from dataclasses import dataclass
from typing import Literal

RiskLevel = Literal["low", "medium", "high", "critical"]


@dataclass(frozen=True)
class RiskRule:
    level: RiskLevel
    label: str
    failure_probability_gte: float | None = None
    health_score_lt: float | None = None


RISK_RULES: tuple[RiskRule, ...] = (
    RiskRule("critical", "严重风险", failure_probability_gte=0.8, health_score_lt=30),
    RiskRule("high", "高风险", failure_probability_gte=0.6, health_score_lt=50),
    RiskRule("medium", "中风险", failure_probability_gte=0.3, health_score_lt=75),
    RiskRule("low", "低风险"),
)


def evaluate_risk_level(*, failure_probability: float, health_score: float) -> RiskLevel:
    return evaluate_risk(failure_probability=failure_probability, health_score=health_score)[0]


def evaluate_risk(
    *,
    failure_probability: float,
    health_score: float,
) -> tuple[RiskLevel, list[str]]:
    for rule in RISK_RULES:
        reasons = explain_rule_match(
            rule,
            failure_probability=failure_probability,
            health_score=health_score,
        )
        if reasons:
            return rule.level, reasons
    return "low", ["故障概率和健康评分均未触发中高风险阈值"]


def explain_risk(
    *,
    risk_level: str,
    failure_probability: float,
    health_score: float,
    top_features: list[str] | None = None,
) -> list[str]:
    rule = next((item for item in RISK_RULES if item.level == risk_level), RISK_RULES[-1])
    reasons = explain_rule_match(
        rule,
        failure_probability=failure_probability,
        health_score=health_score,
    )
    if not reasons:
        reasons = ["故障概率和健康评分均未触发中高风险阈值"]
    if top_features:
        reasons.append(f"主要贡献特征：{'、'.join(top_features[:3])}")
    return reasons


def explain_rule_match(
    rule: RiskRule,
    *,
    failure_probability: float,
    health_score: float,
) -> list[str]:
    reasons: list[str] = []
    if (
        rule.failure_probability_gte is not None
        and failure_probability >= rule.failure_probability_gte
    ):
        reasons.append(
            f"故障概率 {failure_probability:.2f}，"
            f"超过{rule.label}阈值 {rule.failure_probability_gte:.2f}"
        )
    if rule.health_score_lt is not None and health_score < rule.health_score_lt:
        reasons.append(
            f"健康评分 {health_score:.1f}，低于{rule.label}阈值 {rule.health_score_lt:g}"
        )
    return reasons
