import os
import unittest
from unittest.mock import patch

import api.contact_service as cs
from api.contact_service import ContactInput, build_email, build_notion_page, handle_contact, normalize, validate

ENV = {
    "NOTION_TOKEN": "dummy",
    "NOTION_DATABASE_ID": "db123",
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "465",
    "SMTP_USER": "site@example.com",
    "SMTP_PASS": "x",
    "SMTP_FROM": "site@example.com",
    "NOTIFY_TO": "compagnie.tht@gmail.com",
}


def make(ip, **kw):
    base = dict(name="Jean Dupont", email="jean@example.com", organisation="Theatre X", topic="booking",
                message="Bonjour, une date en mai ?", lang="fr", honeypot="", client_ip=ip)
    base.update(kw)
    return ContactInput(**base)


class ContactValidationTests(unittest.TestCase):
    def test_valid_input(self):
        self.assertIsNone(validate(make("10.0.0.1")))

    def test_honeypot_silent_ok(self):
        r = validate(make("10.0.0.2", honeypot="http://spam"))
        self.assertTrue(r.ok)

    def test_invalid_email(self):
        r = validate(make("10.0.0.3", email="nope"))
        self.assertFalse(r.ok)

    def test_empty_message(self):
        r = validate(normalize(make("10.0.0.4", message="   ")))
        self.assertFalse(r.ok)

    def test_rate_limit(self):
        results = [validate(make("10.0.0.5")) for _ in range(6)]
        self.assertIsNone(results[0])
        self.assertEqual(results[-1].code, "rate_limit")


class ContactPayloadTests(unittest.TestCase):
    def test_notion_mapping(self):
        schema = {
            "Name": {"type": "title"},
            "Email": {"type": "email"},
            "Organisation": {"type": "rich_text"},
            "Notes": {"type": "rich_text"},
        }
        props, children = build_notion_page(schema, make("10.0.1.1"))
        self.assertEqual(props["Name"]["title"][0]["text"]["content"], "Jean Dupont")
        self.assertEqual(props["Email"]["email"], "jean@example.com")
        self.assertIn("Website contact form", props["Notes"]["rich_text"][0]["text"]["content"])
        self.assertTrue(children)

    def test_email_headers(self):
        msg = build_email(make("10.0.1.2"), "site@example.com", "compagnie.tht@gmail.com")
        self.assertEqual(msg["To"], "compagnie.tht@gmail.com")
        self.assertEqual(msg["Reply-To"], "jean@example.com")
        self.assertIn("Jean Dupont", msg["Subject"])
        self.assertIn("une date en mai", msg.get_content())


class HandleContactTests(unittest.TestCase):
    @patch.dict(os.environ, ENV, clear=False)
    def test_saves_and_emails(self):
        with patch.object(cs, "save_to_notion") as notion, patch.object(cs, "send_email") as smtp:
            r = handle_contact(make("10.0.2.1"))
        self.assertTrue(r.ok)
        notion.assert_called_once()
        smtp.assert_called_once()
        self.assertEqual(smtp.call_args[0][0]["To"], "compagnie.tht@gmail.com")

    @patch.dict(os.environ, ENV, clear=False)
    def test_email_still_sent_when_notion_fails(self):
        with patch.object(cs, "save_to_notion", side_effect=RuntimeError("401")), \
                patch.object(cs, "send_email") as smtp:
            r = handle_contact(make("10.0.2.2"))
        self.assertTrue(r.ok)
        smtp.assert_called_once()

    @patch.dict(os.environ, ENV, clear=False)
    def test_error_when_both_fail(self):
        with patch.object(cs, "save_to_notion", side_effect=RuntimeError("401")), \
                patch.object(cs, "send_email", side_effect=OSError("refused")):
            r = handle_contact(make("10.0.2.3"))
        self.assertFalse(r.ok)

    def test_test_mode_skips_delivery(self):
        with patch.object(cs, "save_to_notion") as notion, patch.object(cs, "send_email") as smtp:
            r = handle_contact(make("10.0.2.4"), test_mode=True)
        self.assertTrue(r.ok)
        notion.assert_not_called()
        smtp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
