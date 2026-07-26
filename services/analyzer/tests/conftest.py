from __future__ import annotations

import pytest
from roundlens_analyzer.normalization.models import (
    CapabilityStatus,
    Damage,
    DataQuality,
    Kill,
    ParsedMatch,
    Player,
    PlayerRoundState,
    Round,
    Shot,
)


@pytest.fixture
def parsed_match() -> ParsedMatch:
    rounds = [
        Round(
            round_id=f"r{number}",
            number=number,
            start_tick=(number - 1) * 1000,
            end_tick=number * 1000 - 1,
            winner_side="T" if number != 2 else "CT",
            t_equipment_value=22000,
            ct_equipment_value=9000,
        )
        for number in range(1, 7)
    ]
    kills: list[Kill] = []
    damages: list[Damage] = []
    shots: list[Shot] = []
    for index, round_ in enumerate(rounds):
        base = round_.start_tick + 100
        opening_attacker = "me" if index != 1 else "enemy1"
        opening_victim = "enemy1" if index != 1 else "me"
        attacker_side = "T" if opening_attacker == "me" else "CT"
        victim_side = "CT" if opening_victim == "enemy1" else "T"
        kills.extend(
            [
                Kill(
                    event_id=f"k{index}-1",
                    round_id=round_.round_id,
                    tick=base,
                    attacker_id=opening_attacker,
                    victim_id=opening_victim,
                    attacker_side=attacker_side,
                    victim_side=victim_side,
                    weapon="ak47",
                ),
                Kill(
                    event_id=f"k{index}-2",
                    round_id=round_.round_id,
                    tick=base + 64,
                    attacker_id="enemy2",
                    victim_id="me",
                    attacker_side="CT",
                    victim_side="T",
                    weapon="m4a1",
                ),
                Kill(
                    event_id=f"k{index}-3",
                    round_id=round_.round_id,
                    tick=base + 128,
                    attacker_id="mate",
                    victim_id="enemy2",
                    attacker_side="T",
                    victim_side="CT",
                    weapon="ak47",
                ),
            ]
        )
        damages.extend(
            [
                Damage(
                    event_id=f"d{index}-1",
                    round_id=round_.round_id,
                    tick=base - 10,
                    attacker_id="me",
                    victim_id="enemy1",
                    amount=40,
                ),
                Damage(
                    event_id=f"d{index}-2",
                    round_id=round_.round_id,
                    tick=base,
                    attacker_id="me",
                    victim_id="enemy1",
                    amount=60,
                ),
            ]
        )
        shots.append(
            Shot(
                event_id=f"s{index}",
                round_id=round_.round_id,
                tick=base - 12,
                player_id="me",
                target_id="enemy1",
                weapon="ak47",
                speed=30,
                weapon_max_speed=215,
                hit=index % 2 == 0,
                visible_enemy_count=2 if index % 2 == 0 else 1,
            )
        )
    return ParsedMatch(
        parser_name="fixture",
        parser_version="1",
        map_name="de_fixture",
        tick_rate=64,
        players=[
            Player(steam_id="me", name="Me"),
            Player(steam_id="mate", name="Mate"),
            Player(steam_id="enemy1", name="Enemy 1"),
            Player(steam_id="enemy2", name="Enemy 2"),
        ],
        rounds=rounds,
        kills=kills,
        damages=damages,
        shots=shots,
        player_round_states=[
            PlayerRoundState(
                round_id=round_.round_id,
                player_id="me",
                side="T",
                survived=False,
                utility_value_on_death=300,
            )
            for round_ in rounds
        ],
        quality=DataQuality(
            core_events=CapabilityStatus.AVAILABLE,
            shots=CapabilityStatus.AVAILABLE,
            positions=CapabilityStatus.AVAILABLE,
            velocity=CapabilityStatus.AVAILABLE,
            visibility=CapabilityStatus.ESTIMATED,
        ),
    )
