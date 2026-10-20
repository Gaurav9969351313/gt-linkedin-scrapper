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


def report_category(tag: str) -> str:
    return tag.replace("_", " ").title()


def report_subject(tag: str, email_count: int) -> str:
    return f"{report_category(tag)} Jobs - {email_count} Email{'s' if email_count != 1 else ''}"


def render_report_html(keyword: str, tag: str, email_count: int, date: str, attachment_name: str) -> str:
    template = env.get_template("report.html.j2")
    return template.render(
        category=report_category(tag),
        keyword=keyword,
        tag=tag,
        email_count=email_count,
        date=date,
        attachment_name=attachment_name,
    )


def render_report_text(keyword: str, tag: str, email_count: int, date: str, attachment_name: str) -> str:
    return f"""Hello,

Today's LinkedIn search for {report_category(tag)} openings found {email_count} unique recruiter / hiring contact email(s).
The full list is attached as a CSV file (columns: Email, Tag).

Search keyword: {keyword}
Tag: {tag}
Date: {date}
Emails found: {email_count}
Attachment: {attachment_name}

Regards,
LinkedIn Job Scraper

This is an automated message. Please do not reply to this email.
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

        message = MIMEMultipart("mixed")
        message["From"] = from_addr
        message["To"] = recipient
        message["Subject"] = subject

        body = MIMEMultipart("alternative")
        body.attach(MIMEText(text_body, "plain", "utf-8"))
        body.attach(MIMEText(html_body, "html", "utf-8"))
        message.attach(body)

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
            logger.info(
                "Email sent",
                extra={"from": from_addr, "to": recipient, "subject": subject},
            )
        except Exception as exc:
            logger.error(
                "Failed to send email",
                extra={
                    "from": from_addr,
                    "to": recipient,
                    "subject": subject,
                    "error": str(exc),
                },
                exc_info=True,
            )
            raise
