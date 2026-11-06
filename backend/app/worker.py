import argparse
import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from typing import Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import engine
from app.discovery.fetcher import SafeFetcher
from app.discovery.service import expire_past_events, run_discovery_for_source
from app.models import DiscoverySource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("discovery-worker")


class DiscoveryWorker:
    def __init__(self):
        self.running = False
        self._active_sources: Set[int] = set()
        self._lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(settings.discovery_max_concurrent_sources)
        self.fetcher = SafeFetcher(
            user_agent=settings.discovery_user_agent,
            timeout_seconds=settings.discovery_request_timeout,
        )

    async def run_source_with_lock(self, source_id: int) -> None:
        async with self._lock:
            if source_id in self._active_sources:
                logger.debug("Source %d is already actively running, skipping", source_id)
                return
            self._active_sources.add(source_id)

        try:
            async with self.semaphore:
                with Session(engine) as db:
                    await run_discovery_for_source(db, source_id, self.fetcher)
        except Exception as exc:
            logger.exception("Unexpected error executing source %d: %s", source_id, exc)
        finally:
            async with self._lock:
                self._active_sources.discard(source_id)

    async def execute_due_sources(self) -> int:
        now = datetime.now(timezone.utc)
        due_source_ids: list[int] = []

        with Session(engine) as db:
            sources = db.scalars(
                select(DiscoverySource)
                .where(DiscoverySource.is_enabled.is_(True))
                .order_by(DiscoverySource.id)
            ).all()

            for source in sources:
                if source.last_crawl_time is None:
                    due_source_ids.append(source.id)
                else:
                    last_crawl = source.last_crawl_time
                    if last_crawl.tzinfo is None:
                        last_crawl = last_crawl.replace(tzinfo=timezone.utc)
                    elapsed_seconds = (now - last_crawl).total_seconds()
                    interval_seconds = (source.crawl_interval or settings.discovery_interval_minutes) * 60
                    if elapsed_seconds >= interval_seconds:
                        due_source_ids.append(source.id)

            # Also check and expire past events
            try:
                expire_past_events(db)
            except Exception as exc:
                logger.warning("Error running event expiry check: %s", exc)

        if not due_source_ids:
            logger.debug("No discovery sources currently due for crawl")
            return 0

        logger.info("Found %d discovery sources due for crawl: %s", len(due_source_ids), due_source_ids)
        tasks = [self.run_source_with_lock(sid) for sid in due_source_ids]
        await asyncio.gather(*tasks, return_exceptions=True)
        return len(due_source_ids)

    async def start(self, once: bool = False) -> None:
        self.running = True
        logger.info(
            "Starting Tamil Event Discovery Worker (enabled=%s, interval=%dm, max_concurrency=%d)",
            settings.discovery_enabled,
            settings.discovery_interval_minutes,
            settings.discovery_max_concurrent_sources,
        )

        if not settings.discovery_enabled:
            logger.warning("Discovery is disabled via DISCOVERY_ENABLED setting. Exiting.")
            return

        while self.running:
            try:
                await self.execute_due_sources()
            except Exception as exc:
                logger.exception("Error in discovery worker iteration: %s", exc)

            if once:
                logger.info("One-off run requested. Worker exiting.")
                break

            # Poll every 60 seconds
            for _ in range(60):
                if not self.running:
                    break
                await asyncio.sleep(1)

        logger.info("Discovery Worker stopped cleanly.")

    def stop(self) -> None:
        logger.info("Shutdown signal received. Stopping worker...")
        self.running = False


def main():
    parser = argparse.ArgumentParser(description="Tamil Event Discovery Worker")
    parser.add_argument("--once", action="store_true", help="Run once for due sources and exit")
    args = parser.parse_args()

    worker = DiscoveryWorker()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def handle_signal():
        worker.stop()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal)

    try:
        loop.run_until_complete(worker.start(once=args.once))
    except KeyboardInterrupt:
        worker.stop()
        loop.run_until_complete(asyncio.sleep(0.5))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
