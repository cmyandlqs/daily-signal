from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

from app.config import load_config
from app.database import create_session_factory
from app.models import Base
from app.pipeline import run_pipeline
from app.scheduler.jobs import start_scheduler


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="daily-signal runner")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="initialize database tables")

    once_parser = sub.add_parser("once", help="run one slot once")
    once_parser.add_argument("--slot", choices=["AM", "PM"], required=True)
    once_parser.add_argument(
        "--force",
        action="store_true",
        help="force regenerate report even if this date+slot is already done",
    )

    sub.add_parser("schedule", help="start scheduler service")
    return parser


def _setup_logging() -> None:
    Path("logs").mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        filename="logs/app.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(stream_handler)
    root.addHandler(file_handler)


def main() -> None:
    # Load local .env once so long-running/scheduled runs can read API keys.
    load_dotenv(dotenv_path=Path(".env"), override=False)
    _setup_logging()
    args = _build_parser().parse_args()
    cfg = load_config("config.yaml")
    session_factory = create_session_factory(cfg.database_url)

    if args.command == "init-db":
        engine = session_factory.kw["bind"]
        Base.metadata.create_all(bind=engine)
        logging.info("database initialized")
        return

    if args.command == "once":
        result = run_pipeline(
            session_factory=session_factory,
            cfg=cfg,
            slot=args.slot,
            force=bool(args.force),
        )
        if result.skipped_as_done:
            logging.info("slot %s already generated for %s", result.slot, result.date)
        else:
            logging.info(
                "done slot=%s date=%s fetched=%s kept=%s report=%s",
                result.slot,
                result.date,
                result.fetched_count,
                result.kept_count,
                result.report_path,
            )
        return

    if args.command == "schedule":
        start_scheduler(session_factory=session_factory, cfg=cfg)
        return


if __name__ == "__main__":
    main()
