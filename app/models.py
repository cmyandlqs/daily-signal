from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    rss_url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_weight: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    entries: Mapped[list["Entry"]] = relationship(back_populates="source")


class Entry(Base):
    __tablename__ = "entries"
    __table_args__ = (UniqueConstraint("source_id", "canonical_url", name="uq_entry_source_canonical"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(2048), nullable=False)
    url: Mapped[str] = mapped_column(String(4096), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(4096), nullable=False)
    title_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    content_raw: Mapped[str] = mapped_column(Text, default="", nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    keyword_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    popularity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    recency_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    one_liner: Mapped[str] = mapped_column(Text, default="", nullable=False)
    bullets_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    why_it_matters: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="raw", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    source: Mapped["Source"] = relationship(back_populates="entries")


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("date", "slot", name="uq_report_date_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)
    slot: Mapped[str] = mapped_column(String(8), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary_fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

