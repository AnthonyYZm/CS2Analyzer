from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from roundlens_analyzer.impact.rules import ImpactScore, RuleBasedImpactModel
from roundlens_analyzer.metrics.models import MetricResult, MetricStatus


class IssueCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: str
    title: str
    category: str
    metric_refs: list[str]
    sample_size: int
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[str]
    impact: ImpactScore
    next_match_rule: str
    target_metric: str


RULES = {
    "advantage_giveback_rate": (
        "ADVANTAGE_GIVEBACK",
        "人数优势后过早送回",
        "decision_making",
        0.25,
        False,
        "取得人数优势后，先确认可补枪队友与交叉火力，再离开当前安全位置。",
    ),
    "isolated_death_rate": (
        "ISOLATED_DUEL",
        "脱离团队支援的死亡",
        "teamplay",
        0.40,
        False,
        "发起交火前确认至少一名队友能在 5 秒内形成补枪；否则先收缩距离。",
    ),
    "trade_opportunity_success_rate": (
        "MISSED_TRADE_OPPORTUNITY",
        "补枪机会转化不足",
        "teamplay",
        0.45,
        True,
        "队友接触时保持可补枪距离，听到交火后先处理同一目标。",
    ),
    "first_shot_hit_rate": (
        "LOW_FIRST_SHOT_EFFICIENCY",
        "交火第一发效率偏低",
        "aim",
        0.35,
        True,
        "步枪中远距离交火先完成停稳和准星确认，再提交第一发。",
    ),
    "normalized_speed_at_first_shot": (
        "MOVING_FIRST_SHOT",
        "步枪首发时移动偏快",
        "movement",
        0.34,
        False,
        "下一场每次中远距离步枪首发前，确认速度已经降至武器最大速度的 34% 以下。",
    ),
    "first_damage_conversion_rate": (
        "FIRST_DAMAGE_NOT_CONVERTED",
        "先造成伤害后未完成交火",
        "duels",
        0.50,
        True,
        "先造成伤害后不要立即重复同节奏探身；优先换位或等待队友形成第二枪线。",
    ),
    "multi_angle_exposure_rate": (
        "MULTI_ANGLE_EXPOSURE",
        "进入交火时暴露多个角度",
        "positioning",
        0.20,
        False,
        "探点时用掩体切割视野，每次只让一个主要威胁角度可见。",
    ),
    "anti_eco_loss_rate": (
        "ANTI_ECO_ISOLATION",
        "反 ECO 回合处理不稳",
        "economy_and_objectives",
        0.20,
        False,
        "装备领先局避免单人进入近距离死角，保持双人交换和道具清点。",
    ),
    "unused_utility_value_on_death": (
        "UNUSED_UTILITY_ON_DEATH",
        "死亡时仍保留较多道具",
        "utility",
        250.0,
        False,
        "进入高风险区域前先计划一颗能建立优势的道具，不把全部道具带入死亡画面。",
    ),
}


class IssueDetector:
    def __init__(self) -> None:
        self.impact_model = RuleBasedImpactModel()

    def detect(self, metrics: list[MetricResult]) -> list[IssueCandidate]:
        candidates: list[IssueCandidate] = []
        for metric in metrics:
            rule = RULES.get(metric.metric_id)
            if (
                rule is None
                or metric.value is None
                or metric.status not in {MetricStatus.AVAILABLE, MetricStatus.ESTIMATED}
            ):
                continue
            issue_id, title, category, threshold, high_is_good, action = rule
            bad = metric.value < threshold if high_is_good else metric.value > threshold
            if not bad:
                continue
            if high_is_good:
                severity = min(1.0, (threshold - metric.value) / max(threshold, 0.01))
            else:
                severity = min(1.0, (metric.value - threshold) / max(threshold, 0.01))
            frequency = min(1.0, max(metric.value, 1 - metric.value) * severity + 0.25)
            impact = self.impact_model.score_issue(
                frequency=frequency,
                confidence=metric.confidence,
                context_weight=0.75,
                state_change=0.75 if category in {"decision_making", "teamplay"} else 0.6,
                actionability=0.9,
                explanation=[
                    f"指标 {metric.metric_id} 在 {metric.sample_size} 个样本中触发规则阈值",
                    "这是规则影响分，不是精确胜率变化",
                ],
            )
            candidates.append(
                IssueCandidate(
                    issue_id=issue_id,
                    title=title,
                    category=category,
                    metric_refs=[metric.metric_id],
                    sample_size=metric.sample_size,
                    confidence=metric.confidence,
                    evidence_refs=metric.evidence_refs,
                    impact=impact,
                    next_match_rule=action,
                    target_metric=metric.metric_id,
                )
            )
        return self._merge(candidates)

    @staticmethod
    def _merge(candidates: list[IssueCandidate]) -> list[IssueCandidate]:
        support_ids = {"ISOLATED_DUEL", "MISSED_TRADE_OPPORTUNITY", "MULTI_ANGLE_EXPOSURE"}
        support = [candidate for candidate in candidates if candidate.issue_id in support_ids]
        remaining = [candidate for candidate in candidates if candidate.issue_id not in support_ids]
        if len(support) >= 2:
            primary = max(support, key=lambda item: item.impact.score)
            primary.issue_id = "LOW_TEAM_SUPPORT_POSITIONING"
            primary.title = "脱离团队支援的过度前压"
            primary.metric_refs = sorted({ref for item in support for ref in item.metric_refs})
            primary.evidence_refs = list(
                dict.fromkeys(ref for item in support for ref in item.evidence_refs)
            )[:20]
            primary.sample_size = max(item.sample_size for item in support)
            primary.confidence = min(item.confidence for item in support)
            remaining.append(primary)
        else:
            remaining.extend(support)
        return sorted(remaining, key=lambda item: item.impact.score, reverse=True)[:5]
