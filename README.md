# THT website

Static site for [Compagnie THT](https://trois-heures-trente.com): server-rendered HTML, assets on disk, Caddy in Docker on Railway.

## Pages

| URL (FR) | URL (EN) | Source output |
| --- | --- | --- |
| `/` | `/en/` | `index.html`, `en/index.html` |
| `/ateliers` | `/en/ateliers` | `ateliers.html`, `en/ateliers.html` |
| `/cherche-en-corps` | `/en/cherche-en-corps` | `cherche-en-corps.html`, … |
| `/contact` | `/en/contact` | `contact.html`, … |
| `/fleur` | `/en/fleur` | `fleur.html`, … |
| `/windows` | `/en/windows` | `windows.html`, … |

## Build (from legacy bundles)

Original Claude artifact bundles (not in git; React UMD triggers secret scanners) belong in `legacy/bundles/`. Restore once from pre-refactor history, e.g. `git show main:index.html > legacy/bundles/index.html`. To regenerate HTML after editing `scripts/build_site.py`:

```sh
pip install pillow
python3 scripts/build_site.py
```

This extracts images/fonts into `assets/`, writes static FR/EN pages, and updates `sitemap.xml` / `robots.txt`.

## Newsletter API

The home page form posts to `POST /api/subscribe`. The Docker image runs Caddy (static files) and a small Python API on `127.0.0.1:8000`.

Copy `.env.example` to `.env` for local runs (never commit secrets).

| Variable | Purpose |
| --- | --- |
| `NOTION_TOKEN` | Notion integration secret |
| `NOTION_DATABASE_ID` | `THT Contacts` database (`9e4d3dbc496e4074b8dc5975f1fc398d`) |
| `SMTP_*` | Infomaniak SMTP (SSL 465) for notification mail |
| `NOTIFY_TO` | Inbox for alerts (e.g. `compagnie.tht@gmail.com`) |
| `SUBSCRIBE_TEST_MODE=1` | Skip Notion/SMTP (tests / dry run) |

### Notion setup

1. Create an integration at [Notion integrations](https://www.notion.so/my-integrations).
2. Open the **THT Contacts** database and **Connect** the integration (full access).
3. Set `NOTION_TOKEN` and `NOTION_DATABASE_ID` on Railway.

The API reads the database schema at runtime (title **Name**, **Email**, optional **Country/City**, **Organisation**, **Source**, **Relationship**, **Notes**). If select options for website signup are missing, details are appended to **Notes**. Duplicate emails are skipped.

### Local preview

With Docker (Caddy + API):

```sh
docker build -t tht-site .
docker run --rm -p 8080:8080 --env-file .env tht-site
```

Tests:

```sh
SUBSCRIBE_TEST_MODE=1 python3 -m unittest discover -s tests -v
curl -X POST http://127.0.0.1:8000/api/subscribe -d "name=Test&email=t@example.com&consent=1&lang=fr"
```

Static-only fallback (form POST will not reach API):

```sh
python3 -m http.server 8080
```

## Deploy

Railway builds the `Dockerfile`, which serves `/srv` with Caddy on `$PORT`. Extensionless URLs map to `.html` files via `try_files`.

See `docs/I18N.md` for the bilingual URL plan.

### Refreshing FLEUR photos

Source photos (LeDockerNoir) live in [this Drive folder](https://drive.google.com/drive/folders/1eaQWj-NYBE0b3p4_UEMfmSZHbWsa1G0E). Download locally (not committed), then:

```sh
pip install gdown pillow
gdown --folder "https://drive.google.com/drive/folders/1eaQWj-NYBE0b3p4_UEMfmSZHbWsa1G0E" -O /tmp/fleur-drive
python3 scripts/optimize_fleur_from_drive.py /tmp/fleur-drive
python3 scripts/build_site.py
```
