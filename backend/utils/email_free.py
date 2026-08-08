"""Free Tier Email utility supporting Resend API with Gmail SMTP fallback."""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

try:
    import resend
    HAS_RESEND = True
except ImportError:
    HAS_RESEND = False

try:
    from backend.config import settings
except ImportError:
    from backend.config_free import free_settings as settings

logger = logging.getLogger(__name__)


async def send_email_free(to_email: str, subject: str, html_body: str) -> bool:
    """Send email via Resend API (3,000/mo free) or fallback to Gmail SMTP."""
    resend_key = getattr(settings, "RESEND_API_KEY", None)

    if HAS_RESEND and resend_key:
        try:
            resend.api_key = resend_key
            params = {
                "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>",
                "to": [to_email],
                "subject": subject,
                "html": html_body
            }
            email_res = resend.Emails.send(params)
            logger.info(f"Email sent via Resend API to {to_email}: {email_res}")
            return True
        except Exception as e:
            logger.error(f"Resend API failed ({e}). Attempting SMTP fallback...")

    return await _send_email_smtp_backup(to_email, subject, html_body)


async def _send_email_smtp_backup(to_email: str, subject: str, html_body: str) -> bool:
    """Gmail SMTP fallback mechanism."""
    user = getattr(settings, "EMAIL_USER", None)
    password = getattr(settings, "EMAIL_PASSWORD", None)

    if not user or not password:
        logger.warning(f"No valid SMTP credentials set. Email to {to_email} skipped.")
        return False

    try:
        host = getattr(settings, "EMAIL_HOST", "smtp.gmail.com")
        port = int(getattr(settings, "EMAIL_PORT", 587))

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.EMAIL_FROM_NAME} <{user}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

        logger.info(f"Backup SMTP email sent successfully to: {to_email}")
        return True
    except Exception as e:
        logger.error(f"Backup SMTP email failed: {e}")
        return False


async def send_verification_email(to_email: str, name: str, token: str) -> bool:
    """Send email verification link."""
    verify_url = f"{settings.FRONTEND_URL}/auth.html?verify={token}"
    html = f"""
    <h2>Welcome to Smart Community Platform, {name}!</h2>
    <p>Please verify your email address to activate your civic reporting account:</p>
    <p><a href="{verify_url}" style="background-color: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verify Email</a></p>
    <p>Or copy this link: {verify_url}</p>
    """
    return await send_email_free(to_email, "Verify Your Smart Community Email", html)


async def send_password_reset_email(to_email: str, name: str, token: str) -> bool:
    """Send password reset link."""
    reset_url = f"{settings.FRONTEND_URL}/auth.html?reset={token}"
    html = f"""
    <h2>Password Reset Request</h2>
    <p>Hello {name}, click below to reset your password:</p>
    <p><a href="{reset_url}" style="background-color: #ef4444; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
    """
    return await send_email_free(to_email, "Password Reset Request", html)


async def send_password_changed_email(to_email: str, name: str) -> bool:
    """Send confirmation when password changes."""
    html = f"<h2>Password Changed</h2><p>Hello {name}, your password has been successfully updated.</p>"
    return await send_email_free(to_email, "Security Alert: Password Changed", html)


async def send_issue_status_update_email(
    to_email: str,
    name: str,
    issue_title: str,
    issue_id: str,
    old_status: str,
    new_status: str,
    note: Optional[str] = None
) -> bool:
    """Send email update when an issue status changes."""
    issue_url = f"{settings.FRONTEND_URL}/issue.html?id={issue_id}"
    html = f"""
    <h2>Issue Status Update</h2>
    <p>Hello {name}, your reported issue <strong>"{issue_title}"</strong> has updated status:</p>
    <p>Status changed from <code>{old_status}</code> to <strong>{new_status}</strong>.</p>
    {f'<p><strong>Note:</strong> {note}</p>' if note else ''}
    <p><a href="{issue_url}">View Issue Details</a></p>
    """
    return await send_email_free(to_email, f"Issue Status Updated: {new_status}", html)


async def send_welcome_email(to_email: str, name: str, role: str) -> bool:
    """Send welcome email upon registration."""
    html = f"<h2>Welcome to Smart Community Platform!</h2><p>Hi {name}, thank you for joining as a <strong>{role}</strong>.</p>"
    return await send_email_free(to_email, "Welcome to Smart Community Platform", html)


async def send_volunteer_matched_email(to_email: str, name: str, issue_title: str, issue_id: str, location: str) -> bool:
    """Send notification when a volunteer is matched to a task."""
    issue_url = f"{settings.FRONTEND_URL}/issue.html?id={issue_id}"
    html = f"""
    <h2>New Volunteer Task Match</h2>
    <p>Hello {name}, you have been matched to help resolve: <strong>"{issue_title}"</strong> near {location}.</p>
    <p><a href="{issue_url}">View Task Details</a></p>
    """
    return await send_email_free(to_email, "New Community Volunteer Task Match", html)
