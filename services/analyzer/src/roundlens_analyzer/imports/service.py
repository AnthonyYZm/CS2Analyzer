from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from roundlens_analyzer.storage.database import Database
from roundlens_analyzer.storage.models import DemoFile
from sqlalchemy import select

ProgressCallback = Callable[[int], None]


class ImportErrorWithCode(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_demo_path(path_value: str | Path) -> Path:
    path = Path(path_value).expanduser().resolve(strict=False)
    if path.suffix.lower() != ".dem":
        raise ImportErrorWithCode("DEMO_UNSUPPORTED", "只支持 .dem 文件")
    if not path.exists():
        raise ImportErrorWithCode("DEMO_NOT_FOUND", "原始 Demo 文件不存在")
    if not path.is_file():
        raise ImportErrorWithCode("DEMO_UNREADABLE", "选择的路径不是普通文件")
    try:
        with path.open("rb") as stream:
            stream.read(1)
    except OSError as exc:
        raise ImportErrorWithCode("DEMO_UNREADABLE", "无法读取 Demo 文件") from exc
    return path


def stream_sha256(
    path: Path,
    callback: ProgressCallback | None = None,
    chunk_size: int = 4 * 1024 * 1024,
) -> str:
    size = path.stat().st_size
    processed = 0
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
            processed += len(chunk)
            if callback:
                callback(100 if size == 0 else min(100, int(processed * 100 / size)))
    return digest.hexdigest()


class DemoImportService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def import_paths(
        self,
        paths: Iterable[str],
        source_type: str = "manual",
        progress: Callable[[str, int], None] | None = None,
    ) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        for value in paths:
            try:
                path = validate_demo_path(value)
                callback: ProgressCallback | None = None
                if progress:
                    filename = path.name

                    def callback(percent: int, current_filename: str = filename) -> None:
                        progress(current_filename, percent)

                digest = stream_sha256(path, callback)
                with self.database.session() as session:
                    existing = session.scalar(select(DemoFile).where(DemoFile.sha256 == digest))
                    if existing is not None:
                        existing.exists = Path(existing.normalized_path).exists()
                        results.append(
                            {
                                "demo_id": existing.id,
                                "filename": existing.filename,
                                "status": "duplicate",
                                "sha256": digest,
                            }
                        )
                        continue
                    stat = path.stat()
                    demo = DemoFile(
                        id=str(uuid4()),
                        original_path=str(Path(value)),
                        normalized_path=str(path),
                        filename=path.name,
                        size_bytes=stat.st_size,
                        modified_at=datetime.fromtimestamp(stat.st_mtime),
                        sha256=digest,
                        source_type=source_type,
                        exists=True,
                        status="imported",
                    )
                    session.add(demo)
                    results.append(
                        {
                            "demo_id": demo.id,
                            "filename": demo.filename,
                            "status": demo.status,
                            "sha256": digest,
                        }
                    )
            except ImportErrorWithCode as exc:
                results.append({"path": str(value), "status": "invalid", "error": exc.code})
        return results

    def scan_directories(self, directories: Iterable[str]) -> list[dict[str, object]]:
        discovered: dict[str, dict[str, object]] = {}
        for raw in directories:
            directory = Path(raw).expanduser().resolve(strict=False)
            if not directory.is_dir():
                continue
            for path in directory.rglob("*.dem"):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                discovered[str(path.resolve())] = {
                    "path": str(path.resolve()),
                    "filename": path.name,
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "status": "discovered",
                }
        return sorted(discovered.values(), key=lambda item: str(item["modified_at"]), reverse=True)

    def list_demos(self) -> list[dict[str, object]]:
        with self.database.session() as session:
            demos = session.scalars(select(DemoFile).order_by(DemoFile.imported_at.desc())).all()
            rows: list[dict[str, object]] = []
            for demo in demos:
                exists = Path(demo.normalized_path).exists()
                if demo.exists != exists:
                    demo.exists = exists
                    if not exists and demo.status not in {"failed", "invalid"}:
                        demo.status = "missing"
                rows.append(
                    {
                        "demo_id": demo.id,
                        "filename": demo.filename,
                        "size_bytes": demo.size_bytes,
                        "sha256": demo.sha256,
                        "imported_at": demo.imported_at.isoformat(),
                        "exists": exists,
                        "status": demo.status,
                        "source_type": demo.source_type,
                    }
                )
            return rows

    def relink(self, demo_id: str, new_path: str) -> dict[str, object]:
        path = validate_demo_path(new_path)
        digest = stream_sha256(path)
        with self.database.session() as session:
            demo = session.get(DemoFile, demo_id)
            if demo is None:
                raise ImportErrorWithCode("DEMO_NOT_FOUND", "未找到导入记录")
            if digest != demo.sha256:
                raise ImportErrorWithCode("DEMO_HASH_MISMATCH", "所选文件与原 Demo 哈希不一致")
            demo.original_path = new_path
            demo.normalized_path = str(path)
            demo.exists = True
            demo.status = "imported"
            return {"demo_id": demo.id, "status": demo.status, "exists": True}
