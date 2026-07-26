from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5

from roundlens_analyzer.normalization.models import (
    CapabilityStatus,
    Damage,
    DataQuality,
    Kill,
    ParsedMatch,
    Player,
    Round,
    Shot,
)


def records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dicts"):
        return list(value.to_dicts())
    if hasattr(value, "to_dict"):
        try:
            result = value.to_dict(orient="records")
        except TypeError:
            result = value.to_dicts() if hasattr(value, "to_dicts") else value.to_dict()
        if isinstance(result, list):
            return [dict(item) for item in result]
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    if isinstance(value, Mapping):
        keys = list(value)
        if keys and all(
            isinstance(value[key], Iterable) and not isinstance(value[key], str) for key in keys
        ):
            columns = {key: list(value[key]) for key in keys}
            length = min((len(column) for column in columns.values()), default=0)
            return [{key: columns[key][index] for key in keys} for index in range(length)]
    return []


def pick(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row and row[name] is not None:
            value = row[name]
            if isinstance(value, float) and math.isnan(value):
                continue
            return value
    return default


def text_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    rendered = str(value).strip()
    if rendered.endswith(".0") and rendered[:-2].isdigit():
        rendered = rendered[:-2]
    return rendered or None


def side(value: Any) -> Literal["T", "CT"] | None:
    rendered = str(value or "").upper()
    if rendered in {"T", "TERRORIST", "TERRORISTS"}:
        return "T"
    if rendered in {"CT", "COUNTERTERRORIST", "COUNTER-TERRORIST", "COUNTERTERRORISTS"}:
        return "CT"
    return None


def xyz(row: Mapping[str, Any], prefix: str) -> tuple[float, float, float] | None:
    values = [pick(row, f"{prefix}_{axis}", f"{prefix}{axis.upper()}") for axis in ("x", "y", "z")]
    if any(value is None for value in values):
        return None
    return (float(values[0]), float(values[1]), float(values[2]))


def event_id(kind: str, row: Mapping[str, Any], index: int) -> str:
    stable = f"{kind}:{pick(row, 'tick', 'event_tick', default=0)}:{index}:{sorted(row)}"
    return str(uuid5(NAMESPACE_URL, stable))


def normalize_awpy(demo: Any, parser_version: str) -> ParsedMatch:
    header = getattr(demo, "header", {}) or {}
    header_row = header if isinstance(header, Mapping) else {}
    round_rows = records(getattr(demo, "rounds", None))
    kill_rows = records(getattr(demo, "kills", None))
    damage_rows = records(getattr(demo, "damages", None))
    shot_rows = records(getattr(demo, "shots", None))
    tick_frame = getattr(demo, "ticks", None)
    grenade_frame = getattr(demo, "grenades", None)
    bomb_frame = getattr(demo, "bomb", None)

    rounds: list[Round] = []
    round_by_number: dict[int, Round] = {}
    for index, row in enumerate(round_rows):
        number = int(pick(row, "round_num", "round_number", "round", default=index + 1))
        start = int(pick(row, "start", "start_tick", "startTick", default=0))
        end = int(pick(row, "end", "end_tick", "endTick", "official_end", default=start))
        normalized = Round(
            round_id=f"r{number}",
            number=number,
            start_tick=start,
            end_tick=end,
            freeze_end_tick=_optional_int(
                pick(row, "freeze_end", "freeze_end_tick", "freezeTimeEndTick")
            ),
            winner_side=side(pick(row, "winner", "winner_side", "winning_side")),
            t_score_before=_optional_int(pick(row, "t_score", "t_score_before")),
            ct_score_before=_optional_int(pick(row, "ct_score", "ct_score_before")),
            bomb_plant_tick=_optional_int(pick(row, "bomb_plant", "bomb_plant_tick")),
            end_reason=_optional_str(pick(row, "reason", "end_reason")),
            t_equipment_value=_optional_int(pick(row, "t_equipment_value", "t_eq_val")),
            ct_equipment_value=_optional_int(pick(row, "ct_equipment_value", "ct_eq_val")),
        )
        rounds.append(normalized)
        round_by_number[number] = normalized

    def round_id_for(row: Mapping[str, Any], tick: int) -> str:
        raw_number = pick(row, "round_num", "round_number", "round")
        if raw_number is not None and int(raw_number) in round_by_number:
            return round_by_number[int(raw_number)].round_id
        for candidate in rounds:
            if candidate.start_tick <= tick <= candidate.end_tick:
                return candidate.round_id
        return f"r{int(raw_number) if raw_number is not None else 0}"

    kills: list[Kill] = []
    players: dict[str, Player] = {}
    for index, row in enumerate(kill_rows):
        tick = int(pick(row, "tick", "event_tick", default=0))
        attacker = text_id(pick(row, "attacker_steamid", "attacker_steam_id", "attackerSteamID"))
        victim = text_id(pick(row, "victim_steamid", "victim_steam_id", "victimSteamID"))
        if victim is None:
            continue
        attacker_side = side(pick(row, "attacker_side", "attackerSide", "attacker_team_name"))
        victim_side = side(pick(row, "victim_side", "victimSide", "victim_team_name"))
        if attacker:
            players.setdefault(
                attacker,
                Player(
                    steam_id=attacker,
                    name=str(pick(row, "attacker_name", "attackerName", default=attacker)),
                    team_name=_optional_str(pick(row, "attacker_team_name", "attackerTeam")),
                ),
            )
        players.setdefault(
            victim,
            Player(
                steam_id=victim,
                name=str(pick(row, "victim_name", "victimName", default=victim)),
                team_name=_optional_str(pick(row, "victim_team_name", "victimTeam")),
            ),
        )
        kills.append(
            Kill(
                event_id=event_id("kill", row, index),
                round_id=round_id_for(row, tick),
                tick=tick,
                seconds=_optional_float(pick(row, "seconds", "clock")),
                attacker_id=attacker,
                victim_id=victim,
                attacker_side=attacker_side,
                victim_side=victim_side,
                assister_id=text_id(pick(row, "assister_steamid", "assister_steam_id")),
                weapon=_optional_str(pick(row, "weapon", "weapon_name")),
                headshot=_optional_bool(pick(row, "headshot", "is_headshot")),
                attacker_xyz=xyz(row, "attacker"),
                victim_xyz=xyz(row, "victim"),
            )
        )

    damages: list[Damage] = []
    for index, row in enumerate(damage_rows):
        victim = text_id(pick(row, "victim_steamid", "victim_steam_id", "victimSteamID"))
        if victim is None:
            continue
        tick = int(pick(row, "tick", "event_tick", default=0))
        damages.append(
            Damage(
                event_id=event_id("damage", row, index),
                round_id=round_id_for(row, tick),
                tick=tick,
                attacker_id=text_id(
                    pick(row, "attacker_steamid", "attacker_steam_id", "attackerSteamID")
                ),
                victim_id=victim,
                amount=int(pick(row, "dmg_health", "damage", "health_damage", default=0)),
                weapon=_optional_str(pick(row, "weapon", "weapon_name")),
            )
        )

    shots: list[Shot] = []
    for index, row in enumerate(shot_rows):
        player = text_id(pick(row, "steamid", "player_steamid", "user_steamid"))
        if player is None:
            continue
        tick = int(pick(row, "tick", "event_tick", default=0))
        shots.append(
            Shot(
                event_id=event_id("shot", row, index),
                round_id=round_id_for(row, tick),
                tick=tick,
                player_id=player,
                weapon=_optional_str(pick(row, "weapon", "weapon_name")),
                speed=_optional_float(pick(row, "velocity", "speed", "horizontal_speed")),
                weapon_max_speed=_optional_float(pick(row, "weapon_max_speed", "max_speed")),
                hit=_optional_bool(pick(row, "hit", "is_hit")),
                target_id=text_id(pick(row, "target_steamid", "victim_steamid")),
                visible_enemy_count=_optional_int(pick(row, "visible_enemy_count")),
                association_status=(
                    CapabilityStatus.AVAILABLE
                    if pick(row, "target_steamid", "victim_steamid") is not None
                    else CapabilityStatus.UNAVAILABLE
                ),
            )
        )

    map_name = str(pick(header_row, "map_name", "map", "mapName", default="unknown"))
    tick_rate = _optional_float(pick(header_row, "tick_rate", "tickrate", "tickRate"))
    quality = DataQuality(
        core_events=CapabilityStatus.AVAILABLE if rounds and kills else CapabilityStatus.PARTIAL,
        shots=CapabilityStatus.AVAILABLE if shots else CapabilityStatus.UNAVAILABLE,
        utility=CapabilityStatus.AVAILABLE
        if records(grenade_frame)
        else CapabilityStatus.UNAVAILABLE,
        positions=CapabilityStatus.AVAILABLE
        if tick_frame is not None
        else CapabilityStatus.UNAVAILABLE,
        view_angles=(
            CapabilityStatus.AVAILABLE
            if _frame_has_columns(tick_frame, {"pitch", "yaw"})
            else CapabilityStatus.UNAVAILABLE
        ),
        velocity=(
            CapabilityStatus.AVAILABLE
            if _frame_has_any_column(tick_frame, {"velocity", "vel_x", "velocity_X"})
            else CapabilityStatus.UNAVAILABLE
        ),
        visibility=CapabilityStatus.ESTIMATED
        if tick_frame is not None
        else CapabilityStatus.UNAVAILABLE,
    )
    return ParsedMatch(
        parser_name="awpy",
        parser_version=parser_version,
        map_name=map_name,
        tick_rate=tick_rate,
        players=list(players.values()),
        rounds=rounds,
        kills=kills,
        damages=damages,
        shots=shots,
        quality=quality,
        dense_frames={
            key: value
            for key, value in {
                "ticks": tick_frame,
                "grenades": grenade_frame,
                "bomb": bomb_frame,
            }.items()
            if value is not None
        },
    )


def _columns(frame: Any) -> set[str]:
    if frame is None:
        return set()
    columns = getattr(frame, "columns", [])
    return {str(column) for column in columns}


def _frame_has_columns(frame: Any, required: set[str]) -> bool:
    return required.issubset(_columns(frame))


def _frame_has_any_column(frame: Any, candidates: set[str]) -> bool:
    return bool(_columns(frame).intersection(candidates))


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_bool(value: Any) -> bool | None:
    return None if value is None else bool(value)
