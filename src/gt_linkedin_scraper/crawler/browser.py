import asyncio
import logging
from typing import Optional
from playwright.async_api import async_playwright, BrowserContext, Page, Browser, Playwright

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.core.exceptions import LoginFailed, LinkedInCheckpointError

logger = logging.getLogger(__name__)


class BrowserPool:
    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )

    async def new_context(self) -> BrowserContext:
        if self._browser is None:
            await self.start()
        return await self._browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="Asia/Kolkata",
        )

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
