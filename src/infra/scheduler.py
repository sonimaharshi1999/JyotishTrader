from __future__ import annotations

import logging
import signal
import sys
from typing import Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.settings import ScheduleSettings

logger = logging.getLogger(__name__)


class TradingScheduler:
    def __init__(self, settings: ScheduleSettings) -> None:
        self.settings = settings
        self.scheduler = BlockingScheduler(timezone=settings.timezone)
        self._setup_shutdown_handlers()

    def add_trading_cycle(self, func: Callable, hour: int = 8, minute: int = 0) -> None:
        self.scheduler.add_job(
            func,
            CronTrigger(
                day_of_week="mon-fri",
                hour=hour, minute=minute,
                timezone=self.settings.timezone,
            ),
            id="daily_trade",
            name="Daily trading cycle",
            replace_existing=True,
        )
        logger.info("Scheduled daily trading cycle at %02d:%02d %s", hour, minute, self.settings.timezone)

    def add_stop_monitor(self, func: Callable, interval_minutes: int = 5) -> None:
        self.scheduler.add_job(
            func,
            CronTrigger(
                day_of_week="mon-fri",
                hour="9-16",
                minute=f"*/{interval_minutes}",
                timezone=self.settings.timezone,
            ),
            id="stop_monitor",
            name="Trailing stop monitor",
            replace_existing=True,
        )
        logger.info("Scheduled stop monitor every %d min during market hours", interval_minutes)

    def add_daily_snapshot(self, func: Callable, hour: int = 16, minute: int = 30) -> None:
        self.scheduler.add_job(
            func,
            CronTrigger(
                day_of_week="mon-fri",
                hour=hour, minute=minute,
                timezone=self.settings.timezone,
            ),
            id="daily_snapshot",
            name="End-of-day portfolio snapshot",
            replace_existing=True,
        )
        logger.info("Scheduled daily snapshot at %02d:%02d", hour, minute)

    def start(self) -> None:
        logger.info("Starting scheduler with %d jobs", len(self.scheduler.get_jobs()))
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped by signal")

    def _setup_shutdown_handlers(self) -> None:
        def shutdown(signum, frame):
            logger.info("Received signal %d, shutting down scheduler...", signum)
            self.scheduler.shutdown(wait=False)
            sys.exit(0)

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)
