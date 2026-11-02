"""Background polling service for automatic Gmail email processing.

This service runs in the background and periodically fetches new emails
from Gmail, processes them through the classification and extraction pipeline,
and updates the database with new placement criteria.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from config import settings

# Configure logging
logger = logging.getLogger(__name__)


class GmailPollingService:
    """Background service for periodic Gmail email polling."""
    
    def __init__(
        self,
        polling_interval_minutes: int | None = None,
        api_base_url: str = "http://localhost:8000",
        enabled: bool | None = None,
    ):
        """Initialize Gmail polling service.
        
        Args:
            polling_interval_minutes: Polling interval in minutes (uses config if None)
            api_base_url: Base URL of the PlaceGuard API
            enabled: Whether polling is enabled (uses config if None)
        """
        self.polling_interval_minutes = (
            polling_interval_minutes or settings.gmail_polling_interval_minutes
        )
        self.api_base_url = api_base_url.rstrip("/")
        self.enabled = enabled if enabled is not None else settings.gmail_polling_enabled
        
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_poll_time: datetime | None = None
        self._last_poll_status: str = "not_started"
        self._total_polls = 0
        self._successful_polls = 0
        self._failed_polls = 0
        self._last_error: str | None = None
    
    async def start(self) -> None:
        """Start the background polling service.
        
        Creates an asyncio task that polls Gmail at the configured interval.
        """
        if not self.enabled:
            logger.info("Gmail polling is disabled in configuration")
            return
        
        if self._running:
            logger.warning("Gmail polling service is already running")
            return
        
        logger.info(
            f"Starting Gmail polling service "
            f"(interval: {self.polling_interval_minutes} minutes)"
        )
        
        self._running = True
        self._task = asyncio.create_task(self._polling_loop())
    
    async def stop(self) -> None:
        """Stop the background polling service gracefully.
        
        Cancels the polling task and waits for it to finish.
        """
        if not self._running:
            logger.warning("Gmail polling service is not running")
            return
        
        logger.info("Stopping Gmail polling service...")
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Gmail polling service stopped")
    
    async def _polling_loop(self) -> None:
        """Main polling loop that runs continuously in the background."""
        # Run first poll immediately (after short delay for startup)
        await asyncio.sleep(5)
        
        while self._running:
            try:
                await self._poll_and_process()
                self._successful_polls += 1
                self._last_poll_status = "success"
                self._last_error = None
                
            except Exception as e:
                self._failed_polls += 1
                self._last_poll_status = "error"
                self._last_error = str(e)
                logger.error(f"Gmail polling failed: {e}", exc_info=True)
            
            finally:
                self._last_poll_time = datetime.utcnow()
                self._total_polls += 1
            
            # Wait for next poll interval
            if self._running:
                await asyncio.sleep(self.polling_interval_minutes * 60)
    
    async def _poll_and_process(self) -> None:
        """Poll Gmail and process new emails.
        
        Makes an HTTP request to the sync-gmail endpoint.
        """
        logger.info("Polling Gmail for new emails...")
        
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.api_base_url}/ingest/sync-gmail",
                    params={"only_unread": True},
                )
                response.raise_for_status()
                
                result = response.json()
                
                logger.info(
                    f"Gmail sync completed: "
                    f"{result.get('emails_fetched', 0)} fetched, "
                    f"{result.get('emails_processed', 0)} processed, "
                    f"{result.get('emails_skipped', 0)} skipped, "
                    f"{result.get('facts_extracted', 0)} facts extracted"
                )
                
                if result.get('errors'):
                    logger.warning(f"Sync had errors: {result['errors']}")
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during Gmail sync: {e.response.status_code} - {e.response.text}")
            raise
        
        except httpx.RequestError as e:
            logger.error(f"Network error during Gmail sync: {e}")
            raise
        
        except Exception as e:
            logger.error(f"Unexpected error during Gmail sync: {e}")
            raise
    
    def get_status(self) -> dict[str, Any]:
        """Get current status of the polling service.
        
        Returns:
            Dict with service status information
        """
        return {
            "enabled": self.enabled,
            "running": self._running,
            "polling_interval_minutes": self.polling_interval_minutes,
            "last_poll_time": self._last_poll_time.isoformat() if self._last_poll_time else None,
            "last_poll_status": self._last_poll_status,
            "total_polls": self._total_polls,
            "successful_polls": self._successful_polls,
            "failed_polls": self._failed_polls,
            "last_error": self._last_error,
        }
    
    async def trigger_manual_poll(self) -> dict[str, Any]:
        """Manually trigger a poll immediately.
        
        This doesn't interfere with the scheduled polling.
        
        Returns:
            Dict with poll result
        """
        logger.info("Manual poll triggered")
        
        try:
            await self._poll_and_process()
            return {
                "success": True,
                "message": "Manual poll completed successfully",
                "timestamp": datetime.now(UTC).replace(tzinfo=None).isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Manual poll failed: {e}")
            return {
                "success": False,
                "message": f"Manual poll failed: {str(e)}",
                "timestamp": datetime.now(UTC).replace(tzinfo=None).isoformat(),
            }


# Global polling service instance
_polling_service: GmailPollingService | None = None


def get_polling_service() -> GmailPollingService:
    """Get the global polling service instance.
    
    Returns:
        GmailPollingService instance
    """
    global _polling_service
    
    if _polling_service is None:
        _polling_service = GmailPollingService()
    
    return _polling_service


async def start_polling_service() -> None:
    """Start the global polling service.
    
    Call this from FastAPI startup event.
    """
    service = get_polling_service()
    await service.start()


async def stop_polling_service() -> None:
    """Stop the global polling service.
    
    Call this from FastAPI shutdown event.
    """
    service = get_polling_service()
    await service.stop()
