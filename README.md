# THT website

Production design is the **Claude artifact bundles** (same as [trois-heures-trente.com](https://trois-heures-trente.com)). This repo patches those bundles for SEO, assets, Cherche videos, newsletter, and `/en` URLs — without replacing the React layout.

## Pages

| URL (FR) | URL (EN) | Source |
| --- | --- | --- |
| `/` | `/en/` | `index.html`, `en/index.html` |
| `/ateliers` | `/en/ateliers` | bundled + patched |
| `/cherche-en-corps` | `/en/cherche-en-corps` | … |
| `/contact` | `/en/contact` | … |
| `/fleur` | `/en/fleur` | … |
| `/windows` | `/en/windows` | … |

Caddy `try_files` maps extensionless paths to `.html`.

## Build (patch bundles)

Canonical bundles live in `legacy/bundles/` (from `main`). Regenerate deployable HTML:

```sh
pip install pillow
python3 scripts/build_site.py
```

This externalizes images/fonts to `assets/`, applies agreed content fixes inside the bundled template, writes FR root + `en/` copies (English default locale), and updates `sitemap.xml`, `robots.txt`, and `llms.txt`.

Public contact email: `compagnie.tht@gmail.com`.

## Newsletter API

Home newsletter block posts to `POST /api/subscribe`. Docker runs Caddy + Python API on `127.0.0.1:8000`.

The contact page form posts JSON to `POST /api/contact`. Each message is saved to Notion (`NOTION_CONTACT_DATABASE_ID`, or `NOTION_DATABASE_ID` if unset) and emailed to `NOTIFY_TO` with Reply-To set to the sender. The request succeeds if either Notion or email works; if both fail the API still answers JSON (`503`, `{"ok": false, "code": "delivery"}`) and the page shows its error line.

### Notification email

Contact messages and newsletter signups send a notification to `NOTIFY_TO`:

- If `RESEND_API_KEY` is set, it goes through the [Resend](https://resend.com) HTTPS API (`POST https://api.resend.com/emails`) from `RESEND_FROM` (default `THT site <onboarding@resend.dev>`). Use this on Railway, which blocks outbound SMTP on non-Pro plans. The default test sender only delivers to the Resend account owner's address, so `NOTIFY_TO` must be that address until a domain is verified in Resend.
- Otherwise it falls back to SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`).

Reply-To is set to the visitor, so replying from the inbox answers them directly. Notion and email calls time out after 10 seconds, and a failed notification never fails a newsletter signup that was saved in Notion.

See `.env.example` for all variables.

## Deploy

Railway builds the `Dockerfile` (Caddy on `$PORT`, static `/srv`, `/api/*` proxied).

## Visual regression

```sh
python3 -m http.server 8080   # local patched site (*.html paths)
python3 scripts/capture_compare.py   # production vs local side-by-sides → /opt/cursor/artifacts/compare/
```
