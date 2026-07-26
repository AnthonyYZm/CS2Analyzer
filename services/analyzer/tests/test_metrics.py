from __future__ import annotations

from roundlens_analyzer.encounters.detector import EncounterDetector
from roundlens_analyzer.metrics.core import (
    AdvantageConversionCalculator,
    AdvantageGivebackCalculator,
    AntiEcoLossCalculator,
    FirstDamageConversionCalculator,
    FirstShotHitCalculator,
    IsolatedDeathCalculator,
    MultiAngleExposureCalculator,
    NormalizedSpeedCalculator,
    OpeningDeathCalculator,
    OpeningMetricCalculator,
    TradeSuccessCalculator,
    UnusedUtilityCalculator,
)
from roundlens_analyzer.metrics.models import MetricContext, MetricStatus
from roundlens_analyzer.normalization.models import DataQuality, Kill, ParsedMatch


def test_missing_capability_is_unavailable_not_zero() -> None:
    match = ParsedMatch(
        parser_name="fixture", parser_version="1", map_name="unknown", quality=DataQuality()
    )
    result = OpeningMetricCalculator().calculate(MetricContext(match=match, player_id="me"))
    assert result.status is MetricStatus.UNAVAILABLE
    assert result.value is None


def test_opening_duel_and_opening_death(parsed_match: ParsedMatch) -> None:
    context = MetricContext(match=parsed_match, player_id="me")
    opening = OpeningMetricCalculator().calculate(context)
    deaths = OpeningDeathCalculator().calculate(context)
    assert opening.sample_size == 6
    assert opening.value == 5 / 6
    assert deaths.value == 1 / 6


def test_advantage_conversion_and_giveback(parsed_match: ParsedMatch) -> None:
    context = MetricContext(match=parsed_match, player_id="me")
    conversion = AdvantageConversionCalculator().calculate(context)
    giveback = AdvantageGivebackCalculator().calculate(context)
    assert conversion.sample_size == 6
    assert conversion.value == 5 / 6
    assert giveback.value == 5 / 6


def test_trade_window_and_isolated_death(parsed_match: ParsedMatch) -> None:
    parsed_match.kills.extend(
        [
            Kill(
                event_id="trade-opportunity",
                round_id="r1",
                tick=400,
                attacker_id="enemy3",
                victim_id="mate",
                attacker_side="CT",
                victim_side="T",
            ),
            Kill(
                event_id="trade-success",
                round_id="r1",
                tick=464,
                attacker_id="me",
                victim_id="enemy3",
                attacker_side="T",
                victim_side="CT",
            ),
        ]
    )
    context = MetricContext(match=parsed_match, player_id="me", trade_window_seconds=5)
    trade = TradeSuccessCalculator().calculate(context)
    isolated = IsolatedDeathCalculator().calculate(context)
    assert trade.status is MetricStatus.INSUFFICIENT_SAMPLE
    assert trade.value == 1
    assert isolated.sample_size == 7
    assert isolated.value == 1 / 7


def test_anti_eco_and_unused_utility(parsed_match: ParsedMatch) -> None:
    context = MetricContext(match=parsed_match, player_id="me")
    anti_eco = AntiEcoLossCalculator().calculate(context)
    utility = UnusedUtilityCalculator().calculate(context)
    assert anti_eco.value == 1 / 6
    assert utility.value == 300
    assert utility.sample_size == 6


def test_encounter_segmentation_and_first_damage(parsed_match: ParsedMatch) -> None:
    encounters = EncounterDetector().detect(parsed_match, "me")
    conversion = FirstDamageConversionCalculator().calculate(
        MetricContext(match=parsed_match, player_id="me")
    )
    assert len(encounters) >= 6
    assert all(encounter.start_tick <= encounter.end_tick for encounter in encounters)
    assert conversion.sample_size == 6


def test_first_shot_speed_and_multi_angle(parsed_match: ParsedMatch) -> None:
    context = MetricContext(match=parsed_match, player_id="me")
    first_shot = FirstShotHitCalculator().calculate(context)
    speed = NormalizedSpeedCalculator().calculate(context)
    exposure = MultiAngleExposureCalculator().calculate(context)
    assert first_shot.value == 0.5
    assert speed.value is not None and speed.value < 0.15
    assert exposure.value == 0.5
    assert exposure.status in {MetricStatus.ESTIMATED, MetricStatus.INSUFFICIENT_SAMPLE}
