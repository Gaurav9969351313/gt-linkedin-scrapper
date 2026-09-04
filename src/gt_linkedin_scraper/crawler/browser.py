import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, BrowserContext, Page, Browser, Playwright

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.core.exceptions import LoginFailed, LinkedInCheckpointError

logger = logging.getLogger(__name__)


def _find_chromium_executable() -> Optional[str]:
    executable_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if executable_path and Path(executable_path).exists():
        return executable_path

    chromium_root = Path.home() / ".cache" / "ms-playwright"
    if not chromium_root.exists():
        return None

    for entry in chromium_root.iterdir():
        if not entry.is_dir():
            continue
        name = entry.name
        if not name.startswith("chromium-"):
            continue
        if "headless" in name:
            continue
        chrome_bin = entry / "chrome-linux64" / "chrome"
        if chrome_bin.exists():
            return str(chrome_bin)

    return None


class BrowserPool:
    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        executable_path = _find_chromium_executable()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            executable_path=executable_path,
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
