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
from app.discovery.service import (
    SourceLockedError,
    expire_past_events,
    is_source_locked,
    recover_abandoned_runs,
    run_discovery_for_source,
)
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
                logger.debug("Source %d is locally queued/running, skipping", source_id)
                return
            self._active_sources.add(source_id)

        try:
            async with self.semaphore:
                with Session(engine) as db:
                    # Persisted database-level lock check
                    if is_source_locked(db, source_id):
                        logger.info("Source %d is locked by another runner or replica, skipping", source_id)
                        return
                    await run_discovery_for_source(db, source_id, self.fetcher)
        except SourceLockedError:
            logger.info("Source %d was locked concurrently, skipping", source_id)
        except Exception as exc:
            logger.exception("Unexpected error executing source %d: %s", source_id, exc)
        finally:
            async with self._lock:
                self._active_sources.discard(source_id)

    async def execute_cycle(self) -> int:
        """
        Executes one worker cycle:
        1. Recovers any abandoned runs from previous process crashes.
        2. ALWAYS runs event expiry sweep (even if discovery is disabled or zero sources exist).
        3. Checks due discovery sources and triggers crawls.
        """
        now = datetime.now(timezone.utc)
        due_source_ids: list[int] = []

        with Session(engine) as db:
            # 1. Recover abandoned runs (> 15 minutes old in status 'running')
            try:
                recovered = recover_abandoned_runs(db)
                if recovered > 0:
                    logger.info("Worker iteration recovered %d abandoned run(s)", recovered)
            except Exception as exc:
                logger.warning("Error recovering abandoned runs: %s", exc)

            # 2. Expiry task: MUST ALWAYS run regardless of sources
            try:
                expired = expire_past_events(db)
                if expired > 0:
                    logger.info("Worker expiry sweep marked %d event(s) as expired", expired)
            except Exception as exc:
                logger.error("Error executing scheduled event expiry: %s", exc)

            # If discovery is globally disabled, do not crawl sources
            if not settings.discovery_enabled:
                logger.debug("Discovery disabled in settings; crawled 0 sources")
                return 0

            # 3. Find due sources
            sources = db.scalars(
                select(DiscoverySource)
                .where(DiscoverySource.is_enabled.is_(True))
                .order_by(DiscoverySource.id)
            ).all()

            for source in sources:
                # Check persisted lock
                if is_source_locked(db, source.id):
                    continue

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

        while self.running:
            try:
                await self.execute_cycle()
            except Exception as exc:
                logger.exception("Error in discovery worker iteration: %s", exc)

            if once:
                logger.info("One-off run completed. Worker exiting.")
                break

            # Sleep in 1-second increments to honor graceful shutdown immediately
            interval_secs = max(10, settings.discovery_interval_minutes * 60)
            for _ in range(interval_secs):
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
