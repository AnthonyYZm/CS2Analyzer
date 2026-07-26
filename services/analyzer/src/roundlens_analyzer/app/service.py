from __future__ import annotations

import json
import shutil
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Any
from uuid import uuid4

from roundlens_analyzer.app.config import AppPaths
from roundlens_analyzer.imports.service import DemoImportService, ImportErrorWithCode
from roundlens_analyzer.imports.steam import discover_demo_directories
from roundlens_analyzer.issues.detector import IssueDetector
from roundlens_analyzer.llm.provider import OpenAICompatibleProvider, ProviderSettings
from roundlens_analyzer.metrics.core import calculate_all
from roundlens_analyzer.metrics.models import MetricContext, MetricResult, MetricStatus
from roundlens_analyzer.normalization.models import ParsedMatch
from roundlens_analyzer.parsers.base import DemoParseError
from roundlens_analyzer.parsers.composite import CompositeDemoParser
from roundlens_analyzer.reports.builder import build_deterministic_report
from roundlens_analyzer.review.selector import ReviewRoundSelector
from roundlens_analyzer.storage.database import Database
from roundlens_analyzer.storage.models import (
    Analysis,
    AppSetting,
    DemoFile,
    Match,
    MetricValue,
    ParseJob,
    PlayerProfile,
)
from roundlens_analyzer.strengths.detector import StrengthDetector
from sqlalchemy import delete, select

EventCallback = Callable[[str, dict[str, Any]], None]


class ApplicationError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class AnalyzerApplication:
    def __init__(self, paths: AppPaths, emit: EventCallback) -> None:
        self.paths = paths
        self.database = Database(paths)
        self.imports = DemoImportService(self.database)
        self.parser = CompositeDemoParser()
        self.emit = emit
        self.cancel_events: dict[str, Event] = {}

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "protocol_version": 1,
            "database": str(self.database.db_path),
            "parser": self.parser.name,
        }

    def get_settings(self) -> dict[str, Any]:
        with self.database.session() as session:
            profile = session.get(PlayerProfile, 1)
            assert profile is not None
            return {
                "product_name": "RoundLens",
                "player_identifier": profile.steam_id,
                "locale": profile.locale,
                "onboarding_complete": profile.onboarding_complete,
                "scan_directories": profile.scan_directories,
                "data_dir": str(self.paths.root),
                "provider": self._provider_settings(session),
            }

    @staticmethod
    def _provider_settings(session: Any) -> dict[str, Any] | None:
        row = session.get(AppSetting, "provider")
        return row.value if row else None

    def update_provider(self, params: dict[str, Any]) -> dict[str, Any]:
        safe_params = {key: value for key, value in params.items() if key != "api_key"}
        settings = ProviderSettings.model_validate(safe_params)
        value = settings.model_dump(mode="json")
        with self.database.session() as session:
            row = session.get(AppSetting, "provider")
            if row:
                row.value = value
            else:
                session.add(AppSetting(key="provider", value=value))
        return {"provider": value}

    def test_provider(self, params: dict[str, Any]) -> dict[str, Any]:
        api_key = params.pop("api_key", None)
        if not isinstance(api_key, str) or not api_key:
            raise ApplicationError("LLM_NOT_CONFIGURED", "尚未配置 API Key")
        settings_data = params or self.get_settings().get("provider")
        if not settings_data:
            raise ApplicationError("LLM_NOT_CONFIGURED", "尚未配置 API 服务")
        return OpenAICompatibleProvider(
            ProviderSettings.model_validate(settings_data), api_key
        ).test_connection()

    def update_profile(self, params: dict[str, Any]) -> dict[str, Any]:
        raw_identifier = params.get("player_identifier", params.get("steam_id"))
        player_identifier = str(raw_identifier).strip() if raw_identifier is not None else ""
        if (
            not player_identifier
            or len(player_identifier) > 64
            or any(ord(character) < 32 for character in player_identifier)
        ):
            raise ApplicationError(
                "INVALID_PLAYER_IDENTIFIER",
                "玩家 ID/名称必须为 1–64 个可见字符",
            )
        locale = params.get("locale", "zh-CN")
        if locale not in {"zh-CN", "en-US"}:
            raise ApplicationError("INVALID_LOCALE", "不支持的界面语言")
        directories = params.get("scan_directories", [])
        if not isinstance(directories, list):
            raise ApplicationError("INVALID_PARAMS", "扫描目录必须是数组")
        with self.database.session() as session:
            profile = session.get(PlayerProfile, 1)
            assert profile is not None
            profile.steam_id = player_identifier
            profile.locale = locale
            profile.scan_directories = [str(Path(item).expanduser()) for item in directories]
            profile.onboarding_complete = bool(params.get("onboarding_complete", True))
        return self.get_settings()

    def import_demos(self, params: dict[str, Any]) -> dict[str, Any]:
        paths = params.get("paths")
        if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
            raise ApplicationError("INVALID_PARAMS", "paths 必须是文件路径数组")

        def progress(filename: str, percent: int) -> None:
            self.emit(
                "import.progress",
                {"filename": filename, "stage": "hashing", "progress": percent},
            )

        return {
            "items": self.imports.import_paths(
                paths, source_type=str(params.get("source_type", "manual")), progress=progress
            )
        }

    def scan_demos(self, params: dict[str, Any]) -> dict[str, Any]:
        directories = params.get("directories")
        if directories is None:
            directories = [
                *self.get_settings()["scan_directories"],
                *discover_demo_directories(),
            ]
        if not isinstance(directories, list) or not all(
            isinstance(item, str) for item in directories
        ):
            raise ApplicationError("INVALID_PARAMS", "directories 必须是路径数组")
        return {"items": self.imports.scan_directories(directories)}

    def list_demos(self) -> dict[str, Any]:
        return {"items": self.imports.list_demos()}

    def create_parse_job(self, demo_id: str) -> str:
        with self.database.session() as session:
            demo = session.get(DemoFile, demo_id)
            if demo is None:
                raise ApplicationError("DEMO_NOT_FOUND", "未找到导入的 Demo")
            if not Path(demo.normalized_path).exists():
                demo.exists = False
                demo.status = "missing"
                raise ApplicationError("DEMO_NOT_FOUND", "原始 Demo 文件不存在")
            job_id = str(uuid4())
            session.add(
                ParseJob(
                    id=job_id,
                    type="parse_demo",
                    status="queued",
                    stage="queued",
                    payload={"demo_id": demo_id},
                )
            )
            demo.status = "queued"
            demo.error_code = None
            demo.error_message = None
        self.cancel_events[job_id] = Event()
        return job_id

    def run_parse_job(self, job_id: str) -> None:
        cancel = self.cancel_events[job_id]
        try:
            demo_id = self._start_job(job_id, "validating_file", 2)
            demo_path = self._get_demo_path(demo_id)
            self._check_cancel(job_id, cancel)
            self._progress(job_id, "probing_capabilities", 8, "正在探测解析能力")
            capabilities = self.parser.probe(demo_path)
            if not capabilities.parser_available or not capabilities.core:
                raise ApplicationError("DEMO_UNSUPPORTED", capabilities.reason or "解析器不可用")
            self._check_cancel(job_id, cancel)
            self._progress(job_id, "parsing_core", 20, "正在解析核心回合与事件")
            parsed = self.parser.parse_core(demo_path)
            self._check_cancel(job_id, cancel)
            self._progress(job_id, "normalizing", 65, "正在标准化解析字段")
            player_identifier = self.get_settings().get("player_identifier")
            resolved_player_id = self._resolve_player_id(parsed, str(player_identifier or ""))
            if player_identifier and resolved_player_id is None:
                parsed.warnings.append(f"未在 Demo 中唯一匹配玩家 ID/名称“{player_identifier}”")
            match_id = self._persist_match(demo_id, parsed)
            self._progress(job_id, "computing_metrics", 80, "正在计算个人指标")
            if resolved_player_id:
                metrics = calculate_all(MetricContext(match=parsed, player_id=resolved_player_id))
                self._persist_metrics(match_id, resolved_player_id, metrics)
            self._progress(job_id, "building_review_snapshots", 94, "正在建立复盘候选")
            self._finish_job(job_id, "completed", 100)
            with self.database.session() as session:
                demo = session.get(DemoFile, demo_id)
                if demo:
                    demo.status = "parsed" if not parsed.warnings else "partially_parsed"
                    demo.error_code = None
                    demo.error_message = None
            self.emit(
                "job.completed",
                {"job_id": job_id, "match_id": match_id, "warnings": parsed.warnings},
            )
        except (ApplicationError, DemoParseError, ImportErrorWithCode) as exc:
            code = getattr(exc, "code", "PARSER_CORE_FAILED")
            self._fail_job(job_id, code, str(exc))
        except Exception as exc:
            self._fail_job(job_id, "PARSER_CORE_FAILED", str(exc))
        finally:
            self.cancel_events.pop(job_id, None)

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        cancel = self.cancel_events.get(job_id)
        if cancel is None:
            raise ApplicationError("JOB_NOT_RUNNING", "任务当前未运行")
        cancel.set()
        return {"job_id": job_id, "cancellation_requested": True}

    def list_jobs(self) -> dict[str, Any]:
        with self.database.session() as session:
            jobs = session.scalars(select(ParseJob).order_by(ParseJob.created_at.desc())).all()
            return {
                "items": [
                    {
                        "job_id": job.id,
                        "type": job.type,
                        "status": job.status,
                        "stage": job.stage,
                        "progress": job.progress,
                        "created_at": job.created_at.isoformat(),
                        "error_code": job.error_code,
                        "error_message": job.error_message,
                        "retry_count": job.retry_count,
                    }
                    for job in jobs
                ]
            }

    def list_matches(self) -> dict[str, Any]:
        profile = self.get_settings()
        player_identifier = str(profile.get("player_identifier") or "")
        with self.database.session() as session:
            matches = session.scalars(select(Match).order_by(Match.created_at.desc())).all()
            result: list[dict[str, Any]] = []
            for match in matches:
                demo = session.get(DemoFile, match.demo_id)
                parsed = ParsedMatch.model_validate(match.normalized_data)
                player_id = self._resolve_player_id(parsed, player_identifier)
                result.append(self._match_summary(match, demo, parsed, player_id))
            return {"items": result}

    def relink_demo(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.imports.relink(str(params.get("demo_id", "")), str(params.get("path", "")))
        except ImportErrorWithCode as exc:
            raise ApplicationError(exc.code, str(exc)) from exc

    def create_analysis(self, params: dict[str, Any]) -> dict[str, Any]:
        match_ids = params.get("match_ids")
        player_identifier = str(
            params.get("player_identifier")
            or params.get("player_id")
            or self.get_settings().get("player_identifier")
            or ""
        ).strip()
        if not isinstance(match_ids, list) or not match_ids or not player_identifier:
            raise ApplicationError("INVALID_PARAMS", "至少选择一场比赛并配置本人玩家 ID/名称")
        with self.database.session() as session:
            rows = [session.get(Match, str(match_id)) for match_id in match_ids]
            if any(row is None for row in rows):
                raise ApplicationError("MATCH_NOT_FOUND", "选择中包含不存在的比赛")
            matches = [
                (row.id, ParsedMatch.model_validate(row.normalized_data)) for row in rows if row
            ]
        resolved_matches: list[tuple[str, ParsedMatch, str]] = []
        for match_id, match in matches:
            resolved_player_id = self._resolve_player_id(match, player_identifier)
            if resolved_player_id is None:
                raise ApplicationError(
                    "PLAYER_NOT_FOUND",
                    f"所选比赛中未唯一匹配玩家 ID/名称“{player_identifier}”",
                )
            resolved_matches.append((match_id, match, resolved_player_id))
        per_match = [
            calculate_all(MetricContext(match=match, player_id=resolved_player_id))
            for _, match, resolved_player_id in resolved_matches
        ]
        metrics = aggregate_metrics(per_match)
        issues = IssueDetector().detect(metrics)
        strengths = StrengthDetector().detect(metrics, len(matches))
        reviews = ReviewRoundSelector().select(matches, issues)
        warnings = list(
            dict.fromkeys(warning for _, match in matches for warning in match.warnings)
        )
        report = build_deterministic_report(
            match_count=len(matches),
            round_count=sum(len(match.rounds) for _, match in matches),
            metrics=metrics,
            issues=issues,
            strengths=strengths,
            reviews=reviews,
            warnings=warnings,
        )
        analysis_id = str(uuid4())
        report_path = self.paths.reports / f"{analysis_id}.json"
        report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        with self.database.session() as session:
            session.add(
                Analysis(
                    id=analysis_id,
                    match_ids=[str(match_id) for match_id in match_ids],
                    player_id=player_identifier,
                    report_kind="local",
                    report_path=str(report_path),
                )
            )
        return {"analysis_id": analysis_id, "report": report.model_dump(mode="json")}

    def list_analyses(self) -> dict[str, Any]:
        with self.database.session() as session:
            analyses = session.scalars(select(Analysis).order_by(Analysis.created_at.desc())).all()
            items: list[dict[str, Any]] = []
            for analysis in analyses:
                report_available = False
                summary: dict[str, Any] = {}
                try:
                    report_path = self._safe_data_path(
                        Path(analysis.report_path), self.paths.reports
                    )
                    if report_path.is_file():
                        report_data = json.loads(report_path.read_text(encoding="utf-8"))
                        raw_summary = report_data.get("report_summary", {})
                        if isinstance(raw_summary, dict):
                            summary = raw_summary
                        report_available = True
                except (ApplicationError, OSError, ValueError, TypeError):
                    report_available = False
                items.append(
                    {
                        "analysis_id": analysis.id,
                        "status": analysis.status,
                        "report_kind": analysis.report_kind,
                        "source_changed": analysis.source_changed,
                        "created_at": analysis.created_at.isoformat(),
                        "match_count": len(analysis.match_ids),
                        "report_available": report_available,
                        "one_sentence_summary": summary.get("one_sentence_summary"),
                        "rounds_analyzed": summary.get("rounds_analyzed"),
                        "data_confidence": summary.get("data_confidence"),
                    }
                )
            return {"items": items}

    def get_analysis(self, analysis_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            analysis = session.get(Analysis, analysis_id)
            if analysis is None:
                raise ApplicationError("ANALYSIS_NOT_FOUND", "分析报告不存在")
            path = self._safe_data_path(Path(analysis.report_path), self.paths.reports)
            if not path.exists():
                raise ApplicationError("REPORT_NOT_FOUND", "报告文件不存在")
            return {
                "analysis_id": analysis.id,
                "status": analysis.status,
                "source_changed": analysis.source_changed,
                "report": json.loads(path.read_text(encoding="utf-8")),
            }

    def generate_ai_report(self, params: dict[str, Any]) -> dict[str, Any]:
        analysis_id = str(params.get("analysis_id", ""))
        api_key = params.get("api_key")
        if not isinstance(api_key, str) or not api_key:
            raise ApplicationError("LLM_NOT_CONFIGURED", "尚未配置 API Key")
        current = self.get_analysis(analysis_id)
        settings_data = params.get("provider") or self.get_settings().get("provider")
        if not settings_data:
            raise ApplicationError("LLM_NOT_CONFIGURED", "尚未配置 API 服务")
        report_data = current["report"]
        issues = report_data.get("priority_issues", [])
        strengths = report_data.get("strengths", [])
        reviews = report_data.get("review_rounds", [])
        metric_ids = {
            str(metric)
            for issue in issues
            for metric in [*issue.get("metric_refs", []), issue.get("target_metric")]
            if metric
        }
        evidence_ids = {
            str(evidence) for issue in issues for evidence in issue.get("evidence_refs", [])
        }
        provider = OpenAICompatibleProvider(ProviderSettings.model_validate(settings_data), api_key)
        generated = provider.generate(
            report_data,
            issue_ids={str(issue["issue_id"]) for issue in issues},
            strength_ids={str(strength["strength_id"]) for strength in strengths},
            round_ids={str(review["round_id"]) for review in reviews},
            metric_ids=metric_ids,
            evidence_ids=evidence_ids,
        )
        with self.database.session() as session:
            analysis = session.get(Analysis, analysis_id)
            if analysis is None:
                raise ApplicationError("ANALYSIS_NOT_FOUND", "分析报告不存在")
            report_path = self._safe_data_path(Path(analysis.report_path), self.paths.reports)
            report_path.write_text(generated.model_dump_json(indent=2), encoding="utf-8")
            analysis.status = "completed"
            analysis.report_kind = "ai"
        return {"analysis_id": analysis_id, "report": generated.model_dump(mode="json")}

    def delete_report(self, analysis_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            analysis = session.get(Analysis, analysis_id)
            if analysis is None:
                raise ApplicationError("ANALYSIS_NOT_FOUND", "分析报告不存在")
            path = self._safe_data_path(Path(analysis.report_path), self.paths.reports)
            if path.exists():
                path.unlink()
            session.delete(analysis)
        return {"analysis_id": analysis_id, "deleted": True}

    def delete_match_data(self, match_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            match = session.get(Match, match_id)
            if match is None:
                raise ApplicationError("MATCH_NOT_FOUND", "比赛不存在")
            demo_id = match.demo_id
            session.delete(match)
            demo = session.get(DemoFile, demo_id)
            if demo:
                demo.status = "imported" if Path(demo.normalized_path).exists() else "missing"
        parsed_dir = self._safe_data_path(self.paths.parsed / match_id, self.paths.parsed)
        if parsed_dir.exists():
            shutil.rmtree(parsed_dir)
        self.database.mark_reports_stale(match_id)
        return {"match_id": match_id, "deleted": True, "source_demo_deleted": False}

    def close(self) -> None:
        self.database.close()

    def _start_job(self, job_id: str, stage: str, progress: int) -> str:
        with self.database.session() as session:
            job = session.get(ParseJob, job_id)
            if job is None:
                raise ApplicationError("JOB_NOT_FOUND", "任务不存在")
            job.status = "running"
            job.stage = stage
            job.progress = progress
            job.started_at = datetime.utcnow()
            demo_id = str(job.payload["demo_id"])
        self.emit("job.progress", self._job_event(job_id, stage, progress, "正在验证文件"))
        return demo_id

    def _get_demo_path(self, demo_id: str) -> Path:
        with self.database.session() as session:
            demo = session.get(DemoFile, demo_id)
            if demo is None:
                raise ApplicationError("DEMO_NOT_FOUND", "Demo 导入记录不存在")
            path = Path(demo.normalized_path)
        if not path.is_file():
            raise ApplicationError("DEMO_NOT_FOUND", "原始 Demo 文件不存在")
        return path

    def _progress(self, job_id: str, stage: str, progress: int, message: str) -> None:
        with self.database.session() as session:
            job = session.get(ParseJob, job_id)
            if job:
                job.stage = stage
                job.progress = progress
        self.emit("job.progress", self._job_event(job_id, stage, progress, message))

    def _finish_job(self, job_id: str, stage: str, progress: int) -> None:
        with self.database.session() as session:
            job = session.get(ParseJob, job_id)
            if job:
                job.status = "completed"
                job.stage = stage
                job.progress = progress
                job.finished_at = datetime.utcnow()

    def _fail_job(self, job_id: str, code: str, message: str) -> None:
        demo_id: str | None = None
        with self.database.session() as session:
            job = session.get(ParseJob, job_id)
            if job:
                job.status = "cancelled" if code == "JOB_CANCELLED" else "failed"
                job.stage = "cancelled" if code == "JOB_CANCELLED" else "failed"
                job.error_code = code
                job.error_message = message[:500]
                job.finished_at = datetime.utcnow()
                demo_id = str(job.payload.get("demo_id", ""))
            if demo_id:
                demo = session.get(DemoFile, demo_id)
                if demo:
                    demo.status = "failed"
                    demo.error_code = code
                    demo.error_message = message[:500]
        self.emit("job.failed", {"job_id": job_id, "code": code, "message": message})

    @staticmethod
    def _check_cancel(job_id: str, event: Event) -> None:
        if event.is_set():
            raise ApplicationError("JOB_CANCELLED", f"任务 {job_id} 已取消")

    @staticmethod
    def _job_event(job_id: str, stage: str, progress: int, message: str) -> dict[str, Any]:
        return {"job_id": job_id, "stage": stage, "progress": progress, "message": message}

    def _persist_match(self, demo_id: str, parsed: ParsedMatch) -> str:
        match_id = str(uuid4())
        match_dir = self.paths.parsed / match_id
        match_dir.mkdir(parents=True, exist_ok=True)
        for name, frame in parsed.dense_frames.items():
            safe_name = "".join(char for char in name if char.isalnum() or char in {"-", "_"})
            path = match_dir / f"{safe_name}.parquet"
            try:
                if hasattr(frame, "write_parquet"):
                    frame.write_parquet(path)
                elif hasattr(frame, "to_parquet"):
                    frame.to_parquet(path, index=False)
            except (OSError, TypeError, ValueError) as exc:
                parsed.warnings.append(f"{name} Parquet 写入失败：{exc}")
        payload = parsed.model_dump(mode="json", exclude={"dense_frames"})
        with self.database.session() as session:
            old = session.scalar(select(Match).where(Match.demo_id == demo_id))
            if old:
                old.map_name = parsed.map_name
                old.tick_rate = parsed.tick_rate
                old.parser_name = parsed.parser_name
                old.parser_version = parsed.parser_version
                old.quality = parsed.quality.model_dump(mode="json")
                old.normalized_data = payload
                old.parse_status = "partially_parsed" if parsed.warnings else "parsed"
                shutil.rmtree(match_dir, ignore_errors=True)
                return old.id
            session.add(
                Match(
                    id=match_id,
                    demo_id=demo_id,
                    map_name=parsed.map_name,
                    played_at=parsed.played_at,
                    tick_rate=parsed.tick_rate,
                    parser_name=parsed.parser_name,
                    parser_version=parsed.parser_version,
                    quality=parsed.quality.model_dump(mode="json"),
                    normalized_data=payload,
                    parse_status="partially_parsed" if parsed.warnings else "parsed",
                )
            )
        return match_id

    def _persist_metrics(self, match_id: str, player_id: str, metrics: list[MetricResult]) -> None:
        with self.database.session() as session:
            session.execute(delete(MetricValue).where(MetricValue.match_id == match_id))
            for metric in metrics:
                session.add(
                    MetricValue(
                        id=str(uuid4()),
                        match_id=match_id,
                        player_id=player_id,
                        metric_id=metric.metric_id,
                        value=metric.value,
                        sample_size=metric.sample_size,
                        status=metric.status.value,
                        confidence=metric.confidence,
                        payload=metric.model_dump(mode="json"),
                    )
                )

    @staticmethod
    def _match_summary(
        match: Match, demo: DemoFile | None, parsed: ParsedMatch, player_id: str | None
    ) -> dict[str, Any]:
        if player_id is None:
            return {
                "match_id": match.id,
                "demo_id": match.demo_id,
                "filename": demo.filename if demo else None,
                "map_name": match.map_name,
                "played_at": match.played_at or match.created_at.isoformat(),
                "rounds": len(parsed.rounds),
                "kills": None,
                "deaths": None,
                "kd": None,
                "adr": None,
                "round_wins": None,
                "quality": match.quality,
                "parse_status": match.parse_status,
                "source_exists": Path(demo.normalized_path).exists() if demo else False,
                "parser_version": match.parser_version,
                "schema_version": match.schema_version,
                "player_match_status": "unavailable",
            }
        player_kills = sum(kill.attacker_id == player_id for kill in parsed.kills)
        player_deaths = sum(kill.victim_id == player_id for kill in parsed.kills)
        damage = sum(d.amount for d in parsed.damages if d.attacker_id == player_id)
        player_side_by_round = {
            kill.round_id: kill.attacker_side
            for kill in parsed.kills
            if kill.attacker_id == player_id and kill.attacker_side
        }
        wins = sum(
            round_.winner_side == player_side_by_round.get(round_.round_id)
            for round_ in parsed.rounds
            if round_.round_id in player_side_by_round
        )
        return {
            "match_id": match.id,
            "demo_id": match.demo_id,
            "filename": demo.filename if demo else None,
            "map_name": match.map_name,
            "played_at": match.played_at or match.created_at.isoformat(),
            "rounds": len(parsed.rounds),
            "kills": player_kills,
            "deaths": player_deaths,
            "kd": player_kills / player_deaths if player_deaths else None,
            "adr": damage / len(parsed.rounds) if parsed.rounds else None,
            "round_wins": wins,
            "quality": match.quality,
            "parse_status": match.parse_status,
            "source_exists": Path(demo.normalized_path).exists() if demo else False,
            "parser_version": match.parser_version,
            "schema_version": match.schema_version,
            "player_match_status": "matched",
        }

    @staticmethod
    def _resolve_player_id(parsed: ParsedMatch, player_identifier: str) -> str | None:
        identifier = player_identifier.strip()
        if not identifier:
            return None
        for player in parsed.players:
            if player.steam_id == identifier:
                return player.steam_id
        exact_names = [
            player.steam_id for player in parsed.players if player.name.strip() == identifier
        ]
        if len(exact_names) == 1:
            return exact_names[0]
        folded = identifier.casefold()
        folded_names = [
            player.steam_id for player in parsed.players if player.name.strip().casefold() == folded
        ]
        return folded_names[0] if len(folded_names) == 1 else None

    @staticmethod
    def _safe_data_path(path: Path, root: Path) -> Path:
        resolved = path.resolve(strict=False)
        root_resolved = root.resolve(strict=False)
        if not resolved.is_relative_to(root_resolved):
            raise ApplicationError("PATH_OUTSIDE_DATA_DIR", "拒绝访问应用数据目录之外的路径")
        return resolved


def aggregate_metrics(groups: list[list[MetricResult]]) -> list[MetricResult]:
    by_id: dict[str, list[MetricResult]] = defaultdict(list)
    for group in groups:
        for metric in group:
            if metric.value is not None and metric.status is not MetricStatus.UNAVAILABLE:
                by_id[metric.metric_id].append(metric)
    aggregated: list[MetricResult] = []
    for metric_id, metrics in by_id.items():
        sample_size = sum(metric.sample_size for metric in metrics)
        if sample_size == 0:
            continue
        value = sum((metric.value or 0) * metric.sample_size for metric in metrics) / sample_size
        minimum = (
            15
            if metric_id
            in {
                "first_shot_hit_rate",
                "normalized_speed_at_first_shot",
                "first_damage_conversion_rate",
                "multi_angle_exposure_rate",
            }
            else 5
        )
        estimated = any(metric.status is MetricStatus.ESTIMATED for metric in metrics)
        status = MetricStatus.ESTIMATED if estimated else MetricStatus.AVAILABLE
        if sample_size < minimum:
            status = MetricStatus.INSUFFICIENT_SAMPLE
        aggregated.append(
            MetricResult(
                metric_id=metric_id,
                value=value,
                sample_size=sample_size,
                status=status,
                confidence=min(1.0, sample_size / (minimum * 2))
                * min(metric.confidence for metric in metrics),
                evidence_refs=list(
                    dict.fromkeys(ref for metric in metrics for ref in metric.evidence_refs)
                )[:20],
            )
        )
    return aggregated
