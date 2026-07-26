from __future__ import annotations

import pytest
from roundlens_analyzer.impact.rules import RuleBasedImpactModel
from roundlens_analyzer.issues.detector import IssueDetector
from roundlens_analyzer.metrics.models import MetricResult, MetricStatus
from roundlens_analyzer.reports.builder import build_deterministic_report
from roundlens_analyzer.reports.models import CoachingReport, validate_report_references
from roundlens_analyzer.review.selector import ReviewRoundSelector
from roundlens_analyzer.strengths.detector import StrengthDetector


def metric(metric_id: str, value: float, sample: int = 30) -> MetricResult:
    return MetricResult(
        metric_id=metric_id,
        value=value,
        sample_size=sample,
        status=MetricStatus.AVAILABLE,
        confidence=0.9,
        evidence_refs=["e1", "e2"],
    )


def test_rule_impact_is_bounded_and_explainable() -> None:
    score = RuleBasedImpactModel().score_issue(
        frequency=0.8,
        confidence=0.9,
        context_weight=0.8,
        state_change=0.8,
        actionability=0.9,
        explanation=["fixture"],
    )
    assert 0 <= score.score <= 100
    assert score.level == "high"
    assert score.explanation


def test_issue_merging_combines_support_signals() -> None:
    issues = IssueDetector().detect(
        [
            metric("isolated_death_rate", 0.8),
            metric("trade_opportunity_success_rate", 0.1),
            metric("multi_angle_exposure_rate", 0.7),
        ]
    )
    assert len(issues) == 1
    assert issues[0].issue_id == "LOW_TEAM_SUPPORT_POSITIONING"
    assert len(issues[0].metric_refs) == 3


def test_strength_filter_requires_available_confident_sample() -> None:
    strengths = StrengthDetector().detect([metric("opening_duel_win_rate", 0.7)], 3)
    weak = MetricResult(
        metric_id="first_damage_conversion_rate",
        value=0.8,
        sample_size=2,
        status=MetricStatus.INSUFFICIENT_SAMPLE,
        confidence=0.2,
    )
    assert len(strengths) == 1
    assert StrengthDetector().detect([weak], 3) == []


def test_review_rounds_rank_by_impact(parsed_match) -> None:  # type: ignore[no-untyped-def]
    issue = IssueDetector().detect([metric("advantage_giveback_rate", 0.9)])[0]
    issue.evidence_refs = [parsed_match.kills[0].event_id]
    reviews = ReviewRoundSelector().select([("m1", parsed_match)], [issue])
    assert reviews[0].round_id == "m1:r1"
    assert reviews[0].event_timeline


def test_deterministic_report_validates(parsed_match) -> None:  # type: ignore[no-untyped-def]
    metrics = [
        metric("advantage_giveback_rate", 0.9),
        metric("opening_duel_win_rate", 0.7),
    ]
    issues = IssueDetector().detect(metrics)
    strengths = StrengthDetector().detect(metrics, 2)
    issues[0].evidence_refs = [parsed_match.kills[0].event_id]
    reviews = ReviewRoundSelector().select([("m1", parsed_match)], issues)
    report = build_deterministic_report(
        match_count=2,
        round_count=12,
        metrics=metrics,
        issues=issues,
        strengths=strengths,
        reviews=reviews,
        warnings=[],
    )
    assert CoachingReport.model_validate(report.model_dump())
    assert len(report.dimension_summaries) == 8


def test_report_reference_validation_rejects_unknown_id(parsed_match) -> None:  # type: ignore[no-untyped-def]
    metrics = [metric("advantage_giveback_rate", 0.9)]
    issues = IssueDetector().detect(metrics)
    issues[0].evidence_refs = [parsed_match.kills[0].event_id]
    reviews = ReviewRoundSelector().select([("m1", parsed_match)], issues)
    report = build_deterministic_report(
        match_count=1,
        round_count=6,
        metrics=metrics,
        issues=issues,
        strengths=[],
        reviews=reviews,
        warnings=[],
    )
    report.priority_issues[0].issue_id = "invented"
    with pytest.raises(ValueError, match="unknown issue_id"):
        validate_report_references(
            report,
            issue_ids={issues[0].issue_id},
            strength_ids=set(),
            round_ids={review.round_id for review in reviews},
            metric_ids={"advantage_giveback_rate"},
            evidence_ids={parsed_match.kills[0].event_id},
        )
