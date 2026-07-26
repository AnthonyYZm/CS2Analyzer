from __future__ import annotations

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from roundlens_analyzer.app.config import AppPaths
from roundlens_analyzer.storage.models import Base, ParseJob, PlayerProfile
from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

SCHEMA_VERSION = 2


class Database:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths
        self.db_path = paths.database / "roundlens.db"
        self._backup_existing()
        self.engine = create_engine(
            f"sqlite:///{self.db_path.as_posix()}",
            future=True,
            connect_args={"check_same_thread": False},
        )
        self._configure_sqlite(self.engine)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)
        self._initialize()

    @staticmethod
    def _configure_sqlite(engine: Engine) -> None:
        @event.listens_for(engine, "connect")
        def set_pragmas(connection: Any, _: Any) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    def _backup_existing(self) -> None:
        if not self.db_path.exists() or self.db_path.stat().st_size == 0:
            return
        date = datetime.now(tz=UTC).strftime("%Y%m%d")
        backup = self.paths.backups / f"roundlens-{date}.db"
        if not backup.exists():
            shutil.copy2(self.db_path, backup)

    def _initialize(self) -> None:
        with self.session() as session:
            analysis_columns = {
                str(row[1])
                for row in session.connection().exec_driver_sql("PRAGMA table_info(analyses)")
            }
            if "report_kind" not in analysis_columns:
                session.connection().exec_driver_sql(
                    "ALTER TABLE analyses ADD COLUMN report_kind "
                    "VARCHAR(24) NOT NULL DEFAULT 'local'"
                )
            session.connection().exec_driver_sql(f"PRAGMA user_version={SCHEMA_VERSION}")
            running = session.scalars(select(ParseJob).where(ParseJob.status == "running")).all()
            for job in running:
                job.status = "interrupted"
                job.stage = "interrupted"
                job.finished_at = datetime.utcnow()
            if session.get(PlayerProfile, 1) is None:
                session.add(PlayerProfile(id=1))

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self.session_factory.begin() as session:
            yield session

    def mark_reports_stale(self, match_id: str) -> None:
        from roundlens_analyzer.storage.models import Analysis

        with self.session() as session:
            analyses = session.scalars(select(Analysis)).all()
            for analysis in analyses:
                if match_id in analysis.match_ids:
                    analysis.source_changed = True
                    analysis.status = "stale"

    def close(self) -> None:
        self.engine.dispose()
