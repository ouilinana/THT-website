#!/usr/bin/env python3
"""HTTP server for POST /api/subscribe and POST /api/contact (stdlib only)."""

from __future__ import annotations

import json
import os
import sys
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from api.contact_service import ContactInput, handle_contact  # noqa: E402
from api.subscribe_service import SubscribeInput, subscribe  # noqa: E402


def _client_ip(headers: dict[str, str]) -> str:
    forwarded = headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return headers.get("Remote-Addr", "127.0.0.1")


def _parse_body(content_type: str, body: bytes) -> dict[str, str]:
    if "application/json" in content_type:
        data = json.loads(body.decode("utf-8") or "{}")
        return {k: str(v) for k, v in data.items()}
    if "multipart/form-data" in content_type:
        # cgi.FieldStorage was removed in Python 3.13; parse with the email package.
        msg = BytesParser(policy=HTTP).parsebytes(
            b"Content-Type: " + content_type.encode("latin-1") + b"\r\n\r\n" + body
        )
        out: dict[str, str] = {}
        for part in msg.iter_parts():
            key = part.get_param("name", header="content-disposition")
            if not key or key in out:
                continue
            payload = part.get_payload(decode=True) or b""
            out[key] = payload.decode(part.get_content_charset() or "utf-8", "replace")
        return out
    # application/x-www-form-urlencoded
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {k: (v[0] if v else "") for k, v in parsed.items()}


def _redirect_for(lang: str, ok: bool) -> str:
    if lang == "en":
        return "/en/newsletter-thanks.html" if ok else "/en/newsletter-error.html"
    return "/newsletter-merci.html" if ok else "/newsletter-erreur.html"


class Handler(BaseHTTPRequestHandler):
    server_version = "THTSubscribe/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        self.send_error(404)

    def _read_fields(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(min(length, 64 * 1024))
        ctype = self.headers.get("Content-Type", "")
        try:
            return _parse_body(ctype, body)
        except (json.JSONDecodeError, ValueError, AttributeError):
            return {}

    def _client(self) -> str:
        return _client_ip(
            {
                "X-Forwarded-For": self.headers.get("X-Forwarded-For", ""),
                "Remote-Addr": self.client_address[0],
            }
        )

    def _send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/") == "/api/contact":
            self._handle_contact()
            return
        if parsed.path != "/api/subscribe":
            self.send_error(404)
            return

        fields = self._read_fields()

        inp = SubscribeInput(
            name=fields.get("name", ""),
            email=fields.get("email", ""),
            city=fields.get("city", ""),
            organisation=fields.get("organisation", ""),
            consent=fields.get("consent", "") in ("1", "true", "on", "yes"),
            honeypot=fields.get("company_website", "") or fields.get("website", ""),
            lang=fields.get("lang", "fr"),
            client_ip=self._client(),
        )

        test_mode = os.environ.get("SUBSCRIBE_TEST_MODE", "") == "1"
        result = subscribe(inp, test_mode=test_mode)

        wants_json = "application/json" in self.headers.get("Accept", "") or fields.get(
            "ajax", ""
        ) in ("1", "true")

        if wants_json:
            self.send_response(200 if result.ok else 400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = {"ok": result.ok, "code": result.code, "message": result.message}
            self.wfile.write(json.dumps(payload).encode())
            return

        loc = _redirect_for(inp.lang, result.ok)
        self.send_response(303)
        self.send_header("Location", loc)
        self.end_headers()

    def _handle_contact(self) -> None:
        fields = self._read_fields()
        inp = ContactInput(
            name=fields.get("name", ""),
            email=fields.get("email", ""),
            organisation=fields.get("organisation", ""),
            topic=fields.get("topic", ""),
            message=fields.get("message", ""),
            lang=fields.get("lang", "fr"),
            honeypot=fields.get("company_website", "") or fields.get("website", ""),
            client_ip=self._client(),
        )
        try:
            result = handle_contact(inp)
        except Exception as exc:  # noqa: BLE001 - always answer the browser with JSON
            sys.stderr.write(f"[contact] unexpected error: {exc!r}\n")
            self._send_json(500, {"ok": False, "code": "server", "message": "Server error"})
            return
        status = 200 if result.ok else (429 if result.code == "rate_limit" else 400)
        if result.code in ("config", "delivery"):
            status = 502
        self._send_json(status, {"ok": result.ok, "code": result.code, "message": result.message})


def main() -> None:
    host = os.environ.get("SUBSCRIBE_BIND", "127.0.0.1")
    port = int(os.environ.get("SUBSCRIBE_PORT", "8000"))
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
