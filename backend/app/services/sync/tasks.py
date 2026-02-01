import asyncio
from datetime import datetime, timedelta
import logging
from typing import Optional
import uuid

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.db.models import POSType, SyncStatus, Venue

logger = logging.getLogger(__name__)

# Create async engine for Celery tasks
engine = create_async_engine(settings.DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(bind=True, max_retries=3)
def sync_venue_data(self, venue_id: str, full_sync: bool = False):
    """
    Celery task to sync data for a single venue.

    Args:
        venue_id: UUID of the venue to sync
        full_sync: If True, perform full sync. Otherwise incremental.
    """
    return run_async(_sync_venue_data(venue_id, full_sync))


async def _sync_venue_data(venue_id: str, full_sync: bool = False):
    """Async implementation of venue sync."""
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Venue).where(Venue.id == uuid.UUID(venue_id))
            )
            venue = result.scalar_one_or_none()

            if venue is None:
                logger.error(f"Venue not found: {venue_id}")
                return {"error": "Venue not found"}

            # Update status to in progress
            venue.sync_status = SyncStatus.IN_PROGRESS
            await db.commit()

            # Choose sync service based on POS type
            if venue.pos_type == POSType.IIKO:
                from app.services.sync.iiko_sync import IikoSyncService

                sync_service = IikoSyncService(venue, db)
            elif venue.pos_type == POSType.RKEEPER:
                # TODO: Implement R-Keeper sync
                logger.warning(f"R-Keeper sync not implemented for venue {venue_id}")
                venue.sync_status = SyncStatus.FAILED
                venue.sync_error = "R-Keeper sync not implemented"
                await db.commit()
                return {"error": "R-Keeper sync not implemented"}
            else:
                logger.error(f"Unknown POS type for venue {venue_id}")
                return {"error": "Unknown POS type"}

            # Perform sync
            if full_sync:
                stats = await sync_service.sync_full()
            else:
                stats = await sync_service.sync_incremental()

            await db.commit()
            logger.info(f"Sync completed for venue {venue_id}: {stats}")
            return stats

        except Exception as e:
            logger.exception(f"Sync failed for venue {venue_id}")
            await db.rollback()

            # Update venue status
            result = await db.execute(
                select(Venue).where(Venue.id == uuid.UUID(venue_id))
            )
            venue = result.scalar_one_or_none()
            if venue:
                venue.sync_status = SyncStatus.FAILED
                venue.sync_error = str(e)
                await db.commit()

            raise


@shared_task
def full_sync_all_venues():
    """Celery task to perform full sync for all active venues."""
    return run_async(_full_sync_all_venues())


async def _full_sync_all_venues():
    """Async implementation of full sync for all venues."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Venue.id).where(Venue.is_active == True)
        )
        venue_ids = [str(row[0]) for row in result.fetchall()]

    logger.info(f"Starting full sync for {len(venue_ids)} venues")

    for venue_id in venue_ids:
        # Trigger individual sync tasks
        sync_venue_data.delay(venue_id, full_sync=True)

    return {"venues_queued": len(venue_ids)}


@shared_task
def incremental_sync_all_venues():
    """Celery task to perform incremental sync for all active venues."""
    return run_async(_incremental_sync_all_venues())


async def _incremental_sync_all_venues():
    """Async implementation of incremental sync for all venues."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Venue.id).where(Venue.is_active == True)
        )
        venue_ids = [str(row[0]) for row in result.fetchall()]

    logger.info(f"Starting incremental sync for {len(venue_ids)} venues")

    for venue_id in venue_ids:
        sync_venue_data.delay(venue_id, full_sync=False)

    return {"venues_queued": len(venue_ids)}


@shared_task
def aggregate_daily_sales():
    """Celery task to aggregate daily sales for all venues."""
    return run_async(_aggregate_daily_sales())


async def _aggregate_daily_sales():
    """Async implementation of daily sales aggregation."""
    from app.services.sync.iiko_sync import aggregate_daily_sales as aggregate_fn

    yesterday = (datetime.utcnow() - timedelta(days=1)).date()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Venue.id).where(Venue.is_active == True)
        )
        venue_ids = [row[0] for row in result.fetchall()]

        aggregated = 0
        for venue_id in venue_ids:
            try:
                await aggregate_fn(venue_id, yesterday, db)
                aggregated += 1
            except Exception as e:
                logger.error(f"Failed to aggregate sales for venue {venue_id}: {e}")

        await db.commit()

    logger.info(f"Aggregated daily sales for {aggregated}/{len(venue_ids)} venues")
    return {"aggregated": aggregated, "total": len(venue_ids)}
