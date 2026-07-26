from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from roundlens_analyzer.issues.detector import IssueCandidate
from roundlens_analyzer.normalization.models import ParsedMatch


class ReviewRoundCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    round_id: str
    match_id: str
    review_type: str
    map: str
    round_number: int
    key_tick: int | None = None
    issue_tags: list[str]
    impact_score: int = Field(ge=0, le=100)
    data_confidence: float = Field(ge=0, le=1)
    event_timeline: list[dict[str, object]]
    review_questions: list[str]
    recommended_action: str


class ReviewRoundSelector:
    def select(
        self,
        matches: list[tuple[str, ParsedMatch]],
        issues: list[IssueCandidate],
    ) -> list[ReviewRoundCandidate]:
        issue_by_event = {event_ref: issue for issue in issues for event_ref in issue.evidence_refs}
        candidates: list[ReviewRoundCandidate] = []
        for match_id, match in matches:
            for round_ in match.rounds:
                events = [kill for kill in match.kills if kill.round_id == round_.round_id]
                tagged = [
                    issue_by_event[kill.event_id]
                    for kill in events
                    if kill.event_id in issue_by_event
                ]
                if not tagged:
                    continue
                unique_tags = list(dict.fromkeys(issue.issue_id for issue in tagged))
                primary = max(tagged, key=lambda issue: issue.impact.score)
                timeline: list[dict[str, object]] = [
                    {
                        "tick": kill.tick,
                        "type": "kill",
                        "attacker_id": kill.attacker_id,
                        "victim_id": kill.victim_id,
                        "weapon": kill.weapon,
                    }
                    for kill in events
                ]
                candidates.append(
                    ReviewRoundCandidate(
                        round_id=f"{match_id}:{round_.round_id}",
                        match_id=match_id,
                        review_type="high_impact_issue",
                        map=match.map_name,
                        round_number=round_.number,
                        key_tick=events[0].tick if events else None,
                        issue_tags=unique_tags,
                        impact_score=primary.impact.score,
                        data_confidence=primary.confidence,
                        event_timeline=timeline,
                        review_questions=["当时是否有更安全、仍可被队友补枪的位置？"],
                        recommended_action=primary.next_match_rule,
                    )
                )
        return sorted(candidates, key=lambda item: item.impact_score, reverse=True)[:8]
