import logging
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

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

    def _get_recipients(self, tag: str) -> list[str]:
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
        attachments: list[Path],
        recipient: str,
        sender: str | None = None,
    ) -> None:
        from_addr = sender or self.sender

        message = MIMEMultipart("alternative")
        message["From"] = from_addr
        message["To"] = recipient
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
            logger.debug(f"Email sent from {from_addr} to {recipient}: {subject}")
        except Exception as exc:
            logger.debug(f"Failed to send email from {from_addr} to {recipient}: {exc}", exc_info=True)
            raise
