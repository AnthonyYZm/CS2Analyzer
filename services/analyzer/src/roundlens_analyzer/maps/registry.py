from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class MapCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    map_name: str
    radar_image: bool = False
    coordinate_transform: bool = False
    area_names: bool = False
    nav_mesh: bool = False
    collision_triangles: bool = False
    visibility: bool = False
    source: str = "unavailable"


class MapResourceRegistry:
    def __init__(self, roots: list[Path]) -> None:
        self.roots = [root.resolve(strict=False) for root in roots]

    def get_capabilities(self, map_name: str) -> MapCapabilities:
        safe_name = "".join(
            character for character in map_name if character.isalnum() or character in {"_", "-"}
        )
        if not safe_name or safe_name != map_name:
            return MapCapabilities(map_name=map_name)
        for root in self.roots:
            manifest = root / safe_name / "capabilities.json"
            if not manifest.is_file():
                continue
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                payload["map_name"] = map_name
                payload["source"] = "local_or_licensed"
                return MapCapabilities.model_validate(payload)
            except (OSError, ValueError):
                continue
        return MapCapabilities(map_name=map_name)

    @staticmethod
    def review_mode(capabilities: MapCapabilities) -> str:
        if capabilities.radar_image and capabilities.coordinate_transform:
            return "radar_snapshot"
        if capabilities.coordinate_transform:
            return "relative_trajectory"
        return "event_timeline"
