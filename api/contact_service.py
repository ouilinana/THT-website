"""Contact form: save the message to Notion and email a notification (Resend or SMTP)."""

from __future__ import annotations

import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from api.mailer import backend, notify_to, send_notification
from api.subscribe_service import (
    EMAIL_RE,
    NotionClient,
    _email_prop,
    _rich_text_prop,
    _select_prop,
    _title_prop,
)

SOURCE_VALUE = "Website contact form"
TOPICS = {
    "booking": "Programmer un spectacle / Book a show",
    "atelier": "Organiser un atelier / Plan a workshop",
    "event": "Battle / evenement / event",
    "autre": "Autre / Other",
}
MAX_NAME = 200
MAX_EMAIL = 320
MAX_ORG = 300
MAX_MESSAGE = 5000

_RATE: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 3600
_RATE_MAX = 5


@dataclass
class ContactInput:
    name: str
    email: str
    organisation: str
    topic: str
    message: str
    lang: str
    honeypot: str
    client_ip: str


@dataclass
class ContactResult:
    ok: bool
    code: str
    message: str


def check_rate_limit(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _RATE[ip] if now - t < _RATE_WINDOW]
    _RATE[ip] = hits
    if len(hits) >= _RATE_MAX:
        return False
    _RATE[ip].append(now)
    return True


def normalize(inp: ContactInput) -> ContactInput:
    topic = inp.topic.strip().lower()
    return ContactInput(
        name=inp.name.strip()[:MAX_NAME],
        email=inp.email.strip()[:MAX_EMAIL],
        organisation=inp.organisation.strip()[:MAX_ORG],
        topic=topic if topic in TOPICS else "autre",
        message=inp.message.strip()[:MAX_MESSAGE],
        lang="en" if inp.lang.strip().lower() == "en" else "fr",
        honeypot=inp.honeypot,
        client_ip=inp.client_ip,
    )


def validate(inp: ContactInput) -> ContactResult | None:
    if inp.honeypot.strip():
        # Silently accept bots so they do not retry.
        return ContactResult(True, "ok", "OK")
    if len(inp.name) < 2:
        return ContactResult(False, "name", "Invalid name")
    if not EMAIL_RE.match(inp.email):
        return ContactResult(False, "email", "Invalid email")
    if not inp.message:
        return ContactResult(False, "message", "Empty message")
    if not check_rate_limit(inp.client_ip or "unknown"):
        return ContactResult(False, "rate_limit", "Too many requests")
    return None


def _chunks(text: str, size: int = 1900) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def build_notion_page(schema: dict[str, dict], inp: ContactInput) -> tuple[dict[str, Any], list[dict]]:
    """Map the contact message onto whatever properties the database has.

    Only the title and email properties are required. The full message is also
    stored in the page body so nothing is lost to the 2000 character limit.
    """
    props: dict[str, Any] = {}
    notes: list[str] = []

    def prop_by_type(ptype: str) -> str | None:
        return next((n for n, m in schema.items() if m.get("type") == ptype), None)

    title_name = prop_by_type("title")
    if not title_name:
        raise RuntimeError("Database missing title property")
    props[title_name] = _title_prop(inp.name)

    email_name = prop_by_type("email")
    if email_name:
        props[email_name] = _email_prop(inp.email)
    else:
        notes.append(f"Email: {inp.email}")

    if inp.organisation:
        key = next((n for n in ("Organisation", "Organization") if n in schema), None)
        if key and schema[key].get("type") == "rich_text":
            props[key] = _rich_text_prop(inp.organisation)
        else:
            notes.append(f"Organisation: {inp.organisation}")

    if "Source" in schema and schema["Source"].get("type") == "select":
        options = {o["name"] for o in schema["Source"].get("select", {}).get("options", [])}
        if SOURCE_VALUE in options:
            props["Source"] = _select_prop(SOURCE_VALUE)
        else:
            notes.append(f"Source: {SOURCE_VALUE}")
    elif "Source" in schema and schema["Source"].get("type") == "rich_text":
        props["Source"] = _rich_text_prop(SOURCE_VALUE)
    else:
        notes.append(f"Source: {SOURCE_VALUE}")

    notes.append(f"Topic: {TOPICS[inp.topic]}")
    notes.append(f"Lang: {inp.lang}")
    notes.append(f"Message: {inp.message}")
    if "Notes" in schema and schema["Notes"].get("type") == "rich_text":
        props["Notes"] = _rich_text_prop("; ".join(notes)[:2000])

    children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": line}}]},
        }
        for line in _chunks(
            f"Contact form ({inp.lang}), topic: {TOPICS[inp.topic]}\n"
            f"Name: {inp.name}\nEmail: {inp.email}\n"
            f"Organisation: {inp.organisation or '-'}\n\n{inp.message}"
        )
    ]
    return props, children


def save_to_notion(inp: ContactInput, token: str, db_id: str) -> None:
    notion = NotionClient(token, db_id)
    schema = notion.load_schema()
    props, children = build_notion_page(schema, inp)
    notion._request(
        "POST",
        "/pages",
        {"parent": {"database_id": notion.database_id}, "properties": props, "children": children},
    )


def build_notification(inp: ContactInput) -> tuple[str, str]:
    """Return (subject, text) for the notification email."""
    subject = f"[THT Contact] {TOPICS[inp.topic]} - {inp.name}"
    text = (
        f"New message from the website contact form ({inp.lang})\n\n"
        f"Name: {inp.name}\n"
        f"Email: {inp.email}\n"
        f"Organisation: {inp.organisation or '-'}\n"
        f"Topic: {TOPICS[inp.topic]}\n\n"
        f"{inp.message}\n"
    )
    return subject, text


def _log(msg: str) -> None:
    sys.stderr.write(f"[contact] {msg}\n")


def handle_contact(inp: ContactInput, *, test_mode: bool = False) -> ContactResult:
    if not test_mode:
        test_mode = os.environ.get("SUBSCRIBE_TEST_MODE", "") == "1"
    inp = normalize(inp)
    err = validate(inp)
    if err is not None:
        return err
    if test_mode:
        return ContactResult(True, "ok", "Test mode: not stored")

    token = os.environ.get("NOTION_TOKEN", "")
    db_id = os.environ.get("NOTION_CONTACT_DATABASE_ID", "") or os.environ.get("NOTION_DATABASE_ID", "")
    notion_ready = bool(token and db_id)
    mail_backend = backend()
    if not notion_ready and not mail_backend:
        _log("neither Notion nor email (RESEND_API_KEY or SMTP_*) is configured")
        return ContactResult(False, "config", "Service not configured")

    saved = emailed = False
    if notion_ready:
        try:
            save_to_notion(inp, token, db_id)
            saved = True
        except Exception as exc:  # noqa: BLE001 - keep going so the email still goes out
            _log(f"Notion save failed: {exc!r}")
    if mail_backend:
        try:
            subject, text = build_notification(inp)
            send_notification(subject=subject, text=text, reply_to=inp.email, to=notify_to())
            emailed = True
        except Exception as exc:  # noqa: BLE001
            _log(f"{mail_backend} notification failed: {exc!r}")

    _log(f"from={inp.email} topic={inp.topic} notion={saved} email={emailed} via={mail_backend}")
    if saved or emailed:
        return ContactResult(True, "ok", "Sent")
    return ContactResult(False, "delivery", "Could not deliver message")
