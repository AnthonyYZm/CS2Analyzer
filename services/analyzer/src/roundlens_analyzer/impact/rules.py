from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ImpactComponents(BaseModel):
    model_config = ConfigDict(extra="forbid")

    round_context: float = Field(ge=0, le=1)
    state_change: float = Field(ge=0, le=1)
    frequency: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    actionability: float = Field(ge=0, le=1)


class ImpactScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=0, le=100)
    level: str
    components: ImpactComponents
    explanation: list[str]


class RuleBasedImpactModel:
    def score_issue(
        self,
        *,
        frequency: float,
        confidence: float,
        context_weight: float,
        state_change: float,
        actionability: float,
        explanation: list[str],
    ) -> ImpactScore:
        components = ImpactComponents(
            round_context=max(0, min(context_weight, 1)),
            state_change=max(0, min(state_change, 1)),
            frequency=max(0, min(frequency, 1)),
            confidence=max(0, min(confidence, 1)),
            actionability=max(0, min(actionability, 1)),
        )
        weighted = (
            components.round_context * 0.22
            + components.state_change * 0.25
            + components.frequency * 0.20
            + components.confidence * 0.18
            + components.actionability * 0.15
        )
        score = round(weighted * 100)
        level = "high" if score >= 70 else "medium" if score >= 45 else "low"
        return ImpactScore(
            score=score,
            level=level,
            components=components,
            explanation=explanation,
        )
