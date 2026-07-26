from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

from roundlens_analyzer.app.config import AppPaths
from roundlens_analyzer.app.service import AnalyzerApplication
from roundlens_analyzer.imports.service import DemoImportService, stream_sha256
from roundlens_analyzer.ipc.server import JsonlServer
from roundlens_analyzer.normalization.models import ParsedMatch
from roundlens_analyzer.storage.database import Database
from roundlens_analyzer.storage.models import DemoFile, Match


def test_stream_hash_reports_progress(tmp_path: Path) -> None:
    demo = tmp_path / "fixture.dem"
    demo.write_bytes(b"HL2DEMO" + b"x" * 1024)
    progress: list[int] = []
    digest = stream_sha256(demo, progress.append, chunk_size=128)
    assert len(digest) == 64
    assert progress[-1] == 100


def test_import_deduplicates_by_hash_and_relinks(tmp_path: Path) -> None:
    database = Database(AppPaths.create(tmp_path / "data"))
    service = DemoImportService(database)
    first = tmp_path / "first.dem"
    second = tmp_path / "second.dem"
    first.write_bytes(b"HL2DEMO-fixture")
    second.write_bytes(first.read_bytes())
    imported = service.import_paths([str(first)])[0]
    duplicate = service.import_paths([str(second)])[0]
    assert imported["status"] == "imported"
    assert duplicate["status"] == "duplicate"
    first.unlink()
    result = service.relink(str(imported["demo_id"]), str(second))
    assert result["exists"] is True
    database.close()


def test_database_interrupts_running_jobs(tmp_path: Path) -> None:
    from roundlens_analyzer.storage.models import ParseJob

    paths = AppPaths.create(tmp_path / "data")
    database = Database(paths)
    with database.session() as session:
        session.add(ParseJob(id="job", type="parse_demo", status="running"))
    database.close()
    reopened = Database(paths)
    with reopened.session() as session:
        assert session.get(ParseJob, "job").status == "interrupted"
    reopened.close()


def test_jsonl_health_and_invalid_method(tmp_path: Path) -> None:
    output = io.StringIO()
    server = JsonlServer(tmp_path / "data", input_stream=io.StringIO(), output_stream=output)
    server.handle_line(
        json.dumps({"protocol_version": 1, "id": "1", "method": "health", "params": {}})
    )
    server.handle_line(
        json.dumps({"protocol_version": 1, "id": "2", "method": "not_allowed", "params": {}})
    )
    lines = [json.loads(line) for line in output.getvalue().splitlines()]
    assert lines[0]["result"]["status"] == "ok"
    assert lines[1]["error"]["code"] == "METHOD_NOT_FOUND"
    server.executor.shutdown()
    server.app.close()


def test_jsonl_wire_remains_utf8_safe_with_gbk_stream(tmp_path: Path) -> None:
    raw_output = io.BytesIO()
    output = io.TextIOWrapper(raw_output, encoding="gbk", write_through=True)
    server = JsonlServer(tmp_path / "data", input_stream=io.StringIO(), output_stream=output)

    server.write({"protocol_version": 1, "event": "job.progress", "data": {"message": "正在解析"}})

    wire = raw_output.getvalue().decode("utf-8")
    assert json.loads(wire)["data"]["message"] == "正在解析"
    server.executor.shutdown()
    server.app.close()


def test_deterministic_analysis_persists_and_reloads(
    tmp_path: Path, parsed_match: ParsedMatch
) -> None:
    app = AnalyzerApplication(AppPaths.create(tmp_path / "data"), lambda *_: None)
    with app.database.session() as session:
        session.add(
            DemoFile(
                id="demo-1",
                original_path=str(tmp_path / "fixture.dem"),
                normalized_path=str(tmp_path / "fixture.dem"),
                filename="fixture.dem",
                size_bytes=8,
                modified_at=datetime.now(),
                sha256="a" * 64,
            )
        )
        session.add(
            Match(
                id="match-1",
                demo_id="demo-1",
                map_name=parsed_match.map_name,
                tick_rate=parsed_match.tick_rate,
                parser_name=parsed_match.parser_name,
                parser_version=parsed_match.parser_version,
                quality=parsed_match.quality.model_dump(mode="json"),
                normalized_data=parsed_match.model_dump(mode="json"),
            )
        )

    settings = app.update_profile(
        {
            "player_identifier": "Me",
            "scan_directories": [],
            "onboarding_complete": True,
            "locale": "zh-CN",
        }
    )
    assert settings["player_identifier"] == "Me"
    summary = app.list_matches()["items"][0]
    assert summary["player_match_status"] == "matched"
    assert summary["kills"] is not None

    created = app.create_analysis({"match_ids": ["match-1"]})
    loaded = app.get_analysis(created["analysis_id"])
    listed = app.list_analyses()["items"]

    assert loaded["status"] == "completed"
    assert loaded["report"]["schema_version"] == "1.0.0"
    assert loaded["report"]["report_summary"]["matches_analyzed"] == 1
    assert listed[0]["analysis_id"] == created["analysis_id"]
    assert listed[0]["report_kind"] == "local"
    assert listed[0]["report_available"] is True

    app.update_profile(
        {
            "player_identifier": "not-in-this-demo",
            "scan_directories": [],
            "onboarding_complete": True,
            "locale": "zh-CN",
        }
    )
    unmatched = app.list_matches()["items"][0]
    assert unmatched["player_match_status"] == "unavailable"
    assert unmatched["kills"] is None
    app.close()
