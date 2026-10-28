"""Notification email: Resend HTTPS API when RESEND_API_KEY is set, SMTP otherwise.

Railway blocks outbound SMTP on its non-Pro plans, so production uses Resend
(plain HTTPS on port 443). SMTP stays as a fallback for other hosts.
"""

from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage

RESEND_URL = "https://api.resend.com/emails"
DEFAULT_RESEND_FROM = "THT site <onboarding@resend.dev>"
DEFAULT_NOTIFY_TO = "compagnie.tht@gmail.com"
TIMEOUT = 10  # seconds, for both Resend and SMTP


class MailError(Exception):
    """Raised when a notification could not be sent."""


def notify_to() -> str:
    return os.environ.get("NOTIFY_TO", "").strip() or DEFAULT_NOTIFY_TO


def _recipients(value: str) -> list[str]:
    return [a.strip() for a in value.split(",") if a.strip()]


def _smtp_settings() -> dict[str, str] | None:
    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    sender = os.environ.get("SMTP_FROM", "").strip() or user
    if not (host and user and sender):
        return None
    return {
        "host": host,
        "port": os.environ.get("SMTP_PORT", "").strip() or "465",
        "user": user,
        "password": os.environ.get("SMTP_PASS", ""),
        "from": sender,
    }


def backend() -> str | None:
    """Return "resend", "smtp" or None when nothing is configured."""
    if os.environ.get("RESEND_API_KEY", "").strip():
        return "resend"
    if _smtp_settings():
        return "smtp"
    return None


def build_resend_payload(*, sender: str, to: list[str], subject: str, text: str,
                         reply_to: str | None = None) -> dict:
    payload: dict = {"from": sender, "to": to, "subject": subject, "text": text}
    if reply_to:
        payload["reply_to"] = reply_to
    return payload


def send_via_resend(api_key: str, payload: dict) -> str:
    req = urllib.request.Request(
        RESEND_URL,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Resend sits behind Cloudflare, which rejects the default Python-urllib agent.
            "User-Agent": "tht-site/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise MailError(f"Resend HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise MailError(f"Resend request failed: {exc!r}") from exc
    try:
        return str(json.loads(body).get("id", ""))
    except ValueError:
        return ""


def send_via_smtp(settings: dict[str, str], *, to: list[str], subject: str, text: str,
                  reply_to: str | None = None) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings["from"]
    msg["To"] = ", ".join(to)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text)
    port = int(settings["port"])
    context = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(settings["host"], port, context=context, timeout=TIMEOUT) as smtp:
                smtp.login(settings["user"], settings["password"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(settings["host"], port, timeout=TIMEOUT) as smtp:
                smtp.starttls(context=context)
                smtp.login(settings["user"], settings["password"])
                smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        raise MailError(f"SMTP failed: {exc!r}") from exc


def send_notification(*, subject: str, text: str, reply_to: str | None = None,
                      to: str | None = None) -> str:
    """Send a plain-text notification. Returns the backend used. Raises MailError."""
    recipients = _recipients(to or notify_to())
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    if api_key:
        sender = os.environ.get("RESEND_FROM", "").strip() or DEFAULT_RESEND_FROM
        send_via_resend(api_key, build_resend_payload(
            sender=sender, to=recipients, subject=subject, text=text, reply_to=reply_to))
        return "resend"
    settings = _smtp_settings()
    if settings:
        send_via_smtp(settings, to=recipients, subject=subject, text=text, reply_to=reply_to)
        return "smtp"
    raise MailError("No mail backend configured (set RESEND_API_KEY or SMTP_*)")
