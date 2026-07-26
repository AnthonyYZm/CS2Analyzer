from __future__ import annotations

import re
from pathlib import Path

LIBRARY_PATH = re.compile(r'"path"\s+"([^"]+)"', re.IGNORECASE)


def discover_demo_directories() -> list[str]:
    candidates: list[Path] = []
    steam_roots = _registry_steam_roots()
    for root in steam_roots:
        candidates.extend(_steam_library_roots(root))
    home = Path.home()
    candidates.extend(
        [
            home / "Downloads",
            home / "Documents",
            home / "AppData/Local/FACEIT/videos",
        ]
    )
    results: list[str] = []
    for candidate in candidates:
        resolved = candidate.expanduser().resolve(strict=False)
        if resolved.is_dir() and str(resolved) not in results:
            results.append(str(resolved))
    return results


def _registry_steam_roots() -> list[Path]:
    try:
        import winreg
    except ImportError:
        return []
    values = [
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Valve\Steam", "InstallPath"),
    ]
    roots: list[Path] = []
    for hive, key_path, value_name in values:
        try:
            with winreg.OpenKey(hive, key_path) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
                roots.append(Path(str(value)))
        except OSError:
            continue
    return roots


def _steam_library_roots(steam_root: Path) -> list[Path]:
    roots = [steam_root]
    config = steam_root / "steamapps/libraryfolders.vdf"
    if config.is_file():
        try:
            content = config.read_text(encoding="utf-8", errors="ignore")
            roots.extend(
                Path(match.replace("\\\\", "\\")) for match in LIBRARY_PATH.findall(content)
            )
        except OSError:
            pass
    candidates: list[Path] = []
    for root in roots:
        cs2 = root / "steamapps/common/Counter-Strike Global Offensive/game/csgo"
        candidates.extend([cs2, cs2 / "replays"])
    return candidates
