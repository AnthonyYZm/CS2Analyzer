from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.utcnow()


class Base(DeclarativeBase):
    pass


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class PlayerProfile(Base):
    __tablename__ = "player_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Legacy column name retained for migration compatibility. The value is a
    # user-entered in-match player identifier: SteamID64 or scoreboard name.
    steam_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    locale: Mapped[str] = mapped_column(String(10), default="zh-CN")
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    scan_directories: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class DemoFile(Base):
    __tablename__ = "demo_files"
    __table_args__ = (Index("ix_demo_files_sha256", "sha256", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    original_path: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_path: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    source_type: Mapped[str] = mapped_column(String(32), default="manual")
    exists: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), default="imported")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ParseJob(Base):
    __tablename__ = "parse_jobs"
    __table_args__ = (Index("ix_parse_jobs_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    stage: Mapped[str] = mapped_column(String(64), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        Index("ix_matches_demo", "demo_id", unique=True),
        Index("ix_matches_played_at", "played_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    demo_id: Mapped[str] = mapped_column(ForeignKey("demo_files.id", ondelete="CASCADE"))
    map_name: Mapped[str] = mapped_column(String(100), default="unknown")
    played_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tick_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    parser_name: Mapped[str] = mapped_column(String(80), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    quality: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    normalized_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    parse_status: Mapped[str] = mapped_column(String(32), default="parsed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class MetricValue(Base):
    __tablename__ = "metric_values"
    __table_args__ = (Index("ix_metric_values_match_metric", "match_id", "metric_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    player_id: Mapped[str] = mapped_column(String(32), nullable=False)
    metric_id: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    match_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    player_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="completed")
    report_kind: Mapped[str] = mapped_column(String(24), default="local")
    source_changed: Mapped[bool] = mapped_column(Boolean, default=False)
    benchmark_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    report_schema_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    report_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
