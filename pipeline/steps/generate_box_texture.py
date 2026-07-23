"""Box texture — one-off per team, derived from the artwork layer. TTS-only.

layers/integration/{team}/artwork/icons/{team}-icon-token.jpg + config
   ->  output/{team}/cardbox/{team}-card-box-texture.jpg (+ {team}-card-box.obj)

Texture priority:
  1. config/teams/{team}/box/card-box-texture.jpg  -> manual override (copied)
  2. team token icon present                        -> auto-generate v2 texture
  3. neither                                        -> copy the global default texture
The OBJ is always copied from config/defaults/box/card-box.obj (identical per team).

Source-agnostic — drives off the shared artwork icon.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..utils import paths, team_config
from ..utils.stable_io import stable_write
from ..utils.state import StateIndex, StateManager

logger = logging.getLogger(__name__)

DEFAULTS_BOX = paths.DEFAULTS / "box"
BACKGROUND_PATH = DEFAULTS_BOX / "card-box-background.jpeg"

# UV layout constants (714×585 canvas)
CANVAS_W, CANVAS_H = 714, 585
FACE_TOP = (130, 0, 227, 130)      # (x1, y1, w, h)
FACE_SIDE_A = (130, 130, 227, 325)

# Text config
FONT_SIZE = 33
TEXT_COLOR = (220, 210, 185)       # off-white / cream

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
# Image helpers (verbatim from the legacy step)
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


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
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


def _draw_text_in_region(draw: ImageDraw.ImageDraw, text: str,
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


def _generate_texture(canonical_name: str, background_path: Path,
                      icon_path: Path, output_path: Path) -> bool:
    try:
        canvas = _load_background(background_path).convert("RGBA")

        icon_rgba = None
        if icon_path.exists():
            icon_rgba = _remove_dark_background(Image.open(icon_path))
        else:
            logger.warning(f"  icon not found: {icon_path}")

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
        with stable_write(output_path):
            canvas.convert("RGB").save(str(output_path), "JPEG", quality=95)
        logger.info(f"  OK  {output_path.name}")
        return True
    except Exception as exc:
        logger.error(f"  ERROR generating box texture: {exc}")
        return False


def _icon_path(team: str) -> Path:
    return paths.artwork_team_dir(team) / "icons" / f"{team}-icon-token.jpg"


def get_all_teams() -> list[str]:
    """All integration teams (texture falls back to default when no icon exists)."""
    if not paths.INTEGRATION.exists():
        return []
    return sorted(
        d.name for d in paths.INTEGRATION.iterdir()
        if d.is_dir() and (d / "artwork").exists()
    )


def run(teams: Optional[list] = None, source=None, force: bool = False):
    """Orchestrator entry point. Shared step — ``source`` is ignored."""
    if teams is None:
        teams = get_all_teams()
    if not teams:
        logger.error("No integration teams found (run extract_artwork first)")
        return {"generated": 0, "override": 0, "default": 0, "failed": 0}

    logger.info(f"generate_box_texture: {len(teams)} team(s)")

    counts = {"generated": 0, "override": 0, "default": 0, "failed": 0, "skipped": 0}
    for team in teams:
        canonical = team_config.canonical_name(team)
        out_dir = paths.team_output(team) / "cardbox"
        out_texture = out_dir / f"{team}-card-box-texture.jpg"
        out_obj = out_dir / f"{team}-card-box.obj"
        override_tex = paths.team_config_dir(team) / "box" / "card-box-texture.jpg"
        icon_path = _icon_path(team)

        state = StateManager(team)
        inputs = [
            icon_path,
            override_tex,
            paths.TEAM_CONFIG,
            DEFAULTS_BOX / "card-box.obj",
            DEFAULTS_BOX / "card-box-texture.jpg",
        ]
        if state.can_skip("generate_box_texture", inputs, force):
            logger.info(f"  [skip]      {team}  (unchanged)")
            counts["skipped"] += 1
            continue

        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DEFAULTS_BOX / "card-box.obj", out_obj)

        if not force and override_tex.exists():
            shutil.copy2(override_tex, out_texture)
            logger.info(f"  [override]  {team}")
            counts["override"] += 1
        elif icon_path.exists():
            logger.info(f"  [generate]  {team}")
            if _generate_texture(canonical, BACKGROUND_PATH, icon_path, out_texture):
                counts["generated"] += 1
            else:
                logger.warning(f"  generation failed for {team}, falling back to default")
                shutil.copy2(DEFAULTS_BOX / "card-box-texture.jpg", out_texture)
                counts["default"] += 1
        else:
            shutil.copy2(DEFAULTS_BOX / "card-box-texture.jpg", out_texture)
            logger.info(f"  [default]   {team}  (no token icon)")
            counts["default"] += 1

        state.record_output("generate_box_texture", "card-box-texture.jpg", out_texture)
        state.record_output("generate_box_texture", "card-box.obj", out_obj)
        state.record_inputs("generate_box_texture", inputs)
        state.mark_complete("generate_box_texture")
        state.save()

    StateIndex().rebuild_and_save()
    logger.info(
        f"generate_box_texture done: generated={counts['generated']} "
        f"override={counts['override']} default={counts['default']} "
        f"skipped={counts['skipped']} failed={counts['failed']}"
    )
    return counts
