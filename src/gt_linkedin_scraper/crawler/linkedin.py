import asyncio
import logging
import random
import time
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, BrowserContext, Page, Browser, Playwright

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.core.exceptions import LoginFailed, LinkedInCheckpointError

try:
    from playwright_stealth.stealth import Stealth
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False

logger = logging.getLogger(__name__)

DEBUG_DIR = Path("debug")
DEBUG_DIR.mkdir(exist_ok=True)

LOGIN_URLS = [
    "https://www.linkedin.com/login",
    "https://www.linkedin.com/checkpoint/lg/sign-in-another-account",
    "https://www.linkedin.com/signup",
]

USERNAME_SELECTORS = [
    "input[type='email']",
    "#username",
    "input[name='session_key']",
    "input[id='session_key']",
]

PASSWORD_SELECTORS = [
    "input[type='password']",
    "#password",
    "input[name='session_password']",
    "input[id='session_password']",
]

SUBMIT_SELECTORS = [
    "button[data-litms-control-urn='login-submit']",
    "button[type='button']:has-text('Sign in')",
    "button[type='submit']",
    "button:has-text('Sign in')",
]


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
        context = await self._browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="Asia/Kolkata",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )
        if STEALTH_AVAILABLE:
            await Stealth().apply_stealth_async(context)
        return context

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


class LinkedInCrawler:
    def __init__(self, context: BrowserContext) -> None:
        self.context = context
        self.auth_path = settings.auth_state_path

    async def ensure_login(self, page: Page) -> None:
        from pathlib import Path
        import json

        auth_path = Path(self.auth_path)
        auth_path.parent.mkdir(parents=True, exist_ok=True)

        if auth_path.exists():
            try:
                with open(auth_path, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                await self.context.add_cookies(cookies)
                await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                if "login" not in page.url:
                    logger.info("Session restored from auth state")
                    return
            except Exception as exc:
                logger.warning("Auth state load failed, will re-login", exc_info=exc)

        await self._perform_login(page)
        await self._persist_auth()

    async def _perform_login(self, page: Page) -> None:
        import socket

        username = settings.linkedin_username
        password = settings.linkedin_password
        if not username or not password:
            raise LoginFailed("LinkedIn credentials not configured")

        try:
            socket.gethostbyname("www.linkedin.com")
        except Exception as exc:
            raise LoginFailed(f"DNS resolution failed for LinkedIn: {exc}") from exc

        logger.info("Navigating to LinkedIn login")
        start = time.time()
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        logger.debug(f"Login page loaded in {time.time() - start:.2f}s")
        await page.wait_for_timeout(10000)

        for attempt in range(1, 4):
            try:
                logger.info(f"Login attempt {attempt}/3")
                await self._save_screenshot(page, f"login-attempt-{attempt}-before.png")

                username_sel = await self._first_visible_selector(page, USERNAME_SELECTORS, timeout=1000)
                if not username_sel:
                    raise RuntimeError("Username field not found")

                password_sel = await self._first_visible_selector(page, PASSWORD_SELECTORS, timeout=1000)
                if not password_sel:
                    raise RuntimeError("Password field not found")

                await page.fill(username_sel, username, timeout=5000)
                await page.wait_for_timeout(random.randint(200, 500))
                await page.fill(password_sel, password, timeout=5000)
                await page.wait_for_timeout(random.randint(200, 500))

                submit_sel = await self._first_visible_selector(page, SUBMIT_SELECTORS, timeout=5000)
                if not submit_sel:
                    raise RuntimeError("Submit button not found")
                await page.click(submit_sel)
                await page.wait_for_timeout(4000)

                if "/checkpoint" in page.url:
                    raise LinkedInCheckpointError("LinkedIn checkpoint detected — manual intervention required")

                logger.info("Login successful")
                return
            except Exception as exc:
                logger.warning(f"Login attempt {attempt} failed: {exc}", exc_info=True)
                await self._save_screenshot(page, f"login-attempt-{attempt}-failed.png")
                if attempt == 3:
                    raise
                await page.wait_for_timeout(2000)

    async def _save_screenshot(self, page: Page, filename: str) -> None:
        try:
            path = DEBUG_DIR / filename
            await page.screenshot(path=path, full_page=False)
            logger.info(f"Screenshot saved", extra={"path": str(path)})
        except Exception as exc:
            logger.warning(f"Screenshot failed: {exc}")

    async def _first_visible_selector(self, page: Page, selectors, timeout: int = 60000) -> Optional[str]:
        for selector in selectors:
            try:
                locator = page.locator(selector)
                count = await locator.count()
                for i in range(count):
                    elem = locator.nth(i)
                    try:
                        await elem.wait_for(state="visible", timeout=timeout)
                        if await elem.is_visible():
                            text = await elem.text_content()
                            if text and any(sso in text for sso in ["Microsoft", "Apple"]):
                                continue
                            return f"{selector} >> nth={i}"
                    except Exception:
                        continue
            except Exception:
                continue
        return None

    async def _persist_auth(self) -> None:
        import json
        from pathlib import Path

        auth_path = Path(self.auth_path)
        cookies = await self.context.cookies()
        with open(auth_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)
        logger.info("Auth state saved", extra={"path": str(auth_path)})

    async def navigate_to_search(self, page: Page, keyword: str) -> None:
        url = f"https://www.linkedin.com/search/results/content/?datePosted=past-24h&keywords={keyword}&origin=FACETED_SEARCH&sortBy=date_posted"
        logger.info("Navigating to search", extra={"keyword": keyword})
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        if "/checkpoint" in page.url:
            raise LinkedInCheckpointError("LinkedIn checkpoint detected on search")

    async def scroll_and_collect(self, page: Page, scroll_count: int) -> str:
        html_parts = []
        for i in range(1, scroll_count + 1):
            await page.evaluate("(() => { const els = [document.documentElement, document.body, ...document.querySelectorAll('*')]; els.forEach(el => { if (el.scrollHeight > el.clientHeight + 100) { el.scrollTop += 6000; } }); })();")
            await page.wait_for_timeout(4000)
            html_parts.append(await page.content())
            logger.debug(f"Scroll iteration: {i}")
        return "".join(html_parts)
