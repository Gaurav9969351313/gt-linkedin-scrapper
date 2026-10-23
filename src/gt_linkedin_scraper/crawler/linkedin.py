import asyncio
import json
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from playwright.async_api import BrowserContext, Page

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.core.exceptions import LinkedInCheckpointError, LoginFailed

logger = logging.getLogger(__name__)

DEBUG_DIR = Path(settings.debug_dir)
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
MAX_DEBUG_FILES = 40

LINKEDIN = "https://www.linkedin.com"
LOGIN_URL = f"{LINKEDIN}/login"
FEED_URL = f"{LINKEDIN}/feed/"


def visible_only(*selectors: str) -> str:
    # LinkedIn renders some forms twice (one copy hidden); only match what a person can see.
    return ", ".join(f"{s}:visible" for s in selectors)


# Matched by meaning, not by id: LinkedIn's newer login page uses random generated ids
# (e.g. "_R_e3ppriejj35656j6_") and no name attributes, but keeps the input types.
USERNAME_FIELD = visible_only(
    "#username", "input[name='session_key']", "input[type='email']", "input[autocomplete='username']"
)
PASSWORD_FIELD = visible_only("#password", "input[name='session_password']", "input[type='password']")
# Older page: a submit button. Newer page: a type="button" whose label is exactly "Sign in",
# usually nested in spans (<button><span><span>Sign in</span></span></button>). Exact match,
# so "Sign in with Apple" and "Sign in using another account" don't count.
SUBMIT_BUTTON = visible_only(
    "button[type='submit']",
    "button[data-litms-control-urn='login-submit']",
    "button:text-is('Sign in')",
    "button:has(:text-is('Sign in'))",
)
# Shown on the "Welcome back" (remembered account) and account-chooser pages.
OTHER_ACCOUNT = "text=/sign in using another account/i"
LOGIN_ERRORS = "#error-for-username, #error-for-password, .form__label--error, [role='alert']"
CAPTCHA = "iframe[src*='captcha'], #captcha-internal, iframe[title*='captcha' i]"

LOGGED_OUT_MARKERS = ("/login", "/uas/", "/checkpoint", "/authwall", "/signup")
LOGIN_TIMEOUT_MS = 30_000


def is_logged_in_url(url: str) -> bool:
    return url.startswith(LINKEDIN) and not any(m in url for m in LOGGED_OUT_MARKERS)


def is_challenge_url(url: str) -> bool:
    """Security verification (captcha, emailed/SMS code, 2FA): needs a human."""
    return "/checkpoint/challenge" in url or "/checkpoint/pin" in url


def masked_email_matches(hint: str, email: str) -> bool:
    """LinkedIn shows a remembered account as e.g. 'g*****@gmail.com'."""
    m = re.match(r"^(\w)\*+@(.+)$", hint.strip().lower())
    if not m or "@" not in email:
        return False
    local, domain = email.strip().lower().split("@", 1)
    return local[:1] == m.group(1) and domain == m.group(2)


class LinkedInCrawler:
    def __init__(self, context: BrowserContext) -> None:
        self.context = context
        self.auth_path = Path(settings.auth_state_path)

    # ---------- session ----------

    async def ensure_login(self, page: Page) -> None:
        if await self._restore_session(page):
            return
        # Expired session cookies make LinkedIn show a "Welcome back" page for whichever
        # account they belong to. Start clean so the normal email + password form appears.
        await self.context.clear_cookies()
        await self._perform_login(page)
        await self._persist_auth()

    async def _restore_session(self, page: Page) -> bool:
        if not self.auth_path.exists():
            logger.info("No saved LinkedIn session yet; logging in with the configured account")
            return False
        logger.info(f"Trying the saved LinkedIn session from {self.auth_path}")
        try:
            cookies = json.loads(self.auth_path.read_text(encoding="utf-8"))
            await self.context.add_cookies(cookies)
            await page.goto(FEED_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
        except Exception as exc:
            logger.warning("Saved session could not be loaded; logging in again", exc_info=exc)
            return False
        if is_logged_in_url(page.url):
            logger.info("Session restored from auth state")
            return True
        if is_challenge_url(page.url):
            await self._save_debug(page, "session-challenge")
            raise LinkedInCheckpointError(CHALLENGE_MESSAGE)
        logger.info(f"Saved session has expired (LinkedIn redirected to {page.url}); logging in again")
        return False

    async def _persist_auth(self) -> None:
        self.auth_path.parent.mkdir(parents=True, exist_ok=True)
        self.auth_path.write_text(json.dumps(await self.context.cookies(), indent=2), encoding="utf-8")
        logger.info(f"Logged-in session saved to {self.auth_path}; later runs will reuse it")

    # ---------- login ----------

    async def _perform_login(self, page: Page) -> None:
        username = settings.linkedin_username
        password = settings.linkedin_password
        if not username or not password:
            raise LoginFailed("LinkedIn credentials not configured (LINKEDIN_USERNAME / LINKEDIN_PASSWORD)")

        for attempt in range(1, 4):
            logger.info(f"Login attempt {attempt}/3: opening {LOGIN_URL}")
            start = time.time()
            await page.goto(LOGIN_URL, wait_until="domcontentloaded")
            variant = await self._wait_for_login_page(page)
            logger.info(f"Login page ready ({variant}) in {time.time() - start:.1f}s")

            if variant == "logged_in":
                logger.info("Already logged in")
                return
            if variant == "challenge":
                await self._save_debug(page, f"login-{attempt}-challenge")
                raise LinkedInCheckpointError(CHALLENGE_MESSAGE)
            if variant == "unknown":
                await self._save_debug(page, f"login-{attempt}-unrecognised-page")
                await self._backoff(attempt)
                continue

            if variant == "chooser" or (
                variant == "remembered" and not await self._remembered_account_matches(page, username)
            ):
                variant = await self._switch_to_other_account(page)

            if variant == "form":
                await self._type(page, USERNAME_FIELD, username)
            await self._type(page, PASSWORD_FIELD, password)
            logger.info("Credentials entered; submitting the sign-in form")
            await page.locator(SUBMIT_BUTTON).first.click()

            outcome, detail = await self._wait_for_login_outcome(page)
            if outcome == "success":
                logger.info("Login successful")
                return
            await self._save_debug(page, f"login-{attempt}-{outcome}")
            if outcome == "challenge":
                raise LinkedInCheckpointError(CHALLENGE_MESSAGE)
            if outcome == "rejected":
                # Never retry a rejected password: repeated failures get the account locked.
                raise LoginFailed(f"LinkedIn rejected the login: {detail or 'wrong email or password'}")
            await self._backoff(attempt)

        raise LoginFailed(f"Could not log in to LinkedIn after 3 attempts; see the screenshots and HTML in {DEBUG_DIR}")

    async def _wait_for_login_page(self, page: Page) -> str:
        """Waits for the login page to render and says which variant it is:
        form | remembered | chooser | logged_in | challenge | unknown."""
        deadline = time.monotonic() + LOGIN_TIMEOUT_MS / 1000
        while time.monotonic() < deadline:
            if is_logged_in_url(page.url):
                return "logged_in"
            if is_challenge_url(page.url) or await self._visible(page, CAPTCHA):
                return "challenge"
            has_user = await self._visible(page, USERNAME_FIELD)
            has_pass = await self._visible(page, PASSWORD_FIELD)
            if has_user and has_pass:
                return "form"
            if has_pass:
                return "remembered"  # "Welcome back": account pre-selected, password only
            if await self._visible(page, OTHER_ACCOUNT):
                return "chooser"
            await page.wait_for_timeout(500)
        return "unknown"

    async def _remembered_account_matches(self, page: Page, username: str) -> bool:
        body = await page.inner_text("body")
        hints = re.findall(r"\b\w\*{2,}@[\w.-]+\.\w+", body)
        if any(masked_email_matches(h, username) for h in hints):
            return True
        logger.info("LinkedIn remembered a different account; switching to the configured one")
        return False

    async def _switch_to_other_account(self, page: Page) -> str:
        await page.locator(OTHER_ACCOUNT).first.click()
        await page.locator(USERNAME_FIELD).first.wait_for(state="visible", timeout=LOGIN_TIMEOUT_MS)
        return "form"

    async def _wait_for_login_outcome(self, page: Page) -> tuple[str, Optional[str]]:
        """success | challenge | rejected | timeout, plus LinkedIn's error text if any."""
        deadline = time.monotonic() + LOGIN_TIMEOUT_MS / 1000
        while time.monotonic() < deadline:
            await page.wait_for_timeout(500)
            if is_challenge_url(page.url) or await self._visible(page, CAPTCHA):
                return "challenge", None
            if is_logged_in_url(page.url):
                return "success", None
            errors = page.locator(LOGIN_ERRORS)
            for i in range(await errors.count()):
                error = errors.nth(i)
                text = (await error.inner_text()).strip()
                if text and await error.is_visible():
                    return "rejected", text
        return "timeout", None

    # ---------- helpers ----------

    @staticmethod
    async def _visible(page: Page, selector: str) -> bool:
        try:
            return await page.locator(selector).first.is_visible()
        except Exception:
            return False

    @staticmethod
    async def _type(page: Page, selector: str, value: str) -> None:
        await page.locator(selector).first.fill(value, timeout=10_000)
        await page.wait_for_timeout(random.randint(200, 500))

    @staticmethod
    async def _backoff(attempt: int) -> None:
        await asyncio.sleep(5 * attempt + random.uniform(0, 3))

    async def _save_debug(self, page: Page, label: str) -> None:
        """Screenshot + HTML of the current page, for diagnosing login problems."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        try:
            await page.screenshot(path=DEBUG_DIR / f"{stamp}-{label}.png", full_page=False)
            (DEBUG_DIR / f"{stamp}-{label}.html").write_text(await page.content(), encoding="utf-8")
            logger.info(f"Saved a screenshot and the HTML of {page.url} to {DEBUG_DIR}/{stamp}-{label}.png/.html")
        except Exception as exc:
            logger.warning(f"Could not save debug files: {exc}")
        files = sorted((f for f in DEBUG_DIR.iterdir() if f.is_file()), key=lambda f: f.stat().st_mtime)
        for old in files[:-MAX_DEBUG_FILES]:
            old.unlink(missing_ok=True)

    # ---------- scraping ----------

    async def navigate_to_search(self, page: Page, keyword: str) -> None:
        url = f"https://www.linkedin.com/search/results/content/?datePosted=past-24h&keywords={keyword}&origin=FACETED_SEARCH&sortBy=date_posted"
        logger.info(f"Opening search results for: {keyword}")
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        if "/checkpoint" in page.url:
            await self._save_debug(page, "search-checkpoint")
            raise LinkedInCheckpointError(CHALLENGE_MESSAGE)
        if not is_logged_in_url(page.url):
            await self._save_debug(page, "search-logged-out")
            raise LoginFailed(f"LinkedIn sent the search to {page.url} instead of the results; the session was not accepted")
        logger.info(f"Search results page loaded: {page.url}")

    async def scroll_and_collect(
        self, page: Page, scroll_count: int, progress: Optional[Callable[[str], None]] = None
    ) -> str:
        """Scrolls the results `scroll_count` times and returns the collected HTML.
        `progress` receives one line per scroll (used for the Prefect run log)."""
        from gt_linkedin_scraper.crawler.parser import Parser

        report = progress or logger.info
        html_parts = []
        for i in range(1, scroll_count + 1):
            await page.evaluate("(() => { const els = [document.documentElement, document.body, ...document.querySelectorAll('*')]; els.forEach(el => { if (el.scrollHeight > el.clientHeight + 100) { el.scrollTop += 6000; } }); })();")
            await page.wait_for_timeout(4000)
            content = await page.content()
            html_parts.append(content)
            emails_so_far = len(set(Parser.extract_emails(content)))
            report(f"Scroll {i}/{scroll_count}: page is {len(content) // 1024} KB, {emails_so_far} unique email(s) visible so far")
        return "".join(html_parts)


CHALLENGE_MESSAGE = (
    "LinkedIn is asking for a security verification (captcha, emailed code or 2FA). "
    "Sign in to this LinkedIn account in a normal browser, complete the check, then run the job again."
)
