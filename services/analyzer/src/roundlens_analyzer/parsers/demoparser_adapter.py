from __future__ import annotations

import contextlib
import importlib.metadata
import sys
from pathlib import Path
from typing import Any

from roundlens_analyzer.normalization.models import ParsedMatch
from roundlens_analyzer.parsers.base import DemoParseError, ParseCapabilities


class DemoparserSupplementAdapter:
    name = "demoparser2"

    def probe(self, demo_path: Path) -> ParseCapabilities:
        if not demo_path.is_file():
            return ParseCapabilities(parser_available=True, reason="Demo file is missing")
        try:
            importlib.metadata.version("demoparser2")
        except importlib.metadata.PackageNotFoundError:
            return ParseCapabilities(parser_available=False, reason="demoparser2 is not installed")
        return ParseCapabilities(parser_available=True, core=False, events=True, ticks=True)

    def parse_core(self, demo_path: Path) -> ParsedMatch:
        raise DemoParseError("PARSER_CORE_FAILED", "demoparser2 只作为字段补充，不是核心解析器")

    def raw_events(self, demo_path: Path, event_name: str) -> Any:
        try:
            with contextlib.redirect_stdout(sys.stderr):
                from demoparser2 import DemoParser

                parser = DemoParser(str(demo_path))
                return parser.parse_event(event_name)
        except Exception as exc:
            raise DemoParseError("PARSER_EVENTS_PARTIAL", f"补充事件解析失败：{exc}") from exc

    def raw_ticks(self, demo_path: Path, fields: list[str]) -> Any:
        try:
            with contextlib.redirect_stdout(sys.stderr):
                from demoparser2 import DemoParser

                parser = DemoParser(str(demo_path))
                return parser.parse_ticks(fields)
        except Exception as exc:
            raise DemoParseError("PARSER_TICKS_PARTIAL", f"补充 Tick 解析失败：{exc}") from exc

    def parse_events(self, demo_path: Path) -> ParsedMatch:
        raise DemoParseError("PARSER_EVENTS_PARTIAL", "补充解析结果需要与 Awpy 结果合并")

    def parse_ticks(self, demo_path: Path, fields: list[str]) -> ParsedMatch:
        del fields
        raise DemoParseError("PARSER_TICKS_PARTIAL", "补充解析结果需要与 Awpy 结果合并")
