"""Best-effort transactional email for the web app, using the project SMTP settings."""
import html
import logging
import smtplib
from email.message import EmailMessage

from gt_linkedin_scraper.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to: list[str], subject: str, text: str) -> bool:
    """Returns False instead of raising, so callers can fall back (e.g. a copyable invite link)."""
    recipients = [r for r in to if r]
    if not settings.smtp_host or not settings.smtp_user or not recipients:
        logger.warning("SMTP not configured or no recipients; email '%s' not sent", subject)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = ", ".join(recipients)
    msg.set_content(text)
    msg.add_alternative(
        "<div style=\"font-family:Arial,sans-serif;font-size:14px;line-height:1.5\">"
        + html.escape(text).replace("\n", "<br>")
        + "</div>",
        subtype="html",
    )

    try:
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                smtp.starttls()
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send email '%s'", subject)
        return False
