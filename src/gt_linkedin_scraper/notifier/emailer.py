import logging
from pathlib import Path
from typing import List, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape
from gt_linkedin_scraper.core.config import settings

logger = logging.getLogger(__name__)

env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_report_html(keyword: str, tag: str, records_count: int, date: str) -> str:
    template = env.get_template("report.html.j2")
    return template.render(
        keyword=keyword,
        tag=tag,
        records_count=records_count,
        date=date,
        recipients=settings.all_recipients,
    )


def render_report_text(keyword: str, tag: str, records_count: int, date: str) -> str:
    return f"""LinkedIn Job Scraper Report
=============================
Keyword: {keyword}
Tag: {tag}
Date: {date}
Records Extracted: {records_count}
Recipients: {", ".join(settings.all_recipients)}
"""


class EmailNotifier:
    def __init__(
        self,
        host: str = settings.smtp_host,
        port: int = settings.smtp_port,
        username: str = settings.smtp_user,
        password: str = settings.smtp_password,
        sender: str = settings.smtp_from,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sender = sender

    def _get_recipients(self, tag: str) -> List[str]:
        recipients = list(settings.tag_recipients_map.get(tag, []))
        default = [e.strip() for e in settings.tag_recipients__default.split(",") if e.strip()]
        for d in default:
            if d not in recipients:
                recipients.append(d)
        return recipients

    async def send_with_attachments(
        self,
        subject: str,
        html_body: str,
        text_body: str,
        attachments: List[Path],
        recipients: Optional[List[str]] = None,
    ) -> None:
        if recipients is None:
            recipients = self._get_recipients("default")
        if not recipients:
            logger.warning("No recipients configured, skipping email")
            return

        message = MIMEMultipart("alternative")
        message["From"] = self.sender
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject

        message.attach(MIMEText(text_body, "plain", "utf-8"))
        message.attach(MIMEText(html_body, "html", "utf-8"))

        for attachment in attachments:
            if not attachment.exists():
                continue
            part = MIMEBase("application", "octet-stream")
            with open(attachment, "rb") as f:
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{attachment.name}"')
            message.attach(part)

        try:
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                start_tls=True,
                username=self.username,
                password=self.password,
            )
            logger.info("Email sent", extra={"recipients": recipients, "subject": subject})
        except Exception as exc:
            logger.error("Failed to send email", exc_info=exc)
            raise
