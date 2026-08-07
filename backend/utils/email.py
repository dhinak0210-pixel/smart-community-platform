"""Email utility module for Smart Community Platform.

Supports sending HTML and plain text email notifications with automatic retry logic
and fallback mock mode when SMTP credentials are not set in environment.
"""

import logging
import time
from typing import Optional
from backend.config import settings

logger = logging.getLogger(__name__)


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None
) -> bool:
    """Send an email using SMTP or fallback to console logging if unconfigured.

    Includes automatic 1-time retry on failure. Never raises exceptions.
    """
    if not settings.MAIL_USERNAME or not settings.MAIL_PASSWORD:
        logger.info(
            f"[EMAIL MOCK MODE]\nTo: {to_email}\nSubject: {subject}\n"
            f"HTML Snippet: {html_body[:200]}...\n"
        )
        return True

    text_content = text_body or "Please view this email in an HTML-compatible client."

    def _attempt_send() -> bool:
        try:
            import emails
            message = emails.html(
                html=html_body,
                text=text_content,
                subject=subject,
                mail_from=(getattr(settings, "MAIL_FROM_NAME", "Smart Community Platform"), settings.MAIL_FROM or "noreply@smartcommunity.com")
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
            if response.status_code == 250:
                logger.info(f"Email successfully sent to {to_email} with subject '{subject}'")
                return True
            else:
                logger.warning(f"SMTP returned status code {response.status_code} for {to_email}")
                return False
        except Exception as e:
            logger.error(f"Error attempting to send email to {to_email}: {e}")
            return False

    # First attempt
    if _attempt_send():
        return True

    # Retry once after 1 second delay
    logger.info(f"Retrying email dispatch to {to_email}...")
    time.sleep(1.0)
    return _attempt_send()


def send_verification_email(to_email: str, user_name: str, token: str) -> bool:
    """Send email verification link to newly registered user."""
    frontend_base = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    verify_url = f"{frontend_base}/verify-email/{token}"
    subject = f"Verify your email - {settings.APP_NAME}"
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; }}
            .card {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
            .btn {{ display: inline-block; background-color: #10B981; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 20px 0; }}
            .footer {{ font-size: 12px; color: #6b7280; margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Welcome to {settings.APP_NAME}, {user_name}!</h2>
            <p>Thank you for joining our community platform. Please verify your email address to complete your registration and activate full account features.</p>
            <p><a href="{verify_url}" class="btn">Verify Email Address</a></p>
            <p style="font-size: 13px; color: #4b5563;">Or copy and paste this link into your browser:<br><a href="{verify_url}">{verify_url}</a></p>
            <p><em>This verification link will expire in 24 hours.</em></p>
            <div class="footer">
                <p>If you did not create an account on {settings.APP_NAME}, please ignore this email.</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_body = f"Welcome {user_name}! Please verify your account by visiting: {verify_url}"
    return send_email(to_email=to_email, subject=subject, html_body=html_body, text_body=text_body)


def send_password_reset_email(to_email: str, user_name: str, token: str) -> bool:
    """Send password reset instructions with secure link."""
    frontend_base = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    reset_url = f"{frontend_base}/reset-password/{token}"
    subject = f"Password Reset Request - {settings.APP_NAME}"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; }}
            .card {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
            .btn {{ display: inline-block; background-color: #2563EB; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 20px 0; }}
            .warning {{ background-color: #FEF3C7; border-left: 4px solid #F59E0B; padding: 10px 15px; margin-top: 15px; font-size: 13px; color: #92400E; }}
            .footer {{ font-size: 12px; color: #6b7280; margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Hello {user_name},</h2>
            <p>We received a request to reset the password for your {settings.APP_NAME} account.</p>
            <p><a href="{reset_url}" class="btn">Reset Password</a></p>
            <p style="font-size: 13px; color: #4b5563;">Or copy and paste this link into your browser:<br><a href="{reset_url}">{reset_url}</a></p>
            <div class="warning">
                <strong>Important:</strong> This reset link is valid for 1 hour. If you did not request a password reset, please ignore this email and your password will remain unchanged.
            </div>
            <div class="footer">
                <p>Security Notification - {settings.APP_NAME}</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_body = f"Hello {user_name}, reset your password using the following link: {reset_url} (valid for 1 hour)."
    return send_email(to_email=to_email, subject=subject, html_body=html_body, text_body=text_body)


def send_password_changed_email(to_email: str, user_name: str) -> bool:
    """Send security alert notification after password change."""
    subject = f"Security Alert: Password Changed - {settings.APP_NAME}"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; }}
            .card {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
            .footer {{ font-size: 12px; color: #6b7280; margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Password Changed Successfully</h2>
            <p>Hello {user_name},</p>
            <p>This is confirmation that the password for your account <strong>{to_email}</strong> was updated.</p>
            <p>If you made this change, no further action is required.</p>
            <p style="color: #DC2626;"><strong>If you did not request this change, please contact community support immediately to secure your account.</strong></p>
            <div class="footer">
                <p>{settings.APP_NAME} Security Team</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_body = f"Hello {user_name}, your password was changed. If you did not perform this change, contact support immediately."
    return send_email(to_email=to_email, subject=subject, html_body=html_body, text_body=text_body)


def send_issue_status_update_email(
    to_email: str,
    user_name: str,
    issue_title: str,
    issue_uuid: str,
    old_status: str,
    new_status: str,
    status_note: Optional[str] = None
) -> bool:
    """Notify citizen when an authority updates an issue's status."""
    frontend_base = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    issue_url = f"{frontend_base}/issues/{issue_uuid}"
    subject = f"Issue Update: '{issue_title}' status changed to {new_status.replace('_', ' ').title()}"

    note_block = f"<p><strong>Authority Note:</strong> <em>{status_note}</em></p>" if status_note else ""

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; }}
            .card {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
            .status-badge {{ display: inline-block; background-color: #DBEAFE; color: #1E40AF; padding: 6px 12px; border-radius: 12px; font-size: 14px; font-weight: bold; }}
            .btn {{ display: inline-block; background-color: #3B82F6; color: #ffffff; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Status Update on Your Report</h2>
            <p>Hello {user_name},</p>
            <p>The status of your reported issue <strong>"{issue_title}"</strong> has been updated:</p>
            <p><span class="status-badge">{old_status.upper()} &rarr; {new_status.upper()}</span></p>
            {note_block}
            <p><a href="{issue_url}" class="btn">View Issue Details</a></p>
        </div>
    </body>
    </html>
    """

    text_body = f"Hello {user_name}, status for '{issue_title}' changed from {old_status} to {new_status}. View at: {issue_url}"
    return send_email(to_email=to_email, subject=subject, html_body=html_body, text_body=text_body)


def send_welcome_email(to_email: str, user_name: str, role: str) -> bool:
    """Send welcome onboarding email after successful account verification."""
    frontend_base = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    explore_url = f"{frontend_base}/dashboard"
    subject = f"Welcome to the {settings.APP_NAME} Community!"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; }}
            .card {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
            .btn {{ display: inline-block; background-color: #10B981; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Your account is verified!</h2>
            <p>Hello {user_name},</p>
            <p>Thank you for verifying your email. You are registered as a <strong>{role.title()}</strong> on {settings.APP_NAME}.</p>
            <h3>Quick Start Guide:</h3>
            <ol>
                <li>Report local civic issues (potholes, lighting, waste, etc.).</li>
                <li>Vote and comment on issues in your neighborhood.</li>
                <li>Track resolution progress live on the interactive map.</li>
            </ol>
            <p><a href="{explore_url}" class="btn">Explore Platform Dashboard</a></p>
        </div>
    </body>
    </html>
    """

    text_body = f"Hello {user_name}, your account as {role} is verified! Explore the dashboard: {explore_url}"
    return send_email(to_email=to_email, subject=subject, html_body=html_body, text_body=text_body)


def send_volunteer_matched_email(
    to_email: str,
    volunteer_name: str,
    issue_title: str,
    issue_uuid: str,
    issue_location: str
) -> bool:
    """Notify volunteer when AI agent matches them to a community task."""
    frontend_base = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    issue_url = f"{frontend_base}/volunteers/assignments/{issue_uuid}"
    subject = f"New Volunteer Assignment: '{issue_title}'"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; }}
            .card {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
            .btn {{ display: inline-block; background-color: #8B5CF6; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>You've Been Matched to an Issue!</h2>
            <p>Hello {volunteer_name},</p>
            <p>Based on your skills and location, you have been matched to help resolve:</p>
            <p><strong>{issue_title}</strong><br><em>Location: {issue_location}</em></p>
            <p><a href="{issue_url}" class="btn">View Assignment & Accept</a></p>
        </div>
    </body>
    </html>
    """

    text_body = f"Hello {volunteer_name}, you have been matched to issue '{issue_title}' at {issue_location}. View at: {issue_url}"
    return send_email(to_email=to_email, subject=subject, html_body=html_body, text_body=text_body)

