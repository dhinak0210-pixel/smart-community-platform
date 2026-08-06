"""Email notification utility using SMTP."""

import logging
from typing import Optional
from backend.config import settings

logger = logging.getLogger(__name__)


def send_email_notification(to_email: str, subject: str, body: str) -> bool:
    """Send an automated email notification to a user.

    If SMTP credentials are not configured in settings, logs message to console.
    """
    if not settings.MAIL_USERNAME or not settings.MAIL_PASSWORD:
        logger.info(
            f"[EMAIL MOCK] To: {to_email} | Subject: '{subject}'\nBody: {body}"
        )
        return True

    try:
        import emails
        message = emails.html(
            html=f"<p>{body}</p>",
            subject=subject,
            mail_from=(settings.APP_NAME, settings.MAIL_FROM)
        )
        response = message.send(
            to=to_email,
            smtp={
                "host": settings.MAIL_SERVER,
                "port": settings.MAIL_PORT,
                "ssl": settings.MAIL_SSL_TLS,
                "tls": settings.MAIL_STARTTLS,
                "user": settings.MAIL_USERNAME,
                "password": settings.MAIL_PASSWORD,
            }
        )
        logger.info(f"Email sent successfully to {to_email}: {response.status_code}")
        return response.status_code == 250
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False
