from __future__ import annotations

import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Any, TextIO

from pydantic import ValidationError
from roundlens_analyzer import PROTOCOL_VERSION
from roundlens_analyzer.app.config import AppPaths
from roundlens_analyzer.app.service import AnalyzerApplication, ApplicationError
from roundlens_analyzer.ipc.models import RpcRequest
from roundlens_analyzer.llm.provider import ProviderError
from roundlens_analyzer.security.redaction import redact_text

LOGGER = logging.getLogger("roundlens.sidecar")


class JsonlServer:
    def __init__(
        self,
        data_dir: Path,
        input_stream: TextIO = sys.stdin,
        output_stream: TextIO = sys.stdout,
    ) -> None:
        self.input = input_stream
        self.output = output_stream
        self.write_lock = Lock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="roundlens-parser")
        self.app = AnalyzerApplication(AppPaths.create(data_dir), self.emit)
        self.running = True

    def run(self) -> int:
        self.emit(
            "sidecar.ready",
            {"protocol_version": PROTOCOL_VERSION, "status": "ready"},
        )
        for line in self.input:
            if not self.running:
                break
            if not line.strip():
                continue
            self.handle_line(line)
        self.executor.shutdown(wait=True, cancel_futures=False)
        self.app.close()
        return 0

    def handle_line(self, line: str) -> None:
        request_id = "unknown"
        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                request_id = str(payload.get("id", "unknown"))
            request = RpcRequest.model_validate(payload)
            if request.protocol_version != PROTOCOL_VERSION:
                raise ApplicationError("PROTOCOL_VERSION_MISMATCH", "IPC 协议版本不兼容")
            result = self.dispatch(request.method, dict(request.params))
            self.write({"protocol_version": PROTOCOL_VERSION, "id": request.id, "result": result})
        except json.JSONDecodeError:
            self.write_error(request_id, "INVALID_JSON", "请求不是合法 JSON")
        except ValidationError as exc:
            self.write_error(
                request_id, "INVALID_REQUEST", "请求结构无效", {"errors": exc.errors()}
            )
        except (ApplicationError, ProviderError) as exc:
            self.write_error(
                request_id,
                exc.code,
                str(exc),
                getattr(exc, "details", {}),
            )
        except Exception as exc:
            LOGGER.exception("Unhandled RPC failure: %s", redact_text(str(exc)))
            self.write_error(request_id, "INTERNAL_ERROR", "Sidecar 处理请求时发生内部错误")

    def dispatch(self, method: str, params: dict[str, Any]) -> Any:
        if method in {"health", "initialize"}:
            return self.app.health()
        if method == "get_settings":
            return self.app.get_settings()
        if method == "update_profile":
            return self.app.update_profile(params)
        if method == "update_provider":
            return self.app.update_provider(params)
        if method == "test_provider":
            return self.app.test_provider(params)
        if method == "scan_demos":
            return self.app.scan_demos(params)
        if method == "import_demos":
            return self.app.import_demos(params)
        if method == "list_demos":
            return self.app.list_demos()
        if method == "parse_demo":
            job_id = self.app.create_parse_job(str(params.get("demo_id", "")))
            self.executor.submit(self.app.run_parse_job, job_id)
            return {"job_id": job_id}
        if method == "cancel_job":
            return self.app.cancel_job(str(params.get("job_id", "")))
        if method == "list_jobs":
            return self.app.list_jobs()
        if method == "list_matches":
            return self.app.list_matches()
        if method == "relink_demo":
            return self.app.relink_demo(params)
        if method == "create_analysis":
            return self.app.create_analysis(params)
        if method == "list_analyses":
            return self.app.list_analyses()
        if method == "get_analysis":
            return self.app.get_analysis(str(params.get("analysis_id", "")))
        if method == "generate_ai_report":
            return self.app.generate_ai_report(params)
        if method == "delete_report":
            return self.app.delete_report(str(params.get("analysis_id", "")))
        if method == "delete_match_data":
            return self.app.delete_match_data(str(params.get("match_id", "")))
        if method == "shutdown":
            self.running = False
            return {"shutting_down": True}
        raise ApplicationError("METHOD_NOT_FOUND", "不支持的 RPC 方法")

    def emit(self, event: str, data: dict[str, Any]) -> None:
        self.write({"protocol_version": PROTOCOL_VERSION, "event": event, "data": data})

    def write_error(
        self,
        request_id: str,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.write(
            {
                "protocol_version": PROTOCOL_VERSION,
                "id": request_id,
                "error": {"code": code, "message": message, "details": details or {}},
            }
        )

    def write(self, payload: dict[str, Any]) -> None:
        # ASCII-only JSON is valid UTF-8 regardless of the inherited Windows
        # console code page. JSON decoding restores the original Unicode text.
        encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        with self.write_lock:
            try:
                self.output.write(encoded + "\n")
                self.output.flush()
            except (BrokenPipeError, OSError):
                # The desktop shell may restart during development. Losing its
                # pipe must not turn a valid parse into PARSER_CORE_FAILED.
                self.running = False
