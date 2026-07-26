from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CapabilityStatus(StrEnum):
    AVAILABLE = "available"
    ESTIMATED = "estimated"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class DataQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    core_events: CapabilityStatus = CapabilityStatus.UNAVAILABLE
    shots: CapabilityStatus = CapabilityStatus.UNAVAILABLE
    utility: CapabilityStatus = CapabilityStatus.UNAVAILABLE
    positions: CapabilityStatus = CapabilityStatus.UNAVAILABLE
    view_angles: CapabilityStatus = CapabilityStatus.UNAVAILABLE
    velocity: CapabilityStatus = CapabilityStatus.UNAVAILABLE
    usercmd: CapabilityStatus = CapabilityStatus.UNAVAILABLE
    map_radar: CapabilityStatus = CapabilityStatus.UNAVAILABLE
    map_nav: CapabilityStatus = CapabilityStatus.UNAVAILABLE
    visibility: CapabilityStatus = CapabilityStatus.UNAVAILABLE

    def supports(self, *capabilities: str) -> bool:
        accepted = {CapabilityStatus.AVAILABLE, CapabilityStatus.ESTIMATED}
        return all(getattr(self, capability) in accepted for capability in capabilities)


class Player(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steam_id: str
    name: str
    team_name: str | None = None


class Round(BaseModel):
    model_config = ConfigDict(extra="forbid")

    round_id: str
    number: int
    start_tick: int
    end_tick: int
    winner_side: Literal["T", "CT"] | None = None
    t_score_before: int | None = None
    ct_score_before: int | None = None
    freeze_end_tick: int | None = None
    bomb_plant_tick: int | None = None
    end_reason: str | None = None
    t_equipment_value: int | None = None
    ct_equipment_value: int | None = None


class Kill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    round_id: str
    tick: int
    seconds: float | None = None
    attacker_id: str | None = None
    victim_id: str
    attacker_side: Literal["T", "CT"] | None = None
    victim_side: Literal["T", "CT"] | None = None
    assister_id: str | None = None
    weapon: str | None = None
    headshot: bool | None = None
    attacker_xyz: tuple[float, float, float] | None = None
    victim_xyz: tuple[float, float, float] | None = None


class Damage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    round_id: str
    tick: int
    attacker_id: str | None = None
    victim_id: str
    amount: int
    weapon: str | None = None


class Shot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    round_id: str
    tick: int
    player_id: str
    weapon: str | None = None
    speed: float | None = None
    weapon_max_speed: float | None = None
    hit: bool | None = None
    target_id: str | None = None
    visible_enemy_count: int | None = None
    association_status: CapabilityStatus = CapabilityStatus.UNAVAILABLE


class PlayerRoundState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    round_id: str
    player_id: str
    side: Literal["T", "CT"]
    survived: bool | None = None
    utility_value_on_death: int | None = None
    flash_on_death: int | None = None
    smoke_on_death: int | None = None


class ParsedMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parser_name: str
    parser_version: str
    map_name: str
    tick_rate: float | None = None
    played_at: str | None = None
    players: list[Player] = Field(default_factory=list)
    rounds: list[Round] = Field(default_factory=list)
    kills: list[Kill] = Field(default_factory=list)
    damages: list[Damage] = Field(default_factory=list)
    shots: list[Shot] = Field(default_factory=list)
    player_round_states: list[PlayerRoundState] = Field(default_factory=list)
    quality: DataQuality = Field(default_factory=DataQuality)
    warnings: list[str] = Field(default_factory=list)
    dense_frames: dict[str, Any] = Field(default_factory=dict, exclude=True)
