from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from roundlens_analyzer.normalization.models import ParsedMatch


class MetricStatus(StrEnum):
    AVAILABLE = "available"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_SAMPLE = "insufficient_sample"


class MetricResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    value: float | None = None
    sample_size: int = 0
    status: MetricStatus
    confidence: float = Field(ge=0, le=1)
    contexts: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    calculation_version: str = "1.0.0"
    unavailable_reason: str | None = None


class MetricContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    match: ParsedMatch
    player_id: str
    trade_window_seconds: float = 5.0


def ratio_result(
    metric_id: str,
    numerator: int,
    denominator: int,
    evidence_refs: list[str],
    *,
    minimum_sample: int = 5,
    estimated: bool = False,
) -> MetricResult:
    if denominator == 0:
        return MetricResult(
            metric_id=metric_id,
            status=MetricStatus.UNAVAILABLE,
            confidence=0,
            unavailable_reason="没有符合定义的样本",
        )
    value = numerator / denominator
    confidence = min(1.0, denominator / max(minimum_sample * 2, 1))
    status = MetricStatus.ESTIMATED if estimated else MetricStatus.AVAILABLE
    if denominator < minimum_sample:
        status = MetricStatus.INSUFFICIENT_SAMPLE
    return MetricResult(
        metric_id=metric_id,
        value=value,
        sample_size=denominator,
        status=status,
        confidence=confidence,
        evidence_refs=evidence_refs[:20],
    )
