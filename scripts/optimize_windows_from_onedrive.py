#!/usr/bin/env python3
"""Optimize WINDOWS photos (Photos JAY / OneDrive) into assets/images/windows/."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "images" / "windows"
TARGET_KB = 200
MAX_WIDTH = 1600

# Matches legacy WP hero slot (THT-114-scaled → THT-100.jpg; 114 not in Jay set)
FILES = [
    ("hero", "THT-100.jpg"),
    ("og-windows", "THT-100.jpg"),
    ("g01", "THT-1.jpg"),
    ("g02", "THT-23.jpg"),
    ("g03", "THT-26.jpg"),
    ("g04", "THT-101.jpg"),
    ("g05", "THT-190.jpg"),
    ("g06", "THT-220.jpg"),
    ("g07", "THT-250.jpg"),
    ("g08", "THT-278.jpg"),
]
TILE = "THT-103.jpg"


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
            print(f"{out.name}: {size // 1024} KB")
    tile_src = src_dir / TILE
    if not tile_src.exists():
        print(f"Missing {tile_src}", file=sys.stderr)
        return 1
    with Image.open(tile_src) as im:
        save_webp(im, OUT / "tile.webp")
    print(f"tile.webp: {(OUT / 'tile.webp').stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
