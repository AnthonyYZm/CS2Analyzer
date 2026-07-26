from __future__ import annotations

from collections import defaultdict
from typing import Protocol

from roundlens_analyzer.encounters.detector import EncounterDetector
from roundlens_analyzer.metrics.models import (
    MetricContext,
    MetricResult,
    MetricStatus,
    ratio_result,
)
from roundlens_analyzer.normalization.models import Kill, Round, Shot


class MetricCalculator(Protocol):
    metric_id: str

    def is_available(self, context: MetricContext) -> bool: ...

    def calculate(self, context: MetricContext) -> MetricResult: ...


def _unavailable(metric_id: str, reason: str) -> MetricResult:
    return MetricResult(
        metric_id=metric_id,
        status=MetricStatus.UNAVAILABLE,
        confidence=0,
        unavailable_reason=reason,
    )


def _player_side(kills: list[Kill], player_id: str) -> str | None:
    for kill in kills:
        if kill.attacker_id == player_id and kill.attacker_side:
            return kill.attacker_side
        if kill.victim_id == player_id and kill.victim_side:
            return kill.victim_side
    return None


class OpeningMetricCalculator:
    metric_id = "opening_duel_win_rate"

    def is_available(self, context: MetricContext) -> bool:
        return context.match.quality.supports("core_events") and bool(context.match.rounds)

    def calculate(self, context: MetricContext) -> MetricResult:
        if not self.is_available(context):
            return _unavailable(self.metric_id, "缺少核心回合或击杀事件")
        attempts = wins = 0
        evidence: list[str] = []
        for round_ in context.match.rounds:
            kills = _valid_round_kills(context, round_)
            if not kills:
                continue
            opening = kills[0]
            if context.player_id not in {opening.attacker_id, opening.victim_id}:
                continue
            attempts += 1
            evidence.append(opening.event_id)
            if opening.attacker_id == context.player_id:
                wins += 1
        return ratio_result(self.metric_id, wins, attempts, evidence)


class OpeningAttemptCalculator:
    metric_id = "opening_duel_attempt_rate"

    def is_available(self, context: MetricContext) -> bool:
        return context.match.quality.supports("core_events") and bool(context.match.rounds)

    def calculate(self, context: MetricContext) -> MetricResult:
        if not self.is_available(context):
            return _unavailable(self.metric_id, "缺少核心回合或击杀事件")
        eligible = attempts = 0
        evidence: list[str] = []
        for round_ in context.match.rounds:
            kills = _valid_round_kills(context, round_)
            if not kills:
                continue
            eligible += 1
            opening = kills[0]
            if context.player_id in {opening.attacker_id, opening.victim_id}:
                attempts += 1
                evidence.append(opening.event_id)
        return ratio_result(self.metric_id, attempts, eligible, evidence)


class OpeningDeathCalculator:
    metric_id = "opening_death_rate"

    def is_available(self, context: MetricContext) -> bool:
        return context.match.quality.supports("core_events") and bool(context.match.rounds)

    def calculate(self, context: MetricContext) -> MetricResult:
        if not self.is_available(context):
            return _unavailable(self.metric_id, "缺少核心回合或击杀事件")
        eligible = deaths = 0
        evidence: list[str] = []
        for round_ in context.match.rounds:
            kills = _valid_round_kills(context, round_)
            if not kills:
                continue
            eligible += 1
            if kills[0].victim_id == context.player_id:
                deaths += 1
                evidence.append(kills[0].event_id)
        return ratio_result(self.metric_id, deaths, eligible, evidence)


class OpeningConversionCalculator:
    metric_id = "opening_kill_round_conversion"

    def is_available(self, context: MetricContext) -> bool:
        return context.match.quality.supports("core_events")

    def calculate(self, context: MetricContext) -> MetricResult:
        if not self.is_available(context):
            return _unavailable(self.metric_id, "缺少核心回合或击杀事件")
        opportunities = converted = 0
        evidence: list[str] = []
        for round_ in context.match.rounds:
            kills = _valid_round_kills(context, round_)
            if not kills or kills[0].attacker_id != context.player_id:
                continue
            side = kills[0].attacker_side
            opportunities += 1
            evidence.append(round_.round_id)
            if side and round_.winner_side == side:
                converted += 1
        return ratio_result(self.metric_id, converted, opportunities, evidence)


class PostOpeningSurvivalCalculator:
    metric_id = "post_opening_kill_survival_rate"

    def is_available(self, context: MetricContext) -> bool:
        return context.match.quality.supports("core_events")

    def calculate(self, context: MetricContext) -> MetricResult:
        if not self.is_available(context):
            return _unavailable(self.metric_id, "缺少核心回合或击杀事件")
        opportunities = survived = 0
        evidence: list[str] = []
        for round_ in context.match.rounds:
            kills = _valid_round_kills(context, round_)
            if not kills or kills[0].attacker_id != context.player_id:
                continue
            opportunities += 1
            if not any(kill.victim_id == context.player_id for kill in kills[1:]):
                survived += 1
                evidence.append(round_.round_id)
        return ratio_result(self.metric_id, survived, opportunities, evidence)


class AdvantageConversionCalculator:
    metric_id = "five_v_four_conversion_rate"

    def is_available(self, context: MetricContext) -> bool:
        return context.match.quality.supports("core_events")

    def calculate(self, context: MetricContext) -> MetricResult:
        if not self.is_available(context):
            return _unavailable(self.metric_id, "缺少队伍击杀与回合结果")
        opportunities = converted = 0
        evidence: list[str] = []
        for round_ in context.match.rounds:
            kills = _valid_round_kills(context, round_)
            player_side = _player_side(kills, context.player_id)
            if not player_side:
                continue
            advantage = next(
                (
                    kill
                    for kill in kills
                    if kill.attacker_side == player_side and kill.victim_side != player_side
                ),
                None,
            )
            if not advantage:
                continue
            opportunities += 1
            evidence.append(advantage.event_id)
            if round_.winner_side == player_side:
                converted += 1
        return ratio_result(self.metric_id, converted, opportunities, evidence)


class AdvantageGivebackCalculator:
    metric_id = "advantage_giveback_rate"

    def is_available(self, context: MetricContext) -> bool:
        return context.match.quality.supports("core_events")

    def calculate(self, context: MetricContext) -> MetricResult:
        if not self.is_available(context):
            return _unavailable(self.metric_id, "缺少队伍击杀事件")
        opportunities = givebacks = 0
        evidence: list[str] = []
        for round_ in context.match.rounds:
            kills = _valid_round_kills(context, round_)
            player_side = _player_side(kills, context.player_id)
            if not player_side:
                continue
            for index, kill in enumerate(kills):
                if kill.attacker_side == player_side and kill.victim_side != player_side:
                    opportunities += 1
                    own_next_death = next(
                        (later for later in kills[index + 1 :] if later.victim_side == player_side),
                        None,
                    )
                    if own_next_death and own_next_death.victim_id == context.player_id:
                        givebacks += 1
                        evidence.append(own_next_death.event_id)
                    break
        return ratio_result(self.metric_id, givebacks, opportunities, evidence)


class TradeSuccessCalculator:
    metric_id = "trade_opportunity_success_rate"

    def is_available(self, context: MetricContext) -> bool:
        return context.match.quality.supports("core_events")

    def calculate(self, context: MetricContext) -> MetricResult:
        if not self.is_available(context):
            return _unavailable(self.metric_id, "缺少击杀事件")
        tick_rate = context.match.tick_rate or 64.0
        max_ticks = int(context.trade_window_seconds * tick_rate)
        opportunities = successes = 0
        evidence: list[str] = []
        for round_ in context.match.rounds:
            kills = _valid_round_kills(context, round_)
            player_side = _player_side(kills, context.player_id)
            for death in kills:
                if not player_side or death.victim_side != player_side:
                    continue
                if death.victim_id == context.player_id or not death.attacker_id:
                    continue
                opportunities += 1
                trade = next(
                    (
                        later
                        for later in kills
                        if later.tick >= death.tick
                        and later.tick - death.tick <= max_ticks
                        and later.attacker_id == context.player_id
                        and later.victim_id == death.attacker_id
                    ),
                    None,
                )
                if trade:
                    successes += 1
                    evidence.append(trade.event_id)
        return ratio_result(
            self.metric_id,
            successes,
            opportunities,
            evidence,
            minimum_sample=8,
            estimated=True,
        )


class IsolatedDeathCalculator:
    metric_id = "isolated_death_rate"

    def is_available(self, context: MetricContext) -> bool:
        return context.match.quality.supports("core_events")

    def calculate(self, context: MetricContext) -> MetricResult:
        if not self.is_available(context):
            return _unavailable(self.metric_id, "缺少击杀事件")
        tick_rate = context.match.tick_rate or 64.0
        max_ticks = int(context.trade_window_seconds * tick_rate)
        deaths = isolated = 0
        evidence: list[str] = []
        for round_ in context.match.rounds:
            kills = _valid_round_kills(context, round_)
            player_side = _player_side(kills, context.player_id)
            for death in kills:
                if death.victim_id != context.player_id or not death.attacker_id:
                    continue
                deaths += 1
                traded = any(
                    later.tick >= death.tick
                    and later.tick - death.tick <= max_ticks
                    and later.attacker_side == player_side
                    and later.victim_id == death.attacker_id
                    for later in kills
                )
                if not traded:
                    isolated += 1
                    evidence.append(death.event_id)
        return ratio_result(
            self.metric_id,
            isolated,
            deaths,
            evidence,
            minimum_sample=8,
            estimated=True,
        )


class AntiEcoLossCalculator:
    metric_id = "anti_eco_loss_rate"

    def is_available(self, context: MetricContext) -> bool:
        return context.match.quality.supports("core_events") and any(
            round_.t_equipment_value is not None and round_.ct_equipment_value is not None
            for round_ in context.match.rounds
        )

    def calculate(self, context: MetricContext) -> MetricResult:
        if not self.is_available(context):
            return _unavailable(self.metric_id, "缺少双方团队装备价值")
        opportunities = losses = 0
        evidence: list[str] = []
        for round_ in context.match.rounds:
            kills = _valid_round_kills(context, round_)
            player_side = _player_side(kills, context.player_id)
            if (
                not player_side
                or round_.t_equipment_value is None
                or round_.ct_equipment_value is None
            ):
                continue
            own = round_.t_equipment_value if player_side == "T" else round_.ct_equipment_value
            enemy = round_.ct_equipment_value if player_side == "T" else round_.t_equipment_value
            if enemy <= 0 or own / enemy < 1.8:
                continue
            opportunities += 1
            if round_.winner_side != player_side:
                losses += 1
                evidence.append(round_.round_id)
        return ratio_result(self.metric_id, losses, opportunities, evidence)


class UnusedUtilityCalculator:
    metric_id = "unused_utility_value_on_death"

    def is_available(self, context: MetricContext) -> bool:
        return bool(context.match.player_round_states)

    def calculate(self, context: MetricContext) -> MetricResult:
        if not self.is_available(context):
            return _unavailable(self.metric_id, "缺少死亡时库存字段")
        values = [
            state.utility_value_on_death
            for state in context.match.player_round_states
            if state.player_id == context.player_id and state.utility_value_on_death is not None
        ]
        if not values:
            return _unavailable(self.metric_id, "没有可用的死亡时道具样本")
        return MetricResult(
            metric_id=self.metric_id,
            value=sum(values) / len(values),
            sample_size=len(values),
            status=(
                MetricStatus.AVAILABLE if len(values) >= 8 else MetricStatus.INSUFFICIENT_SAMPLE
            ),
            confidence=min(1.0, len(values) / 16),
            evidence_refs=[state.round_id for state in context.match.player_round_states[:20]],
        )


class FirstShotHitCalculator:
    metric_id = "first_shot_hit_rate"

    def is_available(self, context: MetricContext) -> bool:
        return context.match.quality.supports("shots") and any(
            shot.player_id == context.player_id and shot.hit is not None
            for shot in context.match.shots
        )

    def calculate(self, context: MetricContext) -> MetricResult:
        if not self.is_available(context):
            return _unavailable(self.metric_id, "缺少可关联到交火的逐发命中数据")
        grouped: dict[tuple[str, str], list[Shot]] = defaultdict(list)
        for shot in context.match.shots:
            if shot.player_id == context.player_id and shot.target_id:
                grouped[(shot.round_id, shot.target_id)].append(shot)
        first_shots = [min(shots, key=lambda shot: shot.tick) for shots in grouped.values()]
        return ratio_result(
            self.metric_id,
            sum(shot.hit is True for shot in first_shots),
            len(first_shots),
            [shot.event_id for shot in first_shots if shot.hit],
            minimum_sample=15,
            estimated=any(shot.association_status.value == "estimated" for shot in first_shots),
        )


class NormalizedSpeedCalculator:
    metric_id = "normalized_speed_at_first_shot"

    def is_available(self, context: MetricContext) -> bool:
        return context.match.quality.supports("shots", "velocity") and any(
            shot.player_id == context.player_id
            and shot.speed is not None
            and shot.weapon_max_speed not in {None, 0}
            for shot in context.match.shots
        )

    def calculate(self, context: MetricContext) -> MetricResult:
        if not self.is_available(context):
            return _unavailable(self.metric_id, "缺少开火瞬间速度或武器最大速度")
        grouped: dict[tuple[str, str], list[Shot]] = defaultdict(list)
        for shot in context.match.shots:
            if shot.player_id == context.player_id and shot.target_id:
                grouped[(shot.round_id, shot.target_id)].append(shot)
        first_shots = [min(shots, key=lambda shot: shot.tick) for shots in grouped.values()]
        values: list[float] = []
        for shot in first_shots:
            if (
                shot.speed is not None
                and shot.weapon_max_speed is not None
                and shot.weapon_max_speed != 0
            ):
                values.append(shot.speed / shot.weapon_max_speed)
        if not values:
            return _unavailable(self.metric_id, "没有可计算的首发速度样本")
        return MetricResult(
            metric_id=self.metric_id,
            value=sum(values) / len(values),
            sample_size=len(values),
            status=(
                MetricStatus.ESTIMATED if len(values) >= 15 else MetricStatus.INSUFFICIENT_SAMPLE
            ),
            confidence=min(0.8, len(values) / 30),
            evidence_refs=[shot.event_id for shot in first_shots[:20]],
        )


class FirstDamageConversionCalculator:
    metric_id = "first_damage_conversion_rate"

    def is_available(self, context: MetricContext) -> bool:
        return context.match.quality.supports("core_events") and bool(context.match.damages)

    def calculate(self, context: MetricContext) -> MetricResult:
        if not self.is_available(context):
            return _unavailable(self.metric_id, "缺少伤害与击杀事件")
        encounters = EncounterDetector().detect(context.match, context.player_id)
        opportunities = [
            encounter for encounter in encounters if encounter.first_damage_side == "player"
        ]
        return ratio_result(
            self.metric_id,
            sum(encounter.outcome == "won" for encounter in opportunities),
            len(opportunities),
            [encounter.encounter_id for encounter in opportunities if encounter.outcome != "won"],
            minimum_sample=15,
        )


class MultiAngleExposureCalculator:
    metric_id = "multi_angle_exposure_rate"

    def is_available(self, context: MetricContext) -> bool:
        return context.match.quality.supports("visibility") and any(
            shot.player_id == context.player_id and shot.visible_enemy_count is not None
            for shot in context.match.shots
        )

    def calculate(self, context: MetricContext) -> MetricResult:
        if not self.is_available(context):
            return _unavailable(self.metric_id, "缺少可靠可见性或同时暴露敌人数")
        samples = [
            shot
            for shot in context.match.shots
            if shot.player_id == context.player_id and shot.visible_enemy_count is not None
        ]
        return ratio_result(
            self.metric_id,
            sum((shot.visible_enemy_count or 0) >= 2 for shot in samples),
            len(samples),
            [shot.event_id for shot in samples if (shot.visible_enemy_count or 0) >= 2],
            minimum_sample=15,
            estimated=context.match.quality.visibility.value == "estimated",
        )


CALCULATORS: tuple[MetricCalculator, ...] = (
    OpeningAttemptCalculator(),
    OpeningMetricCalculator(),
    OpeningDeathCalculator(),
    OpeningConversionCalculator(),
    PostOpeningSurvivalCalculator(),
    AdvantageConversionCalculator(),
    AdvantageGivebackCalculator(),
    TradeSuccessCalculator(),
    IsolatedDeathCalculator(),
    AntiEcoLossCalculator(),
    UnusedUtilityCalculator(),
    FirstShotHitCalculator(),
    NormalizedSpeedCalculator(),
    FirstDamageConversionCalculator(),
    MultiAngleExposureCalculator(),
)


def calculate_all(context: MetricContext) -> list[MetricResult]:
    results: list[MetricResult] = []
    for calculator in CALCULATORS:
        try:
            results.append(calculator.calculate(context))
        except (ArithmeticError, KeyError, TypeError, ValueError) as exc:
            results.append(_unavailable(calculator.metric_id, f"指标计算失败：{exc}"))
    return results


def _valid_round_kills(context: MetricContext, round_: Round) -> list[Kill]:
    return sorted(
        (
            kill
            for kill in context.match.kills
            if kill.round_id == round_.round_id
            and kill.attacker_id
            and kill.attacker_id != kill.victim_id
            and (not kill.attacker_side or kill.attacker_side != kill.victim_side)
        ),
        key=lambda kill: kill.tick,
    )
