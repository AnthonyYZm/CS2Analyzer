from __future__ import annotations

from pathlib import Path

from roundlens_analyzer.imports.steam import _steam_library_roots
from roundlens_analyzer.maps.registry import MapResourceRegistry


def test_steam_libraryfolders_are_discovered(tmp_path: Path) -> None:
    root = tmp_path / "Steam"
    library = tmp_path / "Library"
    config = root / "steamapps/libraryfolders.vdf"
    config.parent.mkdir(parents=True)
    config.write_text(f'"path" "{library}"', encoding="utf-8")
    roots = _steam_library_roots(root)
    assert any(str(library) in str(candidate) for candidate in roots)


def test_missing_map_resource_degrades_to_timeline(tmp_path: Path) -> None:
    registry = MapResourceRegistry([tmp_path])
    capabilities = registry.get_capabilities("de_unknown")
    assert capabilities.radar_image is False
    assert registry.review_mode(capabilities) == "event_timeline"
