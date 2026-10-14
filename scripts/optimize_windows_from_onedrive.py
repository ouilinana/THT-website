#!/usr/bin/env python3
"""Optimize WINDOWS photos (Photos JAY) into assets/images/windows/.

Sources match legacy WP filenames THT-{114,241,329}-scaled via Jay folder name or phash
against bundled-page extracts (Wayback unavailable).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "images" / "windows"
TARGET_KB = 200
MAX_WIDTH = 1600

# WP THT-329-scaled → windows hero + gallery slot 3
# WP THT-114-scaled → home hero + gallery slot 1
# WP THT-241-scaled → home tile + gallery slot 2
FILES = [
    ("hero", "THT-199.jpg"),  # THT-329-scaled (phash → san-francisco extract)
    ("og-windows", "THT-199.jpg"),
    ("g01", "THT-266.jpg"),  # THT-114-scaled
    ("g02", "THT-241.jpg"),  # THT-241-scaled (exact filename)
    ("g03", "THT-199.jpg"),  # THT-329-scaled (gallery repeat)
]
TILE = "THT-241.jpg"


def save_webp(im: Image.Image, dest: Path, target_kb: int = TARGET_KB) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    im = im.convert("RGB") if im.mode in ("RGBA", "P") else im
    w, h = im.size
    if w > MAX_WIDTH:
        im = im.resize((MAX_WIDTH, int(h * MAX_WIDTH / w)), Image.Resampling.LANCZOS)
    for q in (82, 78, 72, 65, 58, 50):
        im.save(dest, "WEBP", quality=q, method=6)
        if dest.stat().st_size <= target_kb * 1024:
            return dest.stat().st_size
    return dest.stat().st_size


def main() -> int:
    src_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/windows-photos-jay")
    if not src_dir.is_dir():
        print(f"Missing source dir: {src_dir}", file=sys.stderr)
        return 1
    for slug, name in FILES:
        src = src_dir / name
        if not src.exists():
            print(f"Missing {src}", file=sys.stderr)
            return 1
        with Image.open(src) as im:
            out = OUT / f"{slug}.webp"
            size = save_webp(im, out)
            print(f"{out.name} ← {name}: {size // 1024} KB")
    with Image.open(src_dir / TILE) as im:
        save_webp(im, OUT / "tile.webp")
    print(f"tile.webp ← {TILE}: {(OUT / 'tile.webp').stat().st_size // 1024} KB")
    for extra in OUT.glob("g0*.webp"):
        if extra.name not in {f"g0{i}.webp" for i in range(1, 4)}:
            extra.unlink()
            print(f"removed {extra.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
