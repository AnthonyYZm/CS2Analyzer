from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict
from roundlens_analyzer.normalization.models import ParsedMatch


class ParseCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parser_available: bool
    core: bool = False
    events: bool = False
    ticks: bool = False
    reason: str | None = None


class DemoParserAdapter(Protocol):
    name: str

    def probe(self, demo_path: Path) -> ParseCapabilities: ...

    def parse_core(self, demo_path: Path) -> ParsedMatch: ...

    def parse_events(self, demo_path: Path) -> ParsedMatch: ...

    def parse_ticks(self, demo_path: Path, fields: list[str]) -> ParsedMatch: ...


class DemoParseError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
