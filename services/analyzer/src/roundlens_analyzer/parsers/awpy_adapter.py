from __future__ import annotations

import contextlib
import importlib.metadata
import inspect
import sys
from pathlib import Path
from typing import Any

from roundlens_analyzer.normalization.awpy import normalize_awpy
from roundlens_analyzer.normalization.models import ParsedMatch
from roundlens_analyzer.parsers.base import DemoParseError, ParseCapabilities


class AwpyParserAdapter:
    name = "awpy"

    def probe(self, demo_path: Path) -> ParseCapabilities:
        if not demo_path.is_file():
            return ParseCapabilities(parser_available=True, reason="Demo file is missing")
        try:
            importlib.metadata.version("awpy")
        except importlib.metadata.PackageNotFoundError:
            return ParseCapabilities(parser_available=False, reason="Awpy is not installed")
        return ParseCapabilities(parser_available=True, core=True, events=True, ticks=True)

    def parse_core(self, demo_path: Path) -> ParsedMatch:
        try:
            with contextlib.redirect_stdout(sys.stderr):
                from awpy import Demo  # type: ignore[import-untyped]

                parameters = inspect.signature(Demo).parameters
                kwargs: dict[str, Any] = {}
                if "verbose" in parameters:
                    kwargs["verbose"] = False
                demo = Demo(demo_path, **kwargs)
                parsed = demo.parse()
                source = parsed if parsed is not None and hasattr(parsed, "rounds") else demo
            version = importlib.metadata.version("awpy")
            return normalize_awpy(source, version)
        except Exception as exc:
            raise DemoParseError("PARSER_CORE_FAILED", f"Awpy 解析失败：{exc}") from exc

    def parse_events(self, demo_path: Path) -> ParsedMatch:
        return self.parse_core(demo_path)

    def parse_ticks(self, demo_path: Path, fields: list[str]) -> ParsedMatch:
        del fields
        return self.parse_core(demo_path)
