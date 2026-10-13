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

## Local preview

With Caddy (matches production routing):

```sh
docker build -t tht-site .
docker run --rm -p 8080:8080 tht-site
```

Or plain Python (requires `.html` in URLs):

```sh
python3 -m http.server 8000
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
