from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path

APP_ID = "roundlens"
PRODUCT_NAME = "RoundLens"
DEFAULT_TRADE_WINDOW_SECONDS = 5.0
DEFAULT_ENCOUNTER_IDLE_SECONDS = 3.0


@dataclass(frozen=True, slots=True)
class AppPaths:
    root: Path
    database: Path
    parsed: Path
    reports: Path
    cache: Path
    logs: Path
    map_cache: Path
    backups: Path

    @classmethod
    def create(cls, root: Path | None = None) -> AppPaths:
        resolved = (root or user_data_path(PRODUCT_NAME, appauthor=False)).resolve()
        paths = cls(
            root=resolved,
            database=resolved / "database",
            parsed=resolved / "parsed",
            reports=resolved / "reports",
            cache=resolved / "cache",
            logs=resolved / "logs",
            map_cache=resolved / "map-cache",
            backups=resolved / "backups",
        )
        for directory in (
            paths.root,
            paths.database,
            paths.parsed,
            paths.reports,
            paths.cache,
            paths.logs,
            paths.map_cache,
            paths.backups,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return paths
