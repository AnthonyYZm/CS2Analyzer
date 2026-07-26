from __future__ import annotations

from collections import defaultdict
from typing import Literal, cast
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict
from roundlens_analyzer.normalization.models import ParsedMatch


class Encounter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    encounter_id: str
    round_id: str
    player_id: str
    enemy_id: str
    start_tick: int
    end_tick: int
    start_reason: Literal["damage", "shot", "kill"]
    weapon: str | None = None
    first_shot_tick: int | None = None
    first_damage_tick: int | None = None
    first_damage_side: Literal["player", "enemy"] | None = None
    outcome: Literal["won", "lost", "disengaged"]
    data_confidence: float
    event_refs: list[str]


class EncounterDetector:
    def __init__(self, idle_seconds: float = 3.0) -> None:
        self.idle_seconds = idle_seconds

    def detect(self, match: ParsedMatch, player_id: str) -> list[Encounter]:
        tick_rate = match.tick_rate or 64.0
        idle_ticks = int(self.idle_seconds * tick_rate)
        raw: dict[tuple[str, str], list[tuple[int, str, str, str | None]]] = defaultdict(list)

        for damage in match.damages:
            enemy: str | None = None
            first_side: str | None = None
            if damage.attacker_id == player_id:
                enemy, first_side = damage.victim_id, "player"
            elif damage.victim_id == player_id and damage.attacker_id:
                enemy, first_side = damage.attacker_id, "enemy"
            if enemy:
                raw[(damage.round_id, enemy)].append(
                    (damage.tick, "damage", damage.event_id, first_side)
                )
        for shot in match.shots:
            if shot.player_id == player_id and shot.target_id:
                raw[(shot.round_id, shot.target_id)].append(
                    (shot.tick, "shot", shot.event_id, shot.weapon)
                )
        for kill in match.kills:
            enemy = None
            outcome = None
            if kill.attacker_id == player_id:
                enemy, outcome = kill.victim_id, "won"
            elif kill.victim_id == player_id and kill.attacker_id:
                enemy, outcome = kill.attacker_id, "lost"
            if enemy:
                raw[(kill.round_id, enemy)].append((kill.tick, "kill", kill.event_id, outcome))

        encounters: list[Encounter] = []
        for (round_id, enemy_id), events in raw.items():
            events.sort(key=lambda item: item[0])
            groups: list[list[tuple[int, str, str, str | None]]] = []
            for event in events:
                if not groups or event[0] - groups[-1][-1][0] > idle_ticks:
                    groups.append([event])
                else:
                    groups[-1].append(event)
            for group_index, group in enumerate(groups):
                first = group[0]
                shot_events = [event for event in group if event[1] == "shot"]
                damage_events = [event for event in group if event[1] == "damage"]
                kill_events = [event for event in group if event[1] == "kill"]
                outcome_value = kill_events[-1][3] if kill_events else "disengaged"
                first_damage_side = damage_events[0][3] if damage_events else None
                identifier = str(
                    uuid5(
                        NAMESPACE_URL,
                        f"{round_id}:{player_id}:{enemy_id}:{group_index}:{first[0]}",
                    )
                )
                encounters.append(
                    Encounter(
                        encounter_id=identifier,
                        round_id=round_id,
                        player_id=player_id,
                        enemy_id=enemy_id,
                        start_tick=first[0],
                        end_tick=group[-1][0],
                        start_reason=cast(Literal["damage", "shot", "kill"], first[1]),
                        weapon=next((event[3] for event in shot_events if event[3]), None),
                        first_shot_tick=shot_events[0][0] if shot_events else None,
                        first_damage_tick=damage_events[0][0] if damage_events else None,
                        first_damage_side=cast(
                            Literal["player", "enemy"] | None, first_damage_side
                        ),
                        outcome=cast(Literal["won", "lost", "disengaged"], outcome_value),
                        data_confidence=0.8 if damage_events else 0.55,
                        event_refs=[event[2] for event in group],
                    )
                )
        return sorted(encounters, key=lambda item: (item.round_id, item.start_tick))
