# THT website

Static site for Compagnie THT. Each page is a self-contained bundle: assets
(images, fonts) are embedded in the HTML and resolved to blob URLs at runtime,
so there are no external asset requests and no build step.

## Pages

| URL | File |
| --- | --- |
| `/` | `index.html` |
| `/ateliers` | `ateliers.html` |
| `/cherche-en-corps` | `cherche-en-corps.html` |
| `/contact` | `contact.html` |
| `/fleur` | `fleur.html` |
| `/windows` | `windows.html` |

## Local preview

```sh
python3 -m http.server 8000
```

Then open http://localhost:8000.

## Deploy

Railway builds the `Dockerfile`, which serves the HTML files with Caddy on
`$PORT`. `try_files` maps extensionless URLs to their `.html` file, so
`/contact` and `/contact.html` both work.
