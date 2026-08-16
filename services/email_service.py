"""
Outbound transactional email via Brevo SMTP relay.

Sending is best-effort: any failure (missing config, network, auth) is
logged and swallowed so it never blocks the caller's request flow.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp-relay.brevo.com"
SMTP_PORT = 587


def send_email(to: str, subject: str, html_body: str) -> bool:
    login = os.getenv("SMTP_LOGIN")
    password = os.getenv("SMTP_BREVO")
    from_addr = os.getenv("SMTP_FROM") or login

    if not login or not password or not to:
        logger.warning("Email not sent to %s: SMTP_LOGIN/SMTP_BREVO not configured.", to)
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = from_addr
    message["To"] = to
    message.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(login, password)
            server.sendmail(from_addr, [to], message.as_string())
        return True
    except Exception as exc:
        logger.warning("Email send to %s failed: %s", to, exc)
        return False


def send_visit_scheduled_emails(visit: dict, spot: dict) -> None:
    from services.visit_schedules import get_spot_owner_email

    spot_name = spot.get("name") or "the destination"
    visit_summary = (
        f"<p><strong>Spot:</strong> {spot_name}</p>"
        f"<p><strong>Date:</strong> {visit.get('visit_date')} at {visit.get('visit_time')}</p>"
        f"<p><strong>Party size:</strong> {visit.get('party_size')}</p>"
    )

    visitor_email = visit.get("visitor_email")
    if visitor_email:
        send_email(
            visitor_email,
            f"Your visit request to {spot_name} is pending confirmation",
            "<p>Thanks for scheduling a visit! Your request is now "
            "<strong>pending</strong> confirmation from the establishment.</p>"
            + visit_summary,
        )

    owner_email = get_spot_owner_email(visit.get("tourist_spot_id"))
    if owner_email:
        send_email(
            owner_email,
            f"New visit request pending review — {spot_name}",
            "<p>A tourist has requested a visit to your establishment. "
            "Please review and confirm or decline it from your dashboard.</p>"
            + visit_summary
            + f"<p><strong>Visitor:</strong> {visit.get('visitor_name')} "
            f"({visitor_email}, {visit.get('visitor_phone') or 'no phone provided'})</p>",
        )
