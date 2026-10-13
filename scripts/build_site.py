#!/usr/bin/env python3
"""Build static HTML from legacy bundled pages (editable source of truth: scripts/ + assets/)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "legacy" / "bundles"
OUT = ROOT
ASSETS = ROOT / "assets"
SITE_URL = "https://trois-heures-trente.com"

PAGES = [
    "index.html",
    "cherche-en-corps.html",
    "fleur.html",
    "windows.html",
    "ateliers.html",
    "contact.html",
]

CEC_PDF = "/assets/docs/THT_Cherche-en-corps_01_presentation.pdf"
FLEUR_DIR = "/assets/images/fleur"
FLEUR_HERO = f"{FLEUR_DIR}/hero.webp"
FLEUR_OG = f"{SITE_URL}{FLEUR_DIR}/og-fleur.webp"
FLEUR_GALLERY = [f"{FLEUR_DIR}/g{i:02d}.webp" for i in range(1, 9)]

WP_REPLACEMENTS = {
    "https://www.trois-heures-trente.com/wp-content/uploads/2025/08/THT-114-scaled.jpg": "/assets/images/windows-hero.webp",
    "https://www.trois-heures-trente.com/wp-content/uploads/2023/08/Ouili_fleur-63-scaled.jpg": f"{FLEUR_DIR}/tile.webp",
    "https://www.trois-heures-trente.com/wp-content/uploads/2025/08/THT-241-scaled.jpg": "/assets/images/cherche-tile.webp",
    "https://www.trois-heures-trente.com/wp-content/uploads/2023/08/Ouili_fleur-52-2-scaled.jpg": FLEUR_HERO,
    "https://www.trois-heures-trente.com/wp-content/uploads/2025/08/THT-329-scaled.jpg": "/assets/images/windows-hero.webp",
    "https://www.trois-heures-trente.com/wp-content/uploads/2025/08/Portrait-de-CEC-FR-Presentation-1-768x1024.png": "/assets/docs/THT_Cherche-en-corps_01_presentation.pdf",
}

PAGE_META: dict[str, dict[str, str]] = {
    "index.html": {
        "fr": {
            "title": "Compagnie THT | Danse hip-hop et contemporaine",
            "description": "Compagnie THT (Trois Heures Trente): créations FLEUR, Cherche en Corps, WINDOWS. Hip-hop et danse contemporaine, Carrières-sous-Poissy et Oslo.",
        },
        "en": {
            "title": "THT Company | Hip-hop and contemporary dance",
            "description": "THT Company (Trois Heures Trente): FLEUR, Cherche en Corps, WINDOWS. Hip-hop meets contemporary dance, based in France and Norway.",
        },
    },
    "cherche-en-corps.html": {
        "fr": {
            "title": "Cherche en Corps | Compagnie THT",
            "description": "Cherche en Corps, duo de Ouili Nana et Raphaël Saint-Laurent. Teaser, captation intégrale et tournée. Compagnie THT.",
        },
        "en": {
            "title": "Cherche en Corps | THT Company",
            "description": "Cherche en Corps, a duo by Ouili Nana and Raphaël Saint-Laurent. Teaser, full recording, and tour dates. THT Company.",
        },
    },
    "fleur.html": {
        "fr": {
            "title": "FLEUR | Solo de Ouili Nana | Compagnie THT",
            "description": "FLEUR, solo hip-hop de Ouili Nana. 50 minutes, compagnie THT.",
        },
        "en": {
            "title": "FLEUR | Solo by Ouili Nana | THT Company",
            "description": "FLEUR, a hip-hop solo by Ouili Nana. 50 minutes, THT Company.",
        },
    },
    "windows.html": {
        "fr": {
            "title": "WINDOWS | Compagnie THT",
            "description": "WINDOWS, création 2025 chorégraphiée par Ouili Nana. Trio hip-hop et lumière.",
        },
        "en": {
            "title": "WINDOWS | THT Company",
            "description": "WINDOWS, 2025 creation choreographed by Ouili Nana. A hip-hop trio in light and shadow.",
        },
    },
    "ateliers.html": {
        "fr": {
            "title": "Ateliers | Compagnie THT",
            "description": "Ateliers de transmission: hip-hop, freestyle et création avec la compagnie THT.",
        },
        "en": {
            "title": "Workshops | THT Company",
            "description": "Workshops in hip-hop, freestyle, and creation with THT Company.",
        },
    },
    "contact.html": {
        "fr": {
            "title": "Contact | Compagnie THT",
            "description": "Contact et diffusion: contact@trois-heures-trente.com. Compagnie THT, Carrières-sous-Poissy.",
        },
        "en": {
            "title": "Contact | THT Company",
            "description": "Booking and contact: contact@trois-heures-trente.com. THT Company, France.",
        },
    },
}


def parse_bundle(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    manifest = json.loads(
        re.search(r'<script type="__bundler/manifest">(.*?)</script>', text, re.DOTALL).group(1)
    )
    template = json.loads(
        re.search(r'<script type="__bundler/template">(.*?)</script>', text, re.DOTALL).group(1)
    )
    return manifest, template


def split_locales(template: str) -> tuple[str, str]:
    parts = re.split(
        r'<sc-if value="\{\{ isFr \}\}"[^>]*>|<sc-if value="\{\{ isEn \}\}"[^>]*>|</sc-if>',
        template,
    )
    fr = parts[1] if len(parts) > 1 else template
    en = parts[3] if len(parts) > 3 else ""
    return fr, en


def extract_helmet_styles(template: str) -> str:
    m = re.search(r"<style>(.*?)</style>", template, re.DOTALL)
    return m.group(1) if m else ""


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.strip().lower()).strip("-")
    return s[:80] or "image"


def decode_asset_data(data: str) -> bytes:
    if data.startswith("data:"):
        return __import__("base64").b64decode(data.split(",", 1)[1])
    return __import__("base64").b64decode(data)


def optimize_image(src: Path, dest: Path, max_width: int = 1920) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
    except ImportError:
        shutil.copy2(src, dest.with_suffix(src.suffix))
        return

    with Image.open(src) as im:
        im = im.convert("RGB") if im.mode in ("RGBA", "P") else im
        w, h = im.size
        if w > max_width:
            im = im.resize((max_width, int(h * max_width / w)), Image.Resampling.LANCZOS)
        im.save(dest, "WEBP", quality=82, method=6)


def collect_assets() -> dict[str, str]:
    """Extract images/fonts from legacy bundles; return uuid -> public URL map."""
    uuid_map: dict[str, str] = {}
    raw_dir = ASSETS / "_raw"
    img_dir = ASSETS / "images"
    font_dir = ASSETS / "fonts"
    raw_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)
    font_dir.mkdir(parents=True, exist_ok=True)

    seen_fonts: set[str] = set()

    for page in PAGES:
        bundle_path = LEGACY / page
        if not bundle_path.exists():
            continue
        manifest, template = parse_bundle(bundle_path)
        for uid, meta in manifest.items():
            if not isinstance(meta, dict):
                continue
            mime = meta.get("mime", "")
            data = meta.get("data", "")
            if not data:
                continue
            if mime.startswith("image/"):
                if uid in uuid_map:
                    continue
                alt_m = re.search(
                    rf'src="{re.escape(uid)}"[^>]*alt="([^"]*)"|alt="([^"]*)"[^>]*src="{re.escape(uid)}"',
                    template,
                )
                alt = (alt_m.group(1) or alt_m.group(2) or uid) if alt_m else uid
                ext = ".png" if "png" in mime else ".jpg"
                raw = raw_dir / f"{slugify(alt)}-{uid[:8]}{ext}"
                if not raw.exists():
                    raw.write_bytes(decode_asset_data(data))
                webp = img_dir / f"{slugify(alt)}-{uid[:8]}.webp"
                if not webp.exists():
                    optimize_image(raw, webp)
                uuid_map[uid] = f"/assets/images/{webp.name}"
            elif mime == "font/woff2" and uid not in seen_fonts:
                seen_fonts.add(uid)
                out = font_dir / f"{uid}.woff2"
                if not out.exists():
                    out.write_bytes(decode_asset_data(data))
                uuid_map[uid] = f"/assets/fonts/{out.name}"

    return uuid_map


def replace_uuids(html: str, uuid_map: dict[str, str]) -> str:
    for uid, url in sorted(uuid_map.items(), key=lambda x: -len(x[0])):
        html = html.replace(f'"{uid}"', f'"{url}"')
        html = html.replace(f"url({uid})", f"url({url})")
        html = html.replace(f'url("{uid}")', f'url("{url}")')
    return html


def fix_internal_links(html: str, lang: str, page: str) -> str:
    prefix = "" if lang == "fr" else "/en"
    other_prefix = "/en" if lang == "fr" else ""

    for name in PAGES:
        base = name.replace(".html", "")
        if lang == "fr":
            html = html.replace(f'href="{name}"', f'href="/{base}"')
            html = html.replace(f'href="/{base}"', f'href="/{base}"')  # idempotent
        else:
            html = html.replace(f'href="{name}"', f'href="/en/{base}"')

    html = re.sub(
        r'<span style="color:rgba\(233,236,242,.4\)">\[\s*<span style="color:#5ec9ff">fr</span>/<span sc-camel-on-click="\{\{ setIsEn \}\}"[^>]*>en</span>\s*\]</span>',
        f'<span style="color:rgba(233,236,242,.4)">[<a href="{other_prefix or "/"}" style="color:#5ec9ff;text-decoration:none">fr</a>/<a href="{prefix or "/"}" style="color:#5ec9ff;text-decoration:none">en</a>]</span>',
        html,
    )
    html = re.sub(
        r'<span style="color:rgba\(233,236,242,.4\)">\[\s*<span sc-camel-on-click="\{\{ setIsFr \}\}"[^>]*>fr</span>/<span style="color:#5ec9ff">en</span>\s*\]</span>',
        f'<span style="color:rgba(233,236,242,.4)">[<a href="{other_prefix or "/"}" style="color:#5ec9ff;text-decoration:none">fr</a>/<a href="{prefix or "/"}" style="color:#5ec9ff;text-decoration:none">en</a>]</span>',
        html,
    )
    if lang == "en" and page == "index.html":
        html = html.replace('href="/"', 'href="/en/"')
    return html


def strip_react_artifacts(html: str) -> str:
    html = re.sub(r"<script src=\"[^\"]+\"></script>", "", html)
    html = re.sub(r"<x-dc>|</x-dc>|<helmet[^>]*>|</helmet>", "", html)
    html = re.sub(r"\sdata-screen-label=\"[^\"]*\"", "", html)
    html = re.sub(r"\ssc-camel-[a-z-]+=\"[^\"]*\"", "", html)
    html = re.sub(r"\shint-placeholder-val=\"[^\"]*\"", "", html)
    return html


def fix_wp_urls(html: str) -> str:
    for old, new in WP_REPLACEMENTS.items():
        html = html.replace(old, new)
    return replace_remaining_wp_images(html)


def replace_remaining_wp_images(html: str) -> str:
    """Swap any leftover WordPress URLs (404) for local WebP gallery images."""
    img_dir = ASSETS / "images"
    pool = sorted(img_dir.glob("*.webp"))
    if not pool:
        return html
    pool_paths = [f"/assets/images/{p.name}" for p in pool if p.name != "og-default.webp"]
    if not pool_paths:
        pool_paths = [f"/assets/images/{pool[0].name}"]
    i = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal i
        url = pool_paths[i % len(pool_paths)]
        i += 1
        return match.group(0).replace(match.group(1), url)

    html = re.sub(
        r'src="(https://www\.trois-heures-trente\.com/wp-content/uploads/[^"]+)"',
        repl,
        html,
    )
    html = re.sub(
        r'href="(https://www\.trois-heures-trente\.com/wp-content/uploads/[^"]+)"',
        lambda m: f'href="mailto:contact@trois-heures-trente.com?subject=Dossier%20FLEUR"',
        html,
    )
    return html


def fix_newsletter(html: str, lang: str) -> str:
    pattern = re.compile(
        r'<div style="display:flex;justify-content:space-between;align-items:center;gap:40px;padding:36px 44px;border-bottom:1px solid rgba\(233,236,242,.12\)">\s*'
        r'<div style="display:flex;flex-direction:column;gap:6px">.*?'
        r'<div style="display:flex;gap:0">.*?</div>\s*</div>',
        re.DOTALL,
    )
    if lang == "fr":
        repl = (
            '<div style="display:flex;justify-content:space-between;align-items:center;gap:40px;padding:36px 44px;border-bottom:1px solid rgba(233,236,242,.12)">'
            '<div style="display:flex;flex-direction:column;gap:6px">'
            '<span style="font:400 26px \'Bebas Neue\',sans-serif;letter-spacing:.05em">Nous écrire</span>'
            '<span style="font:400 11px \'IBM Plex Mono\',monospace;color:rgba(233,236,242,.55)">'
            "Dates, créations, diffusion: écrivez-nous directement.</span></div>"
            '<a href="mailto:contact@trois-heures-trente.com" style="background:#5ec9ff;color:#08090c;padding:12px 22px;text-decoration:none;font:500 12px \'IBM Plex Mono\',monospace">contact@trois-heures-trente.com</a></div>'
        )
    else:
        repl = (
            '<div style="display:flex;justify-content:space-between;align-items:center;gap:40px;padding:36px 44px;border-bottom:1px solid rgba(233,236,242,.12)">'
            '<div style="display:flex;flex-direction:column;gap:6px">'
            '<span style="font:400 26px \'Bebas Neue\',sans-serif;letter-spacing:.05em">Get in touch</span>'
            '<span style="font:400 11px \'IBM Plex Mono\',monospace;color:rgba(233,236,242,.55)">'
            "Tour dates, projects, booking: email us directly.</span></div>"
            '<a href="mailto:contact@trois-heures-trente.com" style="background:#5ec9ff;color:#08090c;padding:12px 22px;text-decoration:none;font:500 12px \'IBM Plex Mono\',monospace">contact@trois-heures-trente.com</a></div>'
        )
    return pattern.sub(repl, html)


def fix_cherche_videos(html: str, lang: str) -> str:
    if lang == "fr":
        block = (
            '<div style="font:400 40px \'Bebas Neue\',sans-serif;letter-spacing:.04em">Vidéos</div>'
            '<div style="display:flex;flex-direction:column;gap:20px">'
            '<div><div style="font:400 11px \'IBM Plex Mono\',monospace;color:#5ec9ff;margin-bottom:8px;letter-spacing:.08em">TEASER</div>'
            '<div style="aspect-ratio:16/9;background:#000;border:1px solid rgba(233,236,242,.12)">'
            '<iframe src="https://www.youtube.com/embed/TjewwAOC488" title="Cherche en Corps — teaser" style="width:100%;height:100%;border:0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe></div></div>'
            '<div><div style="font:400 11px \'IBM Plex Mono\',monospace;color:#5ec9ff;margin-bottom:8px;letter-spacing:.08em">CAPTATION INTÉGRALE</div>'
            '<div style="aspect-ratio:16/9;background:#000;border:1px solid rgba(233,236,242,.12)">'
            '<iframe src="https://www.youtube.com/embed/LgsgqCNG7_U" title="Cherche en Corps — captation" style="width:100%;height:100%;border:0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe></div></div>'
            '<div><div style="font:400 11px \'IBM Plex Mono\',monospace;color:rgba(233,236,242,.55);margin-bottom:8px;letter-spacing:.08em">RÉFÉRENCE · SAN FRANCISCO</div>'
            '<div style="aspect-ratio:16/9;background:#000;border:1px solid rgba(233,236,242,.12)">'
            '<iframe src="https://www.youtube.com/embed/K9OICzieSfc" title="Cherche en Corps à San Francisco" style="width:100%;height:100%;border:0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe></div></div>'
            "</div>"
            '<div style="display:flex;gap:20px;font:400 11px \'IBM Plex Mono\',monospace;margin-top:8px">'
            '<a href="https://www.youtube.com/@THTCompagnie" style="color:rgba(233,236,242,.7);text-decoration:none">▶ plus de vidéos sur la chaîne ↗</a></div>'
        )
    else:
        block = (
            '<div style="font:400 40px \'Bebas Neue\',sans-serif;letter-spacing:.04em">Videos</div>'
            '<div style="display:flex;flex-direction:column;gap:20px">'
            '<div><div style="font:400 11px \'IBM Plex Mono\',monospace;color:#5ec9ff;margin-bottom:8px;letter-spacing:.08em">TEASER</div>'
            '<div style="aspect-ratio:16/9;background:#000;border:1px solid rgba(233,236,242,.12)">'
            '<iframe src="https://www.youtube.com/embed/TjewwAOC488" title="Cherche en Corps — teaser" style="width:100%;height:100%;border:0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe></div></div>'
            '<div><div style="font:400 11px \'IBM Plex Mono\',monospace;color:#5ec9ff;margin-bottom:8px;letter-spacing:.08em">FULL RECORDING</div>'
            '<div style="aspect-ratio:16/9;background:#000;border:1px solid rgba(233,236,242,.12)">'
            '<iframe src="https://www.youtube.com/embed/LgsgqCNG7_U" title="Cherche en Corps — full performance" style="width:100%;height:100%;border:0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe></div></div>'
            '<div><div style="font:400 11px \'IBM Plex Mono\',monospace;color:rgba(233,236,242,.55);margin-bottom:8px;letter-spacing:.08em">REFERENCE · SAN FRANCISCO</div>'
            '<div style="aspect-ratio:16/9;background:#000;border:1px solid rgba(233,236,242,.12)">'
            '<iframe src="https://www.youtube.com/embed/K9OICzieSfc" title="Cherche en Corps in San Francisco" style="width:100%;height:100%;border:0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe></div></div>'
            "</div>"
            '<div style="display:flex;gap:20px;font:400 11px \'IBM Plex Mono\',monospace;margin-top:8px">'
            '<a href="https://www.youtube.com/@THTCompagnie" style="color:rgba(233,236,242,.7);text-decoration:none">▶ more on our YouTube channel ↗</a></div>'
        )

    pattern = re.compile(
        r'<div style="font:400 40px \'Bebas Neue\',sans-serif;letter-spacing:.04em">Vid[ée]os</div>.*?'
        r'<div style="display:flex;gap:20px;font:400 11px \'IBM Plex Mono\',monospace">.*?</div>',
        re.DOTALL,
    )
    return pattern.sub(block, html, count=1)


def fix_dossier_links(html: str, page: str) -> str:
    if page == "cherche-en-corps.html":
        html = re.sub(
            r'href="(?:contact\.html|/contact)"([^>]*>)dossier de diffusion ↓',
            rf'href="{CEC_PDF}" download\1dossier de diffusion ↓',
            html,
        )
        html = re.sub(
            r'href="(?:contact\.html|/en/contact)"([^>]*>)download dossier ↓',
            rf'href="{CEC_PDF}" download\1download dossier ↓',
            html,
        )
    if page == "contact.html":
        html = html.replace(
            f'href="{CEC_PDF}"',
            f'href="{CEC_PDF}"',
        )
        html = re.sub(
            r'href="https://www\.trois-heures-trente\.com/wp-content/uploads/2025/08/Portrait-de-CEC-FR-Presentation-1-768x1024\.png"',
            f'href="{CEC_PDF}" download',
            html,
        )
    return html


def apply_fleur_images(html: str) -> str:
    """Hero + gallery from LeDockerNoir photos (assets/images/fleur/)."""
    html = re.sub(
        r'(<div style="position:relative;height:620px;overflow:hidden[^"]*">\s*)'
        r'<img src="[^"]+" alt="FLEUR[^"]*" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover">',
        rf'\1<img src="{FLEUR_HERO}" alt="FLEUR — Ouili Nana" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover">',
        html,
        count=1,
    )
    gallery_imgs = "".join(
        f'<img src="{src}" alt="FLEUR — LeDockerNoir" style="width:100%;aspect-ratio:4/5;object-fit:cover;display:block">'
        for src in FLEUR_GALLERY
    )
    html = re.sub(
        r'<div style="display:grid;grid-template-columns:repeat\(4,1fr\);gap:1px;background:rgba\(233,236,242,.12\);border-top:1px solid rgba\(233,236,242,.12\);border-bottom:1px solid rgba\(233,236,242,.12\)">\s*'
        r'(?:<img src="[^"]+" alt="FLEUR[^"]*" style="width:100%;aspect-ratio:4/5;object-fit:cover;display:block">\s*)+'
        r"</div>",
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:rgba(233,236,242,.12);border-top:1px solid rgba(233,236,242,.12);border-bottom:1px solid rgba(233,236,242,.12)">{gallery_imgs}</div>',
        html,
        count=1,
    )
    return html


def fix_pronouns(html: str) -> str:
    # Bundler artifact in EN ateliers copy; Ouili Nana uses he/him elsewhere.
    html = re.sub(
        r"creative process and the .{1,48}? of Cherche en [Cc]orps\.?",
        "creative process and the making of Cherche en Corps.",
        html,
    )
    return html


def head_block(page: str, lang: str, styles: str) -> str:
    meta = PAGE_META[page][lang]
    slug = page.replace(".html", "")
    if slug == "index":
        path = "/" if lang == "fr" else "/en/"
    else:
        path = f"/{slug}" if lang == "fr" else f"/en/{slug}"
    canonical = SITE_URL + path
    alt_fr = SITE_URL + (f"/{slug}" if slug != "index" else "/")
    alt_en = SITE_URL + (f"/en/{slug}" if slug != "index" else "/en/")
    if page == "fleur.html":
        og_image = FLEUR_OG
    else:
        og_image = f"{SITE_URL}/assets/images/og-default.webp"
    lang_attr = "fr" if lang == "fr" else "en"
    return f"""<!DOCTYPE html>
<html lang="{lang_attr}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{meta["title"]}</title>
  <meta name="description" content="{meta["description"]}">
  <link rel="canonical" href="{canonical}">
  <link rel="alternate" hreflang="fr" href="{alt_fr}">
  <link rel="alternate" hreflang="en" href="{alt_en}">
  <link rel="alternate" hreflang="x-default" href="{alt_fr}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Compagnie THT">
  <meta property="og:title" content="{meta["title"]}">
  <meta property="og:description" content="{meta["description"]}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{og_image}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{meta["title"]}">
  <meta name="twitter:description" content="{meta["description"]}">
  <meta name="twitter:image" content="{og_image}">
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
  <script type="application/ld+json">{json.dumps({
        "@context": "https://schema.org",
        "@type": "PerformingGroup",
        "name": "Compagnie THT",
        "alternateName": "Trois Heures Trente",
        "url": SITE_URL,
        "email": "contact@trois-heures-trente.com",
        "sameAs": [
            "https://www.instagram.com/compagnie_tht/",
            "https://www.youtube.com/@THTCompagnie",
            "https://www.linkedin.com/company/compagnie-tht/",
        ],
    }, ensure_ascii=False)}</script>
  <style>{styles}
  @media (max-width: 900px) {{
    [data-screen-label] {{ min-width: 0 !important; }}
    div[style*="min-width:1100px"] {{ min-width: 0 !important; }}
  }}
  </style>
</head>
<body>
"""


def build_page(page: str, lang: str, body: str, styles: str) -> str:
    html = strip_react_artifacts(body)
    html = fix_internal_links(html, lang, page)
    html = fix_wp_urls(html)
    html = fix_newsletter(html, lang)
    if page == "cherche-en-corps.html":
        html = fix_cherche_videos(html, lang)
    elif page == "index.html":
        html = re.sub(
            r'(<a href="/fleur"[^>]*><img src=")[^"]+(" alt="FLEUR")',
            rf'\1{FLEUR_DIR}/tile.webp\2',
            html,
        )
        html = html.replace(
            "▶ Cherche en Corps à San Francisco",
            "▶ Cherche en Corps — teaser",
        )
        html = html.replace(
            "▶ Cherche en Corps in San Francisco",
            "▶ Cherche en Corps — teaser",
        )
        html = html.replace(
            "https://www.youtube.com/watch?v=K9OICzieSfc",
            "https://www.youtube.com/watch?v=TjewwAOC488",
        )
    html = fix_dossier_links(html, page)
    html = fix_pronouns(html)
    if page == "fleur.html":
        html = apply_fleur_images(html)
    return head_block(page, lang, styles) + html + "\n</body>\n</html>\n"


def write_sitemap() -> None:
    urls = []
    for page in PAGES:
        slug = page.replace(".html", "")
        for lang in ("fr", "en"):
            if slug == "index":
                path = "/" if lang == "fr" else "/en/"
            else:
                path = f"/{slug}" if lang == "fr" else f"/en/{slug}"
            urls.append(f"  <url><loc>{SITE_URL}{path}</loc></url>")
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    (OUT / "sitemap.xml").write_text(content, encoding="utf-8")


def write_robots() -> None:
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n",
        encoding="utf-8",
    )


def main() -> int:
    LEGACY.mkdir(parents=True, exist_ok=True)
    for page in PAGES:
        src = OUT / page
        if src.exists() and not (LEGACY / page).exists():
            shutil.copy2(src, LEGACY / page)

    uuid_map = collect_assets()

    # Map hero/tile webp aliases from extracted files
    img_dir = ASSETS / "images"
    images = sorted(img_dir.glob("*.webp"))
    if images:
        # pick reasonable defaults by filename hints
        for im in images:
            n = im.name.lower()
            if "cherche" in n and "duo" in n:
                WP_REPLACEMENTS["https://www.trois-heures-trente.com/wp-content/uploads/2025/08/THT-241-scaled.jpg"] = f"/assets/images/{im.name}"
            if "cherche" in n and "san" in n:
                WP_REPLACEMENTS["https://www.trois-heures-trente.com/wp-content/uploads/2025/08/THT-329-scaled.jpg"] = f"/assets/images/{im.name}"
        hero = max(images, key=lambda p: p.stat().st_size)
        WP_REPLACEMENTS["https://www.trois-heures-trente.com/wp-content/uploads/2025/08/THT-114-scaled.jpg"] = f"/assets/images/{hero.name}"
        WP_REPLACEMENTS["https://www.trois-heures-trente.com/wp-content/uploads/2023/08/Ouili_fleur-63-scaled.jpg"] = f"/assets/images/{hero.name}"
        WP_REPLACEMENTS["https://www.trois-heures-trente.com/wp-content/uploads/2023/08/Ouili_fleur-52-2-scaled.jpg"] = f"/assets/images/{hero.name}"
        og = ASSETS / "images" / "og-default.webp"
        if not og.exists():
            shutil.copy2(hero, og)

    for page in PAGES:
        manifest, template = parse_bundle(LEGACY / page)
        _ = manifest
        styles = extract_helmet_styles(template)
        styles = replace_uuids(styles, uuid_map)
        fr_body, en_body = split_locales(template)
        fr_html = build_page(page, "fr", replace_uuids(fr_body, uuid_map), styles)
        en_html = build_page(page, "en", replace_uuids(en_body, uuid_map), styles)

        out_path = OUT / page if page != "index.html" else OUT / "index.html"
        out_path.write_text(fr_html, encoding="utf-8")
        en_dir = OUT / "en"
        en_dir.mkdir(exist_ok=True)
        en_name = "index.html" if page == "index.html" else page
        (en_dir / en_name).write_text(en_html, encoding="utf-8")

    write_sitemap()
    write_robots()

    raw_dir = ASSETS / "_raw"
    if raw_dir.exists():
        shutil.rmtree(raw_dir)

    print("Built static site.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
