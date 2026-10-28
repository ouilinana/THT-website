import io
import json
import os
import smtplib
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from api import mailer

BASE = {"RESEND_API_KEY": "", "RESEND_FROM": "", "SMTP_HOST": "", "SMTP_USER": "", "SMTP_FROM": "",
        "SMTP_PASS": "", "SMTP_PORT": "", "NOTIFY_TO": ""}


def resp(body: dict):
    r = MagicMock()
    r.read.return_value = json.dumps(body).encode()
    r.__enter__ = lambda s: s
    r.__exit__ = lambda s, *a: False
    return r


class BackendTests(unittest.TestCase):
    @patch.dict(os.environ, BASE, clear=False)
    def test_nothing_configured(self):
        self.assertIsNone(mailer.backend())
        with self.assertRaises(mailer.MailError):
            mailer.send_notification(subject="s", text="t")

    @patch.dict(os.environ, {**BASE, "RESEND_API_KEY": "re_x", "SMTP_HOST": "smtp.example.com",
                             "SMTP_USER": "u@example.com"}, clear=False)
    def test_resend_wins_over_smtp(self):
        self.assertEqual(mailer.backend(), "resend")


class ResendTests(unittest.TestCase):
    @patch.dict(os.environ, {**BASE, "RESEND_API_KEY": "re_secret"}, clear=False)
    @patch("api.mailer.urllib.request.urlopen")
    def test_posts_to_resend(self, urlopen):
        urlopen.return_value = resp({"id": "abc"})
        used = mailer.send_notification(subject="Hello", text="Body", reply_to="visitor@example.com")
        self.assertEqual(used, "resend")
        req = urlopen.call_args.args[0]
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 10)
        self.assertEqual(req.full_url, "https://api.resend.com/emails")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("Authorization"), "Bearer re_secret")
        payload = json.loads(req.data)
        self.assertEqual(payload["from"], "THT site <onboarding@resend.dev>")
        self.assertEqual(payload["to"], ["compagnie.tht@gmail.com"])
        self.assertEqual(payload["reply_to"], "visitor@example.com")
        self.assertEqual(payload["subject"], "Hello")
        self.assertEqual(payload["text"], "Body")

    @patch.dict(os.environ, {**BASE, "RESEND_API_KEY": "re_secret", "RESEND_FROM": "THT <site@example.com>",
                             "NOTIFY_TO": "a@example.com, b@example.com"}, clear=False)
    @patch("api.mailer.urllib.request.urlopen")
    def test_custom_from_and_recipients(self, urlopen):
        urlopen.return_value = resp({"id": "abc"})
        mailer.send_notification(subject="s", text="t")
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload["from"], "THT <site@example.com>")
        self.assertEqual(payload["to"], ["a@example.com", "b@example.com"])
        self.assertNotIn("reply_to", payload)

    @patch.dict(os.environ, {**BASE, "RESEND_API_KEY": "re_secret"}, clear=False)
    @patch("api.mailer.urllib.request.urlopen")
    def test_http_error_becomes_mail_error(self, urlopen):
        urlopen.side_effect = urllib.error.HTTPError(
            mailer.RESEND_URL, 403, "Forbidden", {}, io.BytesIO(b'{"message":"domain not verified"}'))
        with self.assertRaises(mailer.MailError) as ctx:
            mailer.send_notification(subject="s", text="t")
        self.assertIn("403", str(ctx.exception))
        self.assertIn("domain not verified", str(ctx.exception))


class SmtpFallbackTests(unittest.TestCase):
    @patch.dict(os.environ, {**BASE, "SMTP_HOST": "smtp.example.com", "SMTP_PORT": "465",
                             "SMTP_USER": "u@example.com", "SMTP_PASS": "p"}, clear=False)
    @patch("api.mailer.smtplib.SMTP_SSL")
    def test_smtp_used_without_resend_key(self, smtp_ssl):
        client = smtp_ssl.return_value.__enter__.return_value
        used = mailer.send_notification(subject="s", text="t", reply_to="v@example.com")
        self.assertEqual(used, "smtp")
        self.assertEqual(smtp_ssl.call_args.kwargs["timeout"], 10)
        msg = client.send_message.call_args.args[0]
        self.assertEqual(msg["Reply-To"], "v@example.com")
        self.assertEqual(msg["From"], "u@example.com")

    @patch.dict(os.environ, {**BASE, "SMTP_HOST": "smtp.example.com", "SMTP_PORT": "465",
                             "SMTP_USER": "u@example.com"}, clear=False)
    @patch("api.mailer.smtplib.SMTP_SSL", side_effect=OSError(101, "Network unreachable"))
    def test_network_unreachable_becomes_mail_error(self, _):
        with self.assertRaises(mailer.MailError):
            mailer.send_notification(subject="s", text="t")


if __name__ == "__main__":
    unittest.main()
