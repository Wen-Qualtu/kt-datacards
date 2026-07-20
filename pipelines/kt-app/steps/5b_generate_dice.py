"""
Step 5b: Generate Dice Textures

Generates Tabletop Simulator dice textures for each team.
Runs after Step 5 (token extraction) so token images are available for color
extraction. Outputs are consumed by Step 7 (TTS objects) which adds a dice bag
to the team box.

Three variants per team:
  - light: fixed orange-on-light background  (always generated)
  - dark:  fixed white-on-dark background    (always generated)
  - team:  team colors extracted from tokens, team icon on face 6
           Priority order:
             1. config/teams/{team}/dice/dice.jpg  -> copy as-is
             2. dice_back_color / dice_front_color in team-config.yaml
             3. auto-extract colors from output/{team}/tokens/*.png
             If none available, team variant is skipped.

Icons are read from layers/warcom/extracted/{team}/icons/{team}-icon-token-transparent.png.
If no icon exists, face 6 uses dots-5 instead.

Input:
    output/{team}/tokens/*.png                            (for color extraction)
    layers/warcom/extracted/{team}/icons/                 (for team icon on face 6)
    config/teams/{team}/dice/dice.jpg                     (optional override)
    config/team-config.yaml                               (dice color overrides)
    config/defaults/dice/{light,dark,team_template}/      (background + dot assets)

Output:
    output/{team}/dice/{team}-dice-light.jpg
    output/{team}/dice/{team}-dice-dark.jpg
    output/{team}/dice/{team}-dice-team.jpg               (if source available)
"""

import argparse
import logging
import shutil
import yaml
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[3]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
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


def load_team_config() -> dict:
    path = PROJECT_ROOT / "config" / "team-config.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f).get("teams", {})


def recolor_image(image_rgba: np.ndarray, color: RGB) -> np.ndarray:
    result = image_rgba.copy()
    for c in range(3):
        result[:, :, c] = np.where(image_rgba[:, :, 3] > 0, color[c], 0)
    return result


def paste_dots(canvas: Image.Image, face_num: int, dots_dir: Path, dot_color: Optional[RGB]) -> None:
    dots = Image.open(dots_dir / f"dots-{face_num}.png").convert("RGBA")
    arr = np.array(dots)
    if dot_color:
        arr = recolor_image(arr, dot_color)
    scaled = Image.fromarray(arr).resize((CONTENT_SIZE, CONTENT_SIZE), Image.Resampling.LANCZOS)
    fx, fy = FACE_COORDS[face_num]
    canvas.paste(scaled, (fx + CONTENT_OFFSET, fy + CONTENT_OFFSET), scaled)


def generate_dice_texture(
    bg_path: Path,
    dots_dir: Path,
    icon_path: Optional[Path],
    output_path: Path,
    bg_color: Optional[RGB] = None,
    dot_color: Optional[RGB] = None,
) -> None:
    bg = Image.open(bg_path).convert("RGB")
    if bg_color:
        arr = np.array(bg).astype(np.float32)
        tinted = (arr * 0.15 + np.array(bg_color) * 0.85).astype(np.uint8)
        bg = Image.fromarray(tinted)

    for face_num in range(1, 6):
        paste_dots(bg, face_num, dots_dir, dot_color)

    fx, fy = FACE_COORDS[6]
    paste_pos = (fx + CONTENT_OFFSET, fy + CONTENT_OFFSET)
    placed_icon = False

    if icon_path and icon_path.exists():
        icon_bgra = cv2.imread(str(icon_path), cv2.IMREAD_UNCHANGED)
        if icon_bgra is not None and icon_bgra.ndim == 3 and icon_bgra.shape[2] == 4:
            icon_rgba = cv2.cvtColor(icon_bgra, cv2.COLOR_BGRA2RGBA)
            arr = recolor_image(np.array(icon_rgba), dot_color) if dot_color else np.array(icon_rgba)
            icon = Image.fromarray(arr).resize((CONTENT_SIZE, CONTENT_SIZE), Image.Resampling.LANCZOS)
            bg.paste(icon, paste_pos, icon)
            placed_icon = True

    if not placed_icon:
        paste_dots(bg, 5, dots_dir, dot_color)  # face 6 falls back to dots-5 pattern

    output_path.parent.mkdir(parents=True, exist_ok=True)
    bg.save(output_path, "JPEG", quality=95)


def extract_token_colors(tokens_dir: Path) -> Optional[Tuple[RGB, RGB]]:
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


def process_team(team: str, team_cfg: dict) -> dict:
    results = {"light": False, "dark": False, "team": False}
    dice_out = PROJECT_ROOT / "output" / team / "dice"
    icon_path = (
        PROJECT_ROOT / "layers" / "warcom" / "extracted" / team / "icons"
        / f"{team}-icon-token-transparent.png"
    )

    light_bg = PROJECT_ROOT / "config" / "defaults" / "dice" / "light" / "background.jpeg"
    dark_bg  = PROJECT_ROOT / "config" / "defaults" / "dice" / "dark"  / "background.jpeg"
    light_dots = PROJECT_ROOT / "config" / "defaults" / "dice" / "light"
    dark_dots  = PROJECT_ROOT / "config" / "defaults" / "dice" / "dark"
    team_bg    = PROJECT_ROOT / "config" / "defaults" / "dice" / "team_template" / "background.jpg"
    team_dots  = PROJECT_ROOT / "config" / "defaults" / "dice" / "team_template"

    # Light dice (fixed orange-on-light, no color params needed)
    try:
        generate_dice_texture(light_bg, light_dots, icon_path, dice_out / f"{team}-dice-light.jpg")
        results["light"] = True
    except Exception as e:
        logger.warning(f"  {team}: light dice failed: {e}")

    # Dark dice (fixed white-on-dark)
    try:
        generate_dice_texture(dark_bg, dark_dots, icon_path, dice_out / f"{team}-dice-dark.jpg")
        results["dark"] = True
    except Exception as e:
        logger.warning(f"  {team}: dark dice failed: {e}")

    # Team dice
    team_out = dice_out / f"{team}-dice-team.jpg"
    config_override = PROJECT_ROOT / "config" / "teams" / team / "dice" / "dice.jpg"

    if config_override.exists():
        team_out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config_override, team_out)
        logger.info(f"  {team}: team dice from config override")
        results["team"] = True
    else:
        # Determine colors: team-config override takes priority over auto-extraction
        bg_color = team_cfg.get("dice_back_color")
        dot_color = team_cfg.get("dice_front_color")
        if bg_color:
            bg_color = tuple(bg_color)
        if dot_color:
            dot_color = tuple(dot_color)

        if not (bg_color and dot_color):
            tokens_dir = PROJECT_ROOT / "output" / team / "tokens"
            if tokens_dir.exists():
                extracted = extract_token_colors(tokens_dir)
                if extracted:
                    bg_color, dot_color = extracted

        if bg_color and dot_color:
            try:
                generate_dice_texture(team_bg, team_dots, icon_path, team_out, bg_color, dot_color)
                logger.info(f"  {team}: team dice bg={list(bg_color)} dots={list(dot_color)}")
                results["team"] = True
            except Exception as e:
                logger.warning(f"  {team}: team dice failed: {e}")
        else:
            if team_out.exists():
                team_out.unlink()
            logger.info(f"  {team}: team dice skipped (no tokens/colors)")

    return results


def run(teams: list) -> dict:
    team_config = load_team_config()
    total = len(teams)
    counts = {"light": 0, "dark": 0, "team": 0}

    for i, team in enumerate(teams, 1):
        cfg = team_config.get(team, {})
        name = cfg.get("canonical_name", team)
        logger.info(f"[{i}/{total}] {name}")
        results = process_team(team, cfg)
        for k in counts:
            if results[k]:
                counts[k] += 1

    return counts


def main():
    parser = argparse.ArgumentParser(description="Step 9: Generate dice textures")
    parser.add_argument("--teams", help="Comma-separated team slugs (default: all with output/)")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Step 5b: Generate Dice Textures")
    logger.info("=" * 70)

    if args.teams:
        teams = [t.strip() for t in args.teams.split(",")]
    else:
        output_dir = PROJECT_ROOT / "output"
        teams = sorted(d.name for d in output_dir.iterdir() if d.is_dir() and (d / "cards").exists())

    logger.info(f"Teams: {len(teams)}")
    counts = run(teams)

    logger.info("")
    logger.info("=" * 70)
    logger.info("Step 5b Complete!")
    logger.info(f"  light: {counts['light']}  dark: {counts['dark']}  team: {counts['team']}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
