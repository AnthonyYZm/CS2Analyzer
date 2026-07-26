from __future__ import annotations

import json
from pathlib import Path

from roundlens_analyzer import PROTOCOL_VERSION, REPORT_SCHEMA_VERSION
from roundlens_analyzer.reports.models import CoachingReport

ROOT = Path(__file__).resolve().parents[2]


def test_report_schema_is_generated_from_strict_model() -> None:
    generated = json.loads(
        (ROOT / "packages/contracts/schemas/report.schema.json").read_text(encoding="utf-8")
    )
    current = CoachingReport.model_json_schema()
    assert generated["properties"] == current["properties"]
    assert generated["$defs"] == current["$defs"]


def test_contract_versions_are_synchronized() -> None:
    versions = (ROOT / "packages/contracts/generated-ts/versions.ts").read_text(encoding="utf-8")
    assert f"IPC_PROTOCOL_VERSION = {PROTOCOL_VERSION}" in versions
    assert f'REPORT_SCHEMA_VERSION = "{REPORT_SCHEMA_VERSION}"' in versions
