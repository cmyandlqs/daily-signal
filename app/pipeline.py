from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import AppConfig, SourceConfig
from app.fetcher.rss_client import fetch_rss
from app.filter.hard_filter import apply_hard_filter, make_title_fingerprint
from app.filter.scorer import score_entries
from app.generator.markdown_builder import build_markdown_report
from app.models import Entry, Report, Source
from app.summarizer.fallback import FallbackSummarizer
from app.summarizer.qwen_openai import QwenOpenAISummarizer

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    date: str
    slot: str
    report_path: str
    fetched_count: int
    kept_count: int
    summary_fail_count: int
    dropped_by_reason: dict[str, int]
    skipped_as_done: bool = False


def _window_for_slot(now_local: datetime, slot: str) -> tuple[datetime, datetime]:
    if slot == "AM":
        anchor_local = now_local.replace(hour=8, minute=0, second=0, microsecond=0)
    else:
        anchor_local = now_local.replace(hour=17, minute=0, second=0, microsecond=0)

    end_utc = anchor_local.astimezone(UTC)
    start_utc = end_utc - timedelta(hours=12)
    return start_utc, end_utc


def _ensure_sources(session: Session, source_cfgs: list[SourceConfig]) -> None:
    existing = {s.rss_url: s for s in session.scalars(select(Source)).all()}
    changed = False
    for cfg in source_cfgs:
        source = existing.get(cfg.rss_url)
        if source is None:
            source = Source(
                name=cfg.name,
                platform=cfg.platform,
                rss_url=cfg.rss_url,
                enabled=cfg.enabled,
                source_weight=cfg.source_weight,
            )
            session.add(source)
            changed = True
        else:
            source.name = cfg.name
            source.platform = cfg.platform
            source.enabled = cfg.enabled
            source.source_weight = cfg.source_weight
            changed = True
    if changed:
        session.commit()


def _upsert_report(session: Session, date_str: str, slot: str) -> Report:
    report = session.scalar(select(Report).where(Report.date == date_str, Report.slot == slot))
    if report is None:
        report = Report(date=date_str, slot=slot, file_path="", status="pending")
        session.add(report)
        session.commit()
        session.refresh(report)
    return report


def run_pipeline(
    session_factory: sessionmaker[Session],
    cfg: AppConfig,
    slot: str,
    force: bool = False,
) -> PipelineResult:
    tz = ZoneInfo(cfg.schedule.timezone)
    now_local = datetime.now(tz)
    date_str = now_local.strftime("%Y-%m-%d")

    with session_factory() as session:
        _ensure_sources(session, cfg.sources)

        report = _upsert_report(session, date_str, slot)
        if report.status == "done" and not force:
            return PipelineResult(
                date=date_str,
                slot=slot,
                report_path=report.file_path,
                fetched_count=0,
                kept_count=0,
                summary_fail_count=0,
                dropped_by_reason={},
                skipped_as_done=True,
            )
        if force and report.status == "done":
            report.status = "pending"
            session.commit()

        enabled_sources = session.scalars(select(Source).where(Source.enabled.is_(True))).all()
        fetched_count = 0

        for source in enabled_sources:
            try:
                source_items = fetch_rss(source.rss_url)
            except Exception:
                source_items = []
            fetched_count += len(source_items)
            for item in source_items:
                entry = Entry(
                    source_id=source.id,
                    title=item.title,
                    url=item.url,
                    canonical_url=item.canonical_url,
                    title_fingerprint=make_title_fingerprint(item.title),
                    content_raw=item.content_raw or "",
                    published_at=item.published_at.replace(tzinfo=None),
                    status="raw",
                )
                exists = session.scalar(
                    select(Entry.id).where(
                        Entry.source_id == source.id,
                        Entry.canonical_url == item.canonical_url,
                    )
                )
                if exists is not None:
                    continue
                session.add(entry)
                session.flush()

        session.commit()

        window_start, window_end = _window_for_slot(now_local, slot)
        enabled_source_ids = [s.id for s in enabled_sources]
        candidates = session.scalars(
            select(Entry).where(
                Entry.source_id.in_(enabled_source_ids),
                Entry.published_at >= window_start.replace(tzinfo=None),
                Entry.published_at <= window_end.replace(tzinfo=None),
            )
        ).all()

        filter_result = apply_hard_filter(
            entries=candidates,
            filter_cfg=cfg.filters,
            window_start=window_start.replace(tzinfo=None),
            window_end=window_end.replace(tzinfo=None),
        )

        source_map = {s.id: s for s in enabled_sources}
        scored = score_entries(
            entries=filter_result.kept,
            source_map=source_map,
            filter_cfg=cfg.filters,
            now=datetime.utcnow(),
        )

        if cfg.summarizer.enabled and cfg.summarizer.provider == "qwen_openai":
            try:
                summarizer = QwenOpenAISummarizer(cfg.summarizer)
            except Exception:
                logger.exception("qwen_openai summarizer init failed, fallback summarizer will be used")
                summarizer = FallbackSummarizer()
        else:
            summarizer = FallbackSummarizer()
        summary_fail_count = 0
        for entry in scored[: cfg.summarizer.top_n]:
            try:
                summary = summarizer.summarize(entry)
                entry.one_liner = summary.one_liner
                entry.bullets_json = json.dumps(summary.bullets, ensure_ascii=False)
                entry.why_it_matters = summary.why_it_matters
                entry.tags_json = json.dumps(summary.tags, ensure_ascii=False)
                entry.status = "summarized"
            except Exception:
                summary_fail_count += 1
                entry.one_liner = (entry.content_raw or "")[:100]
                entry.bullets_json = json.dumps([entry.one_liner], ensure_ascii=False)
                entry.why_it_matters = "信息不足"
                entry.tags_json = "[]"
                entry.status = "summarized"

        report_path = build_markdown_report(scored, cfg.output.dir, date_str, slot)
        report.file_path = report_path
        report.entry_count = len(scored)
        report.summary_fail_count = summary_fail_count
        report.status = "done"
        report.generated_at = datetime.utcnow()
        session.commit()

    return PipelineResult(
        date=date_str,
        slot=slot,
        report_path=report_path,
        fetched_count=fetched_count,
        kept_count=len(scored),
        summary_fail_count=summary_fail_count,
        dropped_by_reason=filter_result.dropped_by_reason,
    )
