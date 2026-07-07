"""Dice textures — one-off per team, derived from the artwork layer. TTS-only.

layers/integration/{team}/artwork/icons + config (+ tokens for team colours)
   ->  output/{team}/dice/{team}-dice-{light,dark,team}.jpg

Three variants per team:
  - light: fixed orange-on-light background   (always generated)
  - dark:  fixed white-on-dark background      (always generated)
  - team:  team colours + team icon on face 6. Priority:
             1. config/teams/{team}/dice/dice.jpg  -> copy as-is
             2. dice_back_color / dice_front_color in team-config.yaml
             3. auto-extract colours from output/{team}/tokens/*.png
           If none available, the team variant is skipped.

PORT-FROM: pipelines/kt-app/steps/5b_generate_dice.py
SOURCE-DECISION: source-agnostic — drives off the shared artwork icon; the team
  variant reuses the tokens produced by ``extract_tokens`` (run tokens first).
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from ..utils import paths, team_config
from ..utils.state import StateIndex, StateManager

logger = logging.getLogger(__name__)

# Dice texture layout constants (matches warcom 4a_generate_dice.py)
FACE_SIZE = 630
CONTENT_SIZE = 567
CONTENT_OFFSET = (FACE_SIZE - CONTENT_SIZE) // 2

FACE_COORDS = {
    1: (20, 1403),
    2: (20, 711),
    3: (711, 1403),
    4: (711, 711),
    5: (1399, 711),
    6: (1399, 1403),
}

RGB = Tuple[int, int, int]

DICE_DEFAULTS = paths.DEFAULTS / "dice"


def _recolor_image(image_rgba: np.ndarray, color: RGB) -> np.ndarray:
    result = image_rgba.copy()
    for c in range(3):
        result[:, :, c] = np.where(image_rgba[:, :, 3] > 0, color[c], 0)
    return result


def _paste_dots(canvas: Image.Image, face_num: int, dots_dir: Path,
                dot_color: Optional[RGB]) -> None:
    dots = Image.open(dots_dir / f"dots-{face_num}.png").convert("RGBA")
    arr = np.array(dots)
    if dot_color:
        arr = _recolor_image(arr, dot_color)
    scaled = Image.fromarray(arr).resize((CONTENT_SIZE, CONTENT_SIZE), Image.Resampling.LANCZOS)
    fx, fy = FACE_COORDS[face_num]
    canvas.paste(scaled, (fx + CONTENT_OFFSET, fy + CONTENT_OFFSET), scaled)


def _generate_dice_texture(bg_path: Path, dots_dir: Path, icon_path: Optional[Path],
                           output_path: Path, bg_color: Optional[RGB] = None,
                           dot_color: Optional[RGB] = None) -> None:
    bg = Image.open(bg_path).convert("RGB")
    if bg_color:
        arr = np.array(bg).astype(np.float32)
        tinted = (arr * 0.15 + np.array(bg_color) * 0.85).astype(np.uint8)
        bg = Image.fromarray(tinted)

    for face_num in range(1, 6):
        _paste_dots(bg, face_num, dots_dir, dot_color)

    fx, fy = FACE_COORDS[6]
    paste_pos = (fx + CONTENT_OFFSET, fy + CONTENT_OFFSET)
    placed_icon = False

    if icon_path and icon_path.exists():
        icon_bgra = cv2.imread(str(icon_path), cv2.IMREAD_UNCHANGED)
        if icon_bgra is not None and icon_bgra.ndim == 3 and icon_bgra.shape[2] == 4:
            icon_rgba = cv2.cvtColor(icon_bgra, cv2.COLOR_BGRA2RGBA)
            arr = _recolor_image(np.array(icon_rgba), dot_color) if dot_color else np.array(icon_rgba)
            icon = Image.fromarray(arr).resize((CONTENT_SIZE, CONTENT_SIZE), Image.Resampling.LANCZOS)
            bg.paste(icon, paste_pos, icon)
            placed_icon = True

    if not placed_icon:
        _paste_dots(bg, 5, dots_dir, dot_color)  # face 6 falls back to dots-5 pattern

    output_path.parent.mkdir(parents=True, exist_ok=True)
    bg.save(output_path, "JPEG", quality=95)


def _extract_token_colors(tokens_dir: Path) -> Optional[Tuple[RGB, RGB]]:
    files = sorted(tokens_dir.glob("*.png"))
    if not files:
        return None

    bg_px, all_px = [], []
    for f in files:
        arr = np.array(Image.open(f).convert("RGBA"))
        alpha = arr[:, :, 3] > 128
        if not alpha.any():
            continue
        h, w = arr.shape[:2]
        ys, xs = np.where(alpha)
        y0, y1 = int(ys.min()), int(ys.max())
        x0, x1 = int(xs.min()), int(xs.max())
        bh, bw = y1 - y0, x1 - x0
        cy, cx = (y0 + y1) / 2.0, (x0 + x1) / 2.0
        Y, X = np.mgrid[0:h, 0:w].astype(np.float32)
        norm_dist = np.sqrt(
            ((Y - cy) / (bh / 2.0 + 1)) ** 2 + ((X - cx) / (bw / 2.0 + 1)) ** 2
        )
        bg_mask = alpha & (norm_dist > 0.65)
        all_px.append(arr[alpha, :3])
        if bg_mask.any():
            bg_px.append(arr[bg_mask, :3])

    if not all_px:
        return None

    source = bg_px if bg_px else all_px
    bg_color = np.vstack(source).astype(np.float32).mean(axis=0)
    all_pixels = np.vstack(all_px).astype(np.float32)
    dist = ((all_pixels - bg_color) ** 2).sum(axis=1)
    threshold = np.percentile(dist, 80)
    dot_color = all_pixels[dist >= threshold].mean(axis=0)

    to_rgb = lambda v: tuple(int(x) for x in v.astype(int))
    return to_rgb(bg_color), to_rgb(dot_color)


def _icon_path(team: str) -> Path:
    return paths.artwork_team_dir(team) / "icons" / f"{team}-icon-token-transparent.png"


def _process_team(team: str, team_cfg: dict) -> dict:
    results = {"light": False, "dark": False, "team": False}
    dice_out = paths.team_output(team) / "dice"
    icon_path = _icon_path(team)

    light_bg = DICE_DEFAULTS / "light" / "background.jpeg"
    dark_bg = DICE_DEFAULTS / "dark" / "background.jpeg"
    light_dots = DICE_DEFAULTS / "light"
    dark_dots = DICE_DEFAULTS / "dark"
    team_bg = DICE_DEFAULTS / "team_template" / "background.jpg"
    team_dots = DICE_DEFAULTS / "team_template"

    try:
        _generate_dice_texture(light_bg, light_dots, icon_path, dice_out / f"{team}-dice-light.jpg")
        results["light"] = True
    except Exception as e:
        logger.warning(f"  {team}: light dice failed: {e}")

    try:
        _generate_dice_texture(dark_bg, dark_dots, icon_path, dice_out / f"{team}-dice-dark.jpg")
        results["dark"] = True
    except Exception as e:
        logger.warning(f"  {team}: dark dice failed: {e}")

    team_out = dice_out / f"{team}-dice-team.jpg"
    config_override = paths.team_config_dir(team) / "dice" / "dice.jpg"

    if config_override.exists():
        team_out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config_override, team_out)
        logger.info(f"  {team}: team dice from config override")
        results["team"] = True
    else:
        bg_color = team_cfg.get("dice_back_color")
        dot_color = team_cfg.get("dice_front_color")
        if bg_color:
            bg_color = tuple(bg_color)
        if dot_color:
            dot_color = tuple(dot_color)

        if not (bg_color and dot_color):
            tokens_dir = paths.team_output(team) / "tokens"
            if tokens_dir.exists():
                extracted = _extract_token_colors(tokens_dir)
                if extracted:
                    bg_color, dot_color = extracted

        if bg_color and dot_color:
            try:
                _generate_dice_texture(team_bg, team_dots, icon_path, team_out, bg_color, dot_color)
                logger.info(f"  {team}: team dice bg={list(bg_color)} dots={list(dot_color)}")
                results["team"] = True
            except Exception as e:
                logger.warning(f"  {team}: team dice failed: {e}")
        else:
            if team_out.exists():
                team_out.unlink()
            logger.info(f"  {team}: team dice skipped (no tokens/colours)")

    return results


def get_all_teams() -> list[str]:
    """All integration teams that have a transparent token icon for face 6."""
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
        return {"light": 0, "dark": 0, "team": 0}

    logger.info(f"generate_dice: {len(teams)} team(s)")

    counts = {"light": 0, "dark": 0, "team": 0, "skipped": 0}
    for team in teams:
        cfg = team_config.team_data(team)
        logger.info(f"[{team}]")

        state = StateManager(team)
        inputs = [
            _icon_path(team),
            paths.TEAM_CONFIG,
            paths.team_config_dir(team) / "dice" / "dice.jpg",
        ]
        if state.can_skip("generate_dice", inputs, force):
            logger.info("  unchanged, skip")
            counts["skipped"] += 1
            continue

        results = _process_team(team, cfg)
        for k in ("light", "dark", "team"):
            if results[k]:
                counts[k] += 1

        dice_out = paths.team_output(team) / "dice"
        for variant in ("light", "dark", "team"):
            f = dice_out / f"{team}-dice-{variant}.jpg"
            if f.exists():
                state.record_output("generate_dice", f"dice-{variant}.jpg", f)
        state.record_inputs("generate_dice", inputs)
        state.mark_complete("generate_dice")
        state.save()

    StateIndex().rebuild_and_save()
    logger.info(
        f"generate_dice done: light={counts['light']} dark={counts['dark']} "
        f"team={counts['team']} skipped={counts['skipped']}"
    )
    return counts
