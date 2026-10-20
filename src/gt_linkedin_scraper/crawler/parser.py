import re
import csv
import random
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Optional

from gt_linkedin_scraper.core.config import settings
from gt_linkedin_scraper.core.exceptions import ParseError

logger = logging.getLogger(__name__)

POST_SELECTORS = [
    'div._9cf78d2b',
    'div._23fb2414',
    'div[data-testid="lazy-column"]',
    'div._6c1f1fa0',
]

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@(?![0-9]x\.png)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')


class RateLimiter:
    def __init__(self, min_delay: float = 2.0, max_delay: float = 8.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._global_semaphore = asyncio.Semaphore(3)

    async def wait(self) -> None:
        delay = random.uniform(self.min_delay, self.max_delay)
        logger.debug("Rate limiter sleep", extra={"delay": delay})
        await asyncio.sleep(delay)

    async def acquire(self) -> None:
        await self._global_semaphore.acquire()

    def release(self) -> None:
        self._global_semaphore.release()


class Parser:
    @staticmethod
    def extract_emails(html: str) -> list[str]:
        if not html:
            logger.debug("No HTML provided for email extraction")
            return []
        found = EMAIL_REGEX.findall(html)
        logger.debug(f"Email regex found {len(found)} emails", extra={"emails": found[:10]})
        return list(dict.fromkeys(found))

    @staticmethod
    def split_posts(html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        for selector in POST_SELECTORS:
            posts = soup.select(selector)
            if posts:
                return [str(post) for post in posts]
        return []

    @staticmethod
    def extract_posts(html: str, job_id: int) -> list[dict]:
        if not html:
            logger.debug("No HTML provided for post extraction")
            return []
        try:
            soup = BeautifulSoup(html, "html.parser")
            posts = []
            for selector in POST_SELECTORS:
                posts = soup.select(selector)
                if posts:
                    logger.debug(f"Found {len(posts)} posts using selector: {selector}")
                    break

            if not posts:
                logger.debug("No posts found with current selectors, saving HTML for inspection")
                extract_dir = Path("extract")
                extract_dir.mkdir(exist_ok=True)
                html_path = extract_dir / f"search-result-{job_id}.html"
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html)
                logger.debug(f"HTML saved to {html_path}", extra={"path": str(html_path)})
                return []

            results = []
            for post in posts:
                content_el = post.select_one('div[data-testid="expandable-text-box"]')
                content = content_el.get_text(separator=" ", strip=True) if content_el else post.get_text(separator=" ", strip=True)
                username = "N/A"
                skip_texts = {"Feed post", "Follow", "more", "Show translation"}
                for span in post.find_all("span"):
                    span_text = span.get_text(strip=True)
                    if span_text and len(span_text.split()) <= 6 and span.get("dir") == "ltr" and span_text not in skip_texts:
                        username = span_text
                        break
                post_emails = Parser.extract_emails(content)
                results.append({
                    "job_id": job_id,
                    "username": username,
                    "content": content,
                    "emails_found": ", ".join(post_emails)[:512],
                })
            logger.debug(f"Extracted {len(results)} posts", extra={"posts": results[:3]})
            return results
        except Exception as exc:
            logger.error("Parse error", exc_info=exc)
            raise ParseError("Failed to parse posts") from exc

    @staticmethod
    def write_csvs(records: list[dict], keyword: str, tag: str, extract_dir: Path) -> tuple[Path, int]:
        today = datetime.now().strftime("%d-%m-%Y")
        out_dir = extract_dir / today
        out_dir.mkdir(parents=True, exist_ok=True)

        safe_keyword = keyword.replace(" ", "_").replace('"', "")
        emails_file = out_dir / f"{safe_keyword}_emails.csv"
        posts_file = out_dir / f"post_details_{safe_keyword}.csv"

        emails_seen = set()
        email_rows = [["Email", "Tag"]]
        post_rows = [["Username", "Email", "Post Content"]]

        for rec in records:
            email_list = [e.strip() for e in rec.get("emails_found", "").split(",") if e.strip()]
            for email in email_list:
                if email not in emails_seen:
                    emails_seen.add(email)
                    email_rows.append([email, tag])
            post_rows.append([
                rec.get("username", "N/A"),
                rec.get("emails_found", ""),
                rec.get("content", "N/A"),
            ])

        with open(emails_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(email_rows)

        with open(posts_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(post_rows)

        logger.info("CSV files written", extra={"emails_file": str(emails_file), "posts_file": str(posts_file)})
        return emails_file, len(emails_seen)
