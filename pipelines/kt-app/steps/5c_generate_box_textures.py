"""
Step 5c: Generate Team Box Textures

Outputs per team:
  output/{team}/cardbox/{team}-card-box-texture.jpg   — UV texture (714×585, 6-sided)
  output/{team}/cardbox/{team}-card-box.obj           — 3-D box mesh (same for all teams)

Texture priority:
  1. config/teams/{team}/box/card-box-texture.jpg exists  → manual override (copy to output)
  2. layers/warcom/extracted/{team}/icons/{team}-icon-token.jpg exists  → auto-generate v2 texture
  3. neither → copy config/defaults/box/card-box-texture.jpg to output

The OBJ is always copied from config/defaults/box/card-box.obj (identical for every team).

Usage:
    python pipelines/kt-app/steps/5c_generate_box_textures.py
    python pipelines/kt-app/steps/5c_generate_box_textures.py --teams angels-of-death kasrkin
    python pipelines/kt-app/steps/5c_generate_box_textures.py --force   # skip override check
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import Optional, Set

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[3]

EXTRACTED_DIR   = PROJECT_ROOT / "layers" / "warcom" / "extracted"
OUTPUT_DIR      = PROJECT_ROOT / "output"
CONFIG_DIR      = PROJECT_ROOT / "config"
DEFAULTS_BOX    = CONFIG_DIR / "defaults" / "box"
BACKGROUND_PATH = DEFAULTS_BOX / "card-box-background.jpeg"

# ---------------------------------------------------------------------------
# UV layout constants (714×585 canvas)
# ---------------------------------------------------------------------------

CANVAS_W, CANVAS_H = 714, 585
FACE_TOP    = (130,   0, 227, 130)   # (x1, y1, w, h)
FACE_SIDE_A = (130, 130, 227, 325)

# ---------------------------------------------------------------------------
# Text config
# ---------------------------------------------------------------------------

FONT_SIZE  = 33
TEXT_COLOR = (220, 210, 185)         # off-white / cream

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
    bg = Image.open(path).convert("RGB")
    bw, bh = bg.size
    ratio = CANVAS_W / CANVAS_H
    if bw / bh > ratio:
        new_w = int(bh * ratio)
        x0 = (bw - new_w) // 2
        bg = bg.crop((x0, 0, x0 + new_w, bh))
    else:
        new_h = int(bw / ratio)
        y0 = (bh - new_h) // 2
        bg = bg.crop((0, y0, bw, y0 + new_h))
    return bg.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)


def _remove_dark_background(icon: Image.Image, threshold: int = 40) -> Image.Image:
    arr = np.array(icon.convert("RGB"))
    brightness = arr.max(axis=2)
    alpha = np.where(brightness < threshold, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([arr, alpha]), "RGBA")


def _wrap_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont,
               max_width: int) -> list[str]:
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
                         align_bottom: bool = False, bottom_margin: int = 12) -> None:
    lines = _wrap_text(draw, text, font, rw - 10)
    line_h = [draw.textbbox((0, 0), l, font=font)[3] for l in lines]
    line_w = [draw.textbbox((0, 0), l, font=font)[2] for l in lines]
    gap = 4
    total_h = sum(line_h) + gap * (len(lines) - 1)
    y_start = (ry + rh - total_h - bottom_margin) if align_bottom else (ry + (rh - total_h) // 2)
    for i, line in enumerate(lines):
        x = rx + (rw - line_w[i]) // 2
        draw.text((x, y_start), line, fill=color, font=font)
        y_start += line_h[i] + gap


def _paste_icon(canvas: Image.Image, icon_rgba: Image.Image,
                rx: int, ry: int, rw: int, rh: int,
                reserved_bottom: int = 48) -> None:
    iw, ih = icon_rgba.size
    avail_w = rw - 20
    avail_h = rh - reserved_bottom - 15
    scale = min(avail_w / iw, avail_h / ih, 1.0)
    new_w, new_h = int(iw * scale), int(ih * scale)
    icon_scaled = icon_rgba.resize((new_w, new_h), Image.LANCZOS)
    canvas.paste(icon_scaled, (rx + (rw - new_w) // 2, ry + 15),
                 mask=icon_scaled.split()[3])


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------

def generate_texture(team_slug: str, canonical_name: str,
                     background_path: Path, icon_path: Path,
                     output_path: Path) -> bool:
    try:
        canvas = _load_background(background_path).convert("RGBA")

        icon_rgba = None
        if icon_path.exists():
            icon_rgba = _remove_dark_background(Image.open(icon_path))
        else:
            print(f"  WARNING: icon not found: {icon_path}")

        display = canonical_name.title()

        rx, ry, rw, rh = FACE_SIDE_A
        if icon_rgba is not None:
            _paste_icon(canvas, icon_rgba, rx, ry, rw, rh, reserved_bottom=44)
        font = _load_font(FONT_SIZE)
        draw = ImageDraw.Draw(canvas)
        _draw_text_in_region(draw, display, rx, ry, rw, rh, font, TEXT_COLOR, align_bottom=True)

        rx, ry, rw, rh = FACE_TOP
        _draw_text_in_region(draw, display, rx, ry, rw, rh, font, TEXT_COLOR)

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
# Pipeline runner
# ---------------------------------------------------------------------------

def load_teams() -> list[tuple[str, dict]]:
    with open(CONFIG_DIR / "team-config.yaml") as f:
        return sorted(yaml.safe_load(f).get("teams", {}).items())


def has_token_icon(slug: str) -> bool:
    return (EXTRACTED_DIR / slug / "icons" / f"{slug}-icon-token.jpg").exists()


def run(team_filter: Optional[Set[str]] = None, force: bool = False) -> dict[str, int]:
    teams = load_teams()
    if team_filter:
        teams = [(s, d) for s, d in teams if s in team_filter]

    counts = {"generated": 0, "override": 0, "default": 0, "failed": 0}

    for slug, data in teams:
        canonical    = data.get("canonical_name", slug.replace("-", " ").title())
        out_dir      = OUTPUT_DIR / slug / "cardbox"
        out_texture  = out_dir / f"{slug}-card-box-texture.jpg"
        out_obj      = out_dir / f"{slug}-card-box.obj"
        override_tex = CONFIG_DIR / "teams" / slug / "box" / "card-box-texture.jpg"
        icon_path    = EXTRACTED_DIR / slug / "icons" / f"{slug}-icon-token.jpg"

        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DEFAULTS_BOX / "card-box.obj", out_obj)

        if not force and override_tex.exists():
            shutil.copy2(override_tex, out_texture)
            print(f"  [override]  {slug}")
            counts["override"] += 1

        elif has_token_icon(slug):
            print(f"  [generate]  {slug}")
            ok = generate_texture(slug, canonical, BACKGROUND_PATH, icon_path, out_texture)
            if ok:
                counts["generated"] += 1
            else:
                print(f"  WARNING: generation failed for {slug}, falling back to default")
                shutil.copy2(DEFAULTS_BOX / "card-box-texture.jpg", out_texture)
                counts["default"] += 1

        else:
            shutil.copy2(DEFAULTS_BOX / "card-box-texture.jpg", out_texture)
            print(f"  [default]   {slug}  (no token icon)")
            counts["default"] += 1

    return counts


def main():
    parser = argparse.ArgumentParser(description="Step 5c: Generate team box textures")
    parser.add_argument("--teams", nargs="+", metavar="TEAM", help="Specific teams to process")
    parser.add_argument(
        "--force", action="store_true",
        help="Re-generate even for teams with a manual override texture"
    )
    args = parser.parse_args()

    team_filter = set(args.teams) if args.teams else None

    print("=== Step 5c: Generate Box Textures ===")
    counts = run(team_filter, args.force)
    print(
        f"\nGenerated: {counts['generated']}"
        f"  Override (kept): {counts['override']}"
        f"  Default (no icon): {counts['default']}"
        f"  Failed: {counts['failed']}"
    )


if __name__ == "__main__":
    main()
