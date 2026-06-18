from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, AsyncSession
from app.models import BlockedRequest

logger = logging.getLogger(__name__)


async def run_retention_cleanup(engine: AsyncEngine) -> dict:
    """Deletes raw BlockedRequest events older than 30 days while keeping aggregated stats."""
    logger.info("Starting database retention cleanup...")
    async_session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    try:
        async with async_session_factory() as session:
            stmt = delete(BlockedRequest).where(BlockedRequest.timestamp < cutoff)
            result = await session.execute(stmt)
            await session.commit()

            deleted_count = result.rowcount
            logger.info(f"Retention cleanup completed. Deleted {deleted_count} raw events older than {cutoff}.")
            return {
                "status": "success",
                "deleted_count": deleted_count,
                "cutoff_date": cutoff.isoformat(),
                "executed_at": datetime.now(timezone.utc).isoformat()
            }
    except Exception as e:
        logger.error(f"Error during retention cleanup: {e}")
        return {
            "status": "error",
            "message": str(e),
            "executed_at": datetime.now(timezone.utc).isoformat()
        }
