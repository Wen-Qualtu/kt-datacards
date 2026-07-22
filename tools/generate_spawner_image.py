"""Generate the Kill Team Spawner overview image (cosmetic team list).

Renders ``output/_generic-tts-objects/team-spawner-image.png`` — the static
picture shown on the in-game "Kill Team Spawner" tile. It lists every team the
spawner offers, in alphabetical order, across four columns.

The team list is read from ``config/team-config.yaml`` (single source of truth),
so adding a team to the config and re-running this keeps the image in sync (team
count, numbering and the "1-N" footer all update automatically).

Run:  python -m tools.generate_spawner_image
"""
from __future__ import annotations

import math
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TEAM_CONFIG = ROOT / "config" / "team-config.yaml"
OUTPUT = ROOT / "output" / "_generic-tts-objects" / "team-spawner-image.png"

# Canvas + style (measured from the existing asset so the look is unchanged).
CANVAS_W, CANVAS_H = 1400, 504
BG = (20, 20, 30)
TITLE_COLOR = (220, 220, 234)
BODY_COLOR = (214, 214, 228)
SEP_COLOR = (60, 60, 74)
FOOTER_COLOR = (91, 162, 230)

COLUMN_X = (51, 375, 700, 1025)
ROW_START_Y = 160
ROW_DY = 22
NUM_COLUMNS = 4

_SANS_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in _SANS_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _team_names() -> list[str]:
    data = yaml.safe_load(TEAM_CONFIG.read_text(encoding="utf-8"))
    names = [v.get("canonical_name", "") for v in data.get("teams", {}).values()]
    return sorted(n for n in names if n)


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, y: int,
                   font: ImageFont.FreeTypeFont, color: tuple) -> None:
    x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=font)
    draw.text(((CANVAS_W - (x1 - x0)) / 2, y), text, font=font, fill=color)


def generate() -> Path:
    names = _team_names()
    n = len(names)
    per_col = math.ceil(n / NUM_COLUMNS)

    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
    draw = ImageDraw.Draw(img)

    title_font = _font(30)
    body_font = _font(18)
    footer_font = _font(15)

    _draw_centered(draw, f"\U0001F3AF KILL TEAM SPAWNER - ALL {n} TEAMS \U0001F3AF",
                   28, title_font, TITLE_COLOR)
    draw.line([(55, 90), (CANVAS_W - 55, 90)], fill=SEP_COLOR, width=2)

    for idx, name in enumerate(names):
        col = idx // per_col
        row = idx % per_col
        x = COLUMN_X[col]
        y = ROW_START_Y + row * ROW_DY
        draw.text((x, y), f"{idx + 1}. {name}", font=body_font, fill=BODY_COLOR)

    _draw_centered(draw, "Click the 'Spawn Team' button above to select a team",
                   448, footer_font, FOOTER_COLOR)
    _draw_centered(draw, f"Enter team number (1-{n}) or partial name (e.g., 'kasrkin', 'death')",
                   470, footer_font, FOOTER_COLOR)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    out = generate()
    print(f"Wrote {out}")
