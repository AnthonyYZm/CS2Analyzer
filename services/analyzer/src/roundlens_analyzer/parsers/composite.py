from __future__ import annotations

import math
from pathlib import Path

from roundlens_analyzer.normalization.awpy import records, text_id
from roundlens_analyzer.normalization.models import CapabilityStatus, ParsedMatch
from roundlens_analyzer.parsers.awpy_adapter import AwpyParserAdapter
from roundlens_analyzer.parsers.base import DemoParseError, ParseCapabilities
from roundlens_analyzer.parsers.demoparser_adapter import DemoparserSupplementAdapter


class CompositeDemoParser:
    name = "awpy+demoparser2"

    def __init__(self) -> None:
        self.primary = AwpyParserAdapter()
        self.supplement = DemoparserSupplementAdapter()

    def probe(self, demo_path: Path) -> ParseCapabilities:
        return self.primary.probe(demo_path)

    def parse_core(self, demo_path: Path) -> ParsedMatch:
        result = self.primary.parse_core(demo_path)
        supplement_probe = self.supplement.probe(demo_path)
        if not supplement_probe.parser_available:
            result.warnings.append("demoparser2 不可用，高级字段仅来自 Awpy")
            return result
        if result.quality.shots is CapabilityStatus.UNAVAILABLE:
            try:
                raw = self.supplement.raw_events(demo_path, "weapon_fire")
                result.dense_frames["weapon_fire_supplement"] = raw
                if raw is not None and len(raw) > 0:
                    result.quality.shots = CapabilityStatus.PARTIAL
            except (DemoParseError, TypeError) as exc:
                result.warnings.append(str(exc))
        if result.quality.velocity is CapabilityStatus.UNAVAILABLE:
            try:
                ticks = self.supplement.raw_ticks(
                    demo_path, ["X", "Y", "Z", "velocity_X", "velocity_Y", "pitch", "yaw"]
                )
                result.dense_frames["ticks_supplement"] = ticks
                if ticks is not None and len(ticks) > 0:
                    result.quality.positions = CapabilityStatus.AVAILABLE
                    result.quality.velocity = CapabilityStatus.AVAILABLE
                    self._attach_shot_velocity(result, ticks)
            except (DemoParseError, TypeError) as exc:
                result.warnings.append(str(exc))
        self._associate_shots(result)
        return result

    def parse_events(self, demo_path: Path) -> ParsedMatch:
        return self.parse_core(demo_path)

    def parse_ticks(self, demo_path: Path, fields: list[str]) -> ParsedMatch:
        del fields
        return self.parse_core(demo_path)

    @staticmethod
    def _associate_shots(result: ParsedMatch) -> None:
        tick_window = int((result.tick_rate or 64) * 3)
        for shot in result.shots:
            if shot.target_id is not None:
                continue
            future_damage = [
                damage
                for damage in result.damages
                if damage.round_id == shot.round_id
                and damage.attacker_id == shot.player_id
                and shot.tick <= damage.tick <= shot.tick + tick_window
            ]
            future_death = [
                kill
                for kill in result.kills
                if kill.round_id == shot.round_id
                and kill.victim_id == shot.player_id
                and shot.tick <= kill.tick <= shot.tick + tick_window
                and kill.attacker_id
            ]
            if future_damage:
                damage = min(future_damage, key=lambda item: item.tick)
                shot.target_id = damage.victim_id
                shot.hit = damage.tick - shot.tick <= max(8, int((result.tick_rate or 64) * 0.15))
                shot.association_status = CapabilityStatus.ESTIMATED
            elif future_death:
                death = min(future_death, key=lambda item: item.tick)
                shot.target_id = death.attacker_id
                shot.hit = False
                shot.association_status = CapabilityStatus.ESTIMATED

    @staticmethod
    def _attach_shot_velocity(result: ParsedMatch, ticks: object) -> None:
        by_player_tick: dict[tuple[str, int], float] = {}
        for row in records(ticks):
            player_id = text_id(
                row.get("steamid") or row.get("player_steamid") or row.get("user_steamid")
            )
            tick = row.get("tick")
            if player_id is None or tick is None:
                continue
            velocity_x = row.get("velocity_X", row.get("velocity_x"))
            velocity_y = row.get("velocity_Y", row.get("velocity_y"))
            if velocity_x is None or velocity_y is None:
                continue
            by_player_tick[(player_id, int(tick))] = math.hypot(
                float(velocity_x), float(velocity_y)
            )
        for shot in result.shots:
            shot.speed = by_player_tick.get((shot.player_id, shot.tick), shot.speed)
            if shot.weapon_max_speed is None:
                shot.weapon_max_speed = weapon_max_speed(shot.weapon)


def weapon_max_speed(weapon: str | None) -> float | None:
    normalized = (weapon or "").lower().replace("weapon_", "")
    speeds = {
        "ak47": 215.0,
        "m4a1": 225.0,
        "m4a1_silencer": 225.0,
        "famas": 220.0,
        "galilar": 215.0,
        "aug": 220.0,
        "sg556": 210.0,
        "awp": 200.0,
        "ssg08": 230.0,
    }
    return speeds.get(normalized)
