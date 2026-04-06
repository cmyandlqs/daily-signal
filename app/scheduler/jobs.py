from __future__ import annotations

import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import AppConfig
from app.models import Report
from app.pipeline import run_pipeline

logger = logging.getLogger(__name__)


def _run_slot(session_factory: sessionmaker[Session], cfg: AppConfig, slot: str) -> None:
    try:
        result = run_pipeline(session_factory=session_factory, cfg=cfg, slot=slot)
        if result.skipped_as_done:
            logger.info("slot %s already done for %s, skip", slot, result.date)
            return
        logger.info(
            "slot=%s date=%s fetched=%s kept=%s report=%s",
            result.slot,
            result.date,
            result.fetched_count,
            result.kept_count,
            result.report_path,
        )
    except Exception:
        logger.exception("slot %s run failed", slot)


def compensate_missed_slots(session_factory: sessionmaker[Session], cfg: AppConfig) -> None:
    tz = ZoneInfo(cfg.schedule.timezone)
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")

    with session_factory() as session:
        completed = {
            r.slot
            for r in session.scalars(
                select(Report).where(
                    Report.date == today,
                    Report.status == "done",
                )
            ).all()
        }

    for slot_cfg in cfg.schedule.slots:
        hour, minute = map(int, slot_cfg.time.split(":"))
        due_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        slot_name = slot_cfg.name.upper()
        if now >= due_time and slot_name not in completed:
            logger.info("compensating missed slot=%s for date=%s", slot_name, today)
            _run_slot(session_factory, cfg, slot_name)


def start_scheduler(session_factory: sessionmaker[Session], cfg: AppConfig) -> None:
    scheduler = BackgroundScheduler(timezone=cfg.schedule.timezone)
    for slot_cfg in cfg.schedule.slots:
        hour, minute = map(int, slot_cfg.time.split(":"))
        slot_name = slot_cfg.name.upper()
        scheduler.add_job(
            _run_slot,
            CronTrigger(hour=hour, minute=minute, timezone=cfg.schedule.timezone),
            args=[session_factory, cfg, slot_name],
            id=f"daily_signal_{slot_name}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
    scheduler.start()
    logger.info("scheduler started with slots: %s", [s.name for s in cfg.schedule.slots])

    if cfg.schedule.compensate_on_startup:
        compensate_missed_slots(session_factory, cfg)

    try:
        while True:
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("scheduler stopping...")
        scheduler.shutdown()
