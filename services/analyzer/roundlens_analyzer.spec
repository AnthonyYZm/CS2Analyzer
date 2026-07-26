# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

service_root = Path(SPECPATH)

datas = []
binaries = []
hiddenimports = []
for package in ("awpy", "demoparser2", "polars", "pyarrow"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += [item for item in package_datas if "tests" not in item[1] and "testing" not in item[1]]
    binaries += package_binaries
    hiddenimports += [
        name for name in package_hidden if ".tests" not in name and ".testing" not in name
    ]

analysis = Analysis(
    [str(service_root / "src/roundlens_analyzer/__main__.py")],
    pathex=[str(service_root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "mypy", "ruff", "hypothesis", "tkinter"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="roundlens-analyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    name="roundlens-analyzer",
)
