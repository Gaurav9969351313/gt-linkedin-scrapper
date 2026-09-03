import asyncio
import random
import logging
from typing import Optional

from playwright.async_api import BrowserContext, Page

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, min_delay: float = 2.0, max_delay: float = 8.0, max_concurrency: int = 3):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._global_semaphore = asyncio.Semaphore(max_concurrency)

    async def acquire(self) -> None:
        await self._global_semaphore.acquire()

    def release(self) -> None:
        self._global_semaphore.release()

    async def wait(self) -> None:
        delay = random.uniform(self.min_delay, self.max_delay)
        logger.debug("Rate limiter sleep", extra={"delay": delay})
        await asyncio.sleep(delay)
