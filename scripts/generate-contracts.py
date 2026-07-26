from __future__ import annotations

import json
from pathlib import Path

from roundlens_analyzer.ipc.models import RpcError, RpcRequest
from roundlens_analyzer.reports.models import CoachingReport

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "packages/contracts/schemas"
GENERATED_TS = ROOT / "packages/contracts/generated-ts"
GENERATED_PY = ROOT / "packages/contracts/generated-python"


def main() -> None:
    for directory in (SCHEMAS, GENERATED_TS, GENERATED_PY):
        directory.mkdir(parents=True, exist_ok=True)
    report_schema = CoachingReport.model_json_schema()
    report_schema["$id"] = "https://roundlens.app/schemas/report-1.0.0.json"
    ipc_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://roundlens.app/schemas/ipc-1.json",
        "oneOf": [RpcRequest.model_json_schema(), RpcError.model_json_schema()],
    }
    (SCHEMAS / "report.schema.json").write_text(
        json.dumps(report_schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (SCHEMAS / "ipc.schema.json").write_text(
        json.dumps(ipc_schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (GENERATED_TS / "versions.ts").write_text(
        "export const IPC_PROTOCOL_VERSION = 1 as const;\n"
        'export const REPORT_SCHEMA_VERSION = "1.0.0" as const;\n',
        encoding="utf-8",
    )
    (GENERATED_PY / "versions.py").write_text(
        'IPC_PROTOCOL_VERSION = 1\nREPORT_SCHEMA_VERSION = "1.0.0"\n', encoding="utf-8"
    )


if __name__ == "__main__":
    main()
