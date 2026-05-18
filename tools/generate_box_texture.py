#!/usr/bin/env python3
"""
Generate 6-sided card box textures (714x585 UV layout) for all Kill Team teams.

UV face layout (matching angels-of-death-card-box.obj):
  Canvas: 714 x 585
  TOP:    x=130,  y=0,   w=227, h=130  — team name centered
  END_A:  x=0,    y=130, w=130, h=325  — background only
  SIDE_A: x=130,  y=130, w=227, h=325  — icon (transparent bg) + team name
  END_B:  x=357,  y=130, w=130, h=325  — background only
  SIDE_B: x=487,  y=130, w=227, h=325  — background only
  BOTTOM: x=130,  y=455, w=227, h=130  — background only

Sources:
  Background : layers/warcom/extracted/_generic/generic-artwork-001.jpeg
  Icon       : layers/warcom/extracted/{team}/icons/{team}-icon-token.jpg
Output:
  config/teams/{team}/box/card-box-texture.jpg

Usage:
  python tools/generate_box_texture_v2.py              # all teams
  python tools/generate_box_texture_v2.py angels-of-death
  python tools/generate_box_texture_v2.py all
"""

import sys
import argparse
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

CANVAS_W, CANVAS_H = 714, 585

# (x1, y1, width, height) for each face
FACE_TOP    = (130,   0, 227, 130)
FACE_SIDE_A = (130, 130, 227, 325)

# ---------------------------------------------------------------------------
# Font / text config
# ---------------------------------------------------------------------------

FONT_SIZE = 33
TEXT_COLOR = (220, 210, 185)  # off-white / cream

# Try these fonts in order; first one that loads wins
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/cinzel/Cinzel-Regular.ttf",
    "C:/Windows/Fonts/Cinzel-Regular.ttf",
    "C:/Windows/Fonts/georgia.ttf",
    "C:/Windows/Fonts/Georgia.ttf",
    "C:/Windows/Fonts/times.ttf",
    "C:/Windows/Fonts/Times New Roman.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def _load_background(path: Path) -> Image.Image:
    """Load background, crop to 714:585 aspect ratio, resize to canvas."""
    bg = Image.open(path).convert("RGB")
    bw, bh = bg.size
    target_ratio = CANVAS_W / CANVAS_H
    if bw / bh > target_ratio:
        new_w = int(bh * target_ratio)
        x0 = (bw - new_w) // 2
        bg = bg.crop((x0, 0, x0 + new_w, bh))
    else:
        new_h = int(bw / target_ratio)
        y0 = (bh - new_h) // 2
        bg = bg.crop((0, y0, bw, y0 + new_h))
    return bg.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)


def _remove_dark_background(icon: Image.Image, threshold: int = 40) -> Image.Image:
    """Return RGBA image with near-black pixels made transparent."""
    arr = np.array(icon.convert("RGB"))
    brightness = arr.max(axis=2)           # per-pixel max(R,G,B)
    alpha = np.where(brightness < threshold, 0, 255).astype(np.uint8)
    rgba = np.dstack([arr, alpha])
    return Image.fromarray(rgba, "RGBA")


def _wrap_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont,
               max_width: int) -> list[str]:
    """Split text into lines that fit within max_width pixels."""
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        bb = draw.textbbox((0, 0), candidate, font=font)
        if bb[2] - bb[0] > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines or [text]


def _draw_text_in_region(draw: ImageDraw.Draw, text: str,
                         rx: int, ry: int, rw: int, rh: int,
                         font: ImageFont.FreeTypeFont, color: tuple,
                         align_bottom: bool = False, bottom_margin: int = 12):
    """Draw text (auto-wrapped) centered horizontally in a face region.

    align_bottom=True  → pin text to the bottom of the region.
    align_bottom=False → center text vertically in the region.
    """
    lines = _wrap_text(draw, text, font, rw - 10)
    line_h = [draw.textbbox((0, 0), l, font=font)[3] for l in lines]
    line_w = [draw.textbbox((0, 0), l, font=font)[2] for l in lines]
    gap = 4
    total_h = sum(line_h) + gap * (len(lines) - 1)

    if align_bottom:
        y_start = ry + rh - total_h - bottom_margin
    else:
        y_start = ry + (rh - total_h) // 2

    for i, line in enumerate(lines):
        x = rx + (rw - line_w[i]) // 2
        draw.text((x, y_start), line, fill=color, font=font)
        y_start += line_h[i] + gap


def _paste_icon(canvas: Image.Image, icon_rgba: Image.Image,
                rx: int, ry: int, rw: int, rh: int,
                reserved_bottom: int = 48) -> int:
    """Paste icon centred horizontally, top-aligned (with small margin).

    reserved_bottom: pixels at the bottom of the region reserved for text.
    Returns y-coordinate of the icon's bottom edge.
    """
    iw, ih = icon_rgba.size
    avail_w = rw - 20
    avail_h = rh - reserved_bottom - 15   # 15px top margin
    scale = min(avail_w / iw, avail_h / ih, 1.0)
    new_w, new_h = int(iw * scale), int(ih * scale)

    icon_scaled = icon_rgba.resize((new_w, new_h), Image.LANCZOS)
    paste_x = rx + (rw - new_w) // 2
    paste_y = ry + 15
    canvas.paste(icon_scaled, (paste_x, paste_y), mask=icon_scaled.split()[3])
    return paste_y + new_h   # bottom of icon


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------

def generate_texture(team_slug: str, canonical_name: str,
                     background_path: Path, icon_path: Path,
                     output_path: Path) -> bool:
    """Build and save the 714×585 box texture for one team."""
    try:
        # --- canvas ---
        canvas = _load_background(background_path).convert("RGBA")

        # --- icon ---
        icon_rgba = None
        if icon_path.exists():
            icon_rgba = _remove_dark_background(Image.open(icon_path))
        else:
            print(f"  WARNING: icon not found: {icon_path}")

        # --- team display name (Title Case) ---
        display = canonical_name.title()

        # --- SIDE_A: paste icon then draw name below it ---
        rx, ry, rw, rh = FACE_SIDE_A
        reserved = 44   # pixels for text at bottom
        if icon_rgba is not None:
            _paste_icon(canvas, icon_rgba, rx, ry, rw, rh,
                        reserved_bottom=reserved)
        font = _load_font(FONT_SIZE)
        draw = ImageDraw.Draw(canvas)
        _draw_text_in_region(draw, display, rx, ry, rw, rh, font, TEXT_COLOR,
                             align_bottom=True)

        # --- TOP: team name centered ---
        rx, ry, rw, rh = FACE_TOP
        _draw_text_in_region(draw, display, rx, ry, rw, rh, font, TEXT_COLOR)

        # --- save ---
        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert("RGB").save(str(output_path), "JPEG", quality=95)
        print(f"  OK  {output_path}")
        return True

    except Exception as exc:
        import traceback
        print(f"  ERROR: {exc}")
        traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate 6-sided card-box UV textures for Kill Team teams"
    )
    parser.add_argument(
        "team", nargs="?", default="all",
        help='Team slug, or "all" to process every team (default: all)'
    )
    parser.add_argument(
        "--base-dir", type=Path, default=None,
        help="Project root (default: parent of this script)"
    )
    parser.add_argument(
        "--background", type=Path, default=None,
        help="Override background image path"
    )
    args = parser.parse_args()

    base = args.base_dir or Path(__file__).resolve().parent.parent
    background = args.background or (
        base / "config" / "defaults" / "box" / "card-box-background.jpeg"
    )
    icons_dir  = base / "layers" / "warcom" / "extracted"
    output_dir = base / "output"
    config_path = base / "config" / "team-config.yaml"

    if not background.exists():
        print(f"ERROR: background not found: {background}")
        sys.exit(1)

    with open(config_path) as fh:
        teams: dict = yaml.safe_load(fh).get("teams", {})

    if args.team == "all":
        targets = list(teams.items())
    elif args.team in teams:
        targets = [(args.team, teams[args.team])]
    else:
        print(f"ERROR: unknown team '{args.team}'")
        print("Available:", ", ".join(sorted(teams)))
        sys.exit(1)

    ok = fail = 0
    for slug, data in targets:
        canonical = data.get("canonical_name", slug.replace("-", " ").title())
        icon_path  = icons_dir / slug / "icons" / f"{slug}-icon-token.jpg"
        out_path   = output_dir / slug / "cardbox" / f"{slug}-card-box-texture.jpg"
        print(f"[{slug}]")
        if generate_texture(slug, canonical, background, icon_path, out_path):
            ok += 1
        else:
            fail += 1

    if len(targets) > 1:
        print(f"\nDone: {ok} OK, {fail} failed")


if __name__ == "__main__":
    main()
