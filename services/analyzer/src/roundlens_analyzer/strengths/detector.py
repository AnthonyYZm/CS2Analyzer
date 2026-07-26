from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from roundlens_analyzer.metrics.models import MetricResult, MetricStatus


class StrengthCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strength_id: str
    title: str
    category: str
    metric_refs: list[str]
    evidence_refs: list[str]
    sample_size: int
    confidence: float = Field(ge=0, le=1)
    maintain_rule: str
    stable: bool


STRENGTH_RULES = {
    "opening_duel_win_rate": (
        "OPENING_DUEL_DISCIPLINE",
        "首次交火处理有效",
        "duels",
        0.60,
        "保持当前首轮接触前的准备节奏；不要为了扩大样本而强行寻找首杀。",
    ),
    "opening_kill_round_conversion": (
        "OPENING_CONVERSION",
        "首杀后回合转化稳定",
        "decision_making",
        0.70,
        "拿到首杀后继续优先存活并与队友建立交叉火力。",
    ),
    "trade_opportunity_success_rate": (
        "TRADE_SUPPORT",
        "补枪支援可靠",
        "teamplay",
        0.65,
        "保持可补枪距离和同目标优先级。",
    ),
    "first_damage_conversion_rate": (
        "FIRST_DAMAGE_CONVERSION",
        "先手伤害转化有效",
        "aim",
        0.65,
        "保持先手后的射击纪律，并在丢失视野时停止无信息扫射。",
    ),
}


class StrengthDetector:
    def detect(self, metrics: list[MetricResult], match_count: int) -> list[StrengthCandidate]:
        results: list[StrengthCandidate] = []
        for metric in metrics:
            rule = STRENGTH_RULES.get(metric.metric_id)
            if (
                rule is None
                or metric.value is None
                or metric.status is not MetricStatus.AVAILABLE
                or metric.confidence < 0.6
            ):
                continue
            strength_id, title, category, threshold, maintain_rule = rule
            if metric.value < threshold:
                continue
            results.append(
                StrengthCandidate(
                    strength_id=strength_id,
                    title=title if match_count > 1 else f"单场亮点：{title}",
                    category=category,
                    metric_refs=[metric.metric_id],
                    evidence_refs=metric.evidence_refs,
                    sample_size=metric.sample_size,
                    confidence=metric.confidence,
                    maintain_rule=maintain_rule,
                    stable=match_count > 1,
                )
            )
        return results[:4]
