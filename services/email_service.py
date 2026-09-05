"""
Outbound transactional email via Brevo SMTP relay.

Sending is best-effort: any failure (missing config, network, auth) is
logged and swallowed so it never blocks the caller's request flow.
"""

from __future__ import annotations

import html
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp-relay.brevo.com"
SMTP_PORT = 587


def send_email(to: str, subject: str, html_body: str, reply_to: str | None = None) -> bool:
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
    if reply_to:
        message["Reply-To"] = reply_to
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


LTCATO_SERVICE_REQUESTS_EMAIL = "ltcato.tourism@gmail.com"

_BRAND_RED = "#9b2c2c"
_BRAND_GOLD = "#fdf2d6"
_BRAND_GOLD_TEXT = "#805500"
_INK = "#1a1a1a"
_MUTED = "#57534e"
_BORDER = "#f5e8d2"


def _division_badge(division: str) -> str:
    is_culture = "Culture" in (division or "")
    bg = "#fdf2d6" if is_culture else "rgba(155,44,44,0.1)"
    fg = _BRAND_GOLD_TEXT if is_culture else _BRAND_RED
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:999px;'
        f'font-size:12px;font-weight:600;background:{bg};color:{fg};">'
        f"{html.escape(division or '')}</span>"
    )


def _row(label: str, value: str) -> str:
    return (
        '<tr>'
        f'<td style="padding:4px 0;font-size:13px;color:{_MUTED};white-space:nowrap;'
        'vertical-align:top;padding-right:14px;">' + html.escape(label) + "</td>"
        f'<td style="padding:4px 0;font-size:14px;color:{_INK};">' + value + "</td>"
        "</tr>"
    )


def send_service_request_email(request_row: dict) -> None:
    """Notify LTCATO's inbox directly — the digital equivalent of the
    'Letter of Request... through E-mail' step every Citizen's Charter
    service starts with (see services/citizen_charter.py). Replying to this
    email goes straight to the requester, not back into LTCATO's own inbox."""
    name = html.escape(request_row.get("requester_name") or "")
    email = html.escape(request_row.get("requester_email") or "")
    phone = html.escape(request_row.get("requester_phone") or "")
    message_text = html.escape(request_row.get("message") or "").replace("\n", "<br>")
    service_title = html.escape(request_row.get("service_title") or "")
    division = request_row.get("division") or ""

    contact = f'<a href="mailto:{email}" style="color:{_BRAND_RED};">{email}</a>'
    if phone:
        contact += f" &middot; {phone}"

    body = f"""
<div style="background:#f0ebe8;padding:32px 16px;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" style="max-width:560px;margin:0 auto;background:#ffffff;
      border:1px solid {_BORDER};border-radius:12px;overflow:hidden;border-collapse:separate;">
    <tr>
      <td style="background:{_BRAND_RED};padding:20px 28px;">
        <span style="color:#ffffff;font-size:15px;font-weight:700;letter-spacing:0.02em;">LTCATO</span>
        <span style="color:#f5e8d2;font-size:13px;"> &middot; Citizen's Charter</span>
      </td>
    </tr>
    <tr>
      <td style="padding:28px;">
        <p style="margin:0 0 6px;font-size:12px;font-weight:600;letter-spacing:0.05em;
            text-transform:uppercase;color:{_MUTED};">New service request</p>
        <h1 style="margin:0 0 10px;font-size:19px;line-height:1.35;color:{_INK};">
          {request_row.get('service_number')}. {service_title}
        </h1>
        {_division_badge(division)}

        <table role="presentation" width="100%" style="margin-top:22px;border-collapse:collapse;">
          {_row('Requester', name)}
          {_row('Contact', contact)}
        </table>

        <div style="margin-top:18px;padding:16px 18px;background:#faf7f5;border-left:3px solid {_BRAND_RED};
            border-radius:0 8px 8px 0;font-size:14px;line-height:1.6;color:{_INK};">
          {message_text}
        </div>
      </td>
    </tr>
    <tr>
      <td style="padding:16px 28px;background:#faf7f5;border-top:1px solid {_BORDER};">
        <p style="margin:0;font-size:12px;color:{_MUTED};">
          Reply directly to this email to respond to {name or 'the requester'}.
        </p>
      </td>
    </tr>
  </table>
</div>
"""

    send_email(
        LTCATO_SERVICE_REQUESTS_EMAIL,
        f"New service request — {request_row.get('service_title')}",
        body,
        reply_to=request_row.get("requester_email") or None,
    )


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
