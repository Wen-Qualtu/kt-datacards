"""
Generate (or clean up) team dice textures.

Priority order per team:
  1. config/teams/{team}/dice/dice.jpg exists  → copy it as the team texture
  2. output/{team}/tokens/*.png exist          → extract colors, render texture
  3. Neither                                   → remove any stale team dice file

Light and dark dice are handled separately by pipelines/warcom/steps/4a_generate_dice.py.

Usage:
    python script/generate_team_dice.py --team battleclade
    python script/generate_team_dice.py --team battleclade --first-token
    python script/generate_team_dice.py --all
"""
import argparse
import logging
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict

import cv2
import numpy as np
import yaml
from PIL import Image

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Dice texture layout constants (matches 4a_generate_dice.py)
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

TEAM_BG = Path('config/defaults/dice/team_template/background.jpg')
TEAM_DOTS_DIR = Path('config/defaults/dice/team_template')
EXTRACTED_DIR = Path('layers/warcom/extracted')
CONFIG_TEAMS_DIR = Path('config/teams')

RGB = Tuple[int, int, int]


def load_team_config() -> Dict:
    with open('config/team-config.yaml', encoding='utf-8') as f:
        return yaml.safe_load(f).get('teams', {})


def extract_token_colors(
    tokens_dir: Path,
    first_token_only: bool = False,
) -> Optional[Tuple[RGB, RGB]]:
    """
    Extract background and dot colors from token PNG images.

    Background: average of outer-ring pixels (normalised ellipse distance > 0.65).
    Dot color:  average of top-20 % pixels most distant from the background color.

    Returns (background_color, dot_color) as RGB tuples, or None if no tokens found.
    """
    files = sorted(tokens_dir.glob('*.png'))
    if not files:
        return None
    if first_token_only:
        files = files[:1]

    bg_px = []
    all_px = []

    for f in files:
        arr = np.array(Image.open(f).convert('RGBA'))
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
            ((Y - cy) / (bh / 2.0 + 1)) ** 2 +
            ((X - cx) / (bw / 2.0 + 1)) ** 2
        )
        bg_mask = alpha & (norm_dist > 0.65)

        all_px.append(arr[alpha, :3])
        if bg_mask.any():
            bg_px.append(arr[bg_mask, :3])

    if not all_px:
        return None

    # Background = outer-ring average
    source = bg_px if bg_px else all_px
    bg_color = np.vstack(source).astype(np.float32).mean(axis=0)

    # Dot color = pixels most different from background (top 20 % by L2 distance)
    all_pixels = np.vstack(all_px).astype(np.float32)
    dist = ((all_pixels - bg_color) ** 2).sum(axis=1)
    threshold = np.percentile(dist, 80)
    dot_color = all_pixels[dist >= threshold].mean(axis=0)

    to_rgb = lambda v: tuple(int(x) for x in v.astype(int))
    return to_rgb(bg_color), to_rgb(dot_color)


def recolor_image(image_rgba: np.ndarray, color: RGB) -> np.ndarray:
    result = image_rgba.copy()
    for c in range(3):
        result[:, :, c] = np.where(image_rgba[:, :, 3] > 0, color[c], 0)
    return result


def paste_dots(canvas: Image.Image, face_num: int, dot_color: RGB) -> None:
    dots = Image.open(TEAM_DOTS_DIR / f'dots-{face_num}.png').convert('RGBA')
    colored = recolor_image(np.array(dots), dot_color)
    scaled = Image.fromarray(colored).resize((CONTENT_SIZE, CONTENT_SIZE), Image.Resampling.LANCZOS)
    fx, fy = FACE_COORDS[face_num]
    canvas.paste(scaled, (fx + CONTENT_OFFSET, fy + CONTENT_OFFSET), scaled)


def generate_team_dice(
    icon_path: Optional[Path],
    output_path: Path,
    background_color: RGB,
    dot_color: RGB,
) -> None:
    """Render one team-dice JPEG using the team_template assets."""
    bg_arr = np.array(Image.open(TEAM_BG).convert('RGB')).astype(np.float32)
    tinted = (bg_arr * 0.15 + np.array(background_color) * 0.85).astype(np.uint8)
    canvas = Image.fromarray(tinted)

    for face_num in range(1, 6):
        paste_dots(canvas, face_num, dot_color)

    fx, fy = FACE_COORDS[6]
    paste_pos = (fx + CONTENT_OFFSET, fy + CONTENT_OFFSET)
    used_icon = False

    if icon_path and icon_path.exists():
        icon_bgra = cv2.imread(str(icon_path), cv2.IMREAD_UNCHANGED)
        if icon_bgra is not None and icon_bgra.ndim == 3 and icon_bgra.shape[2] == 4:
            icon_rgba = cv2.cvtColor(icon_bgra, cv2.COLOR_BGRA2RGBA)
            icon_arr = recolor_image(icon_rgba, dot_color)
            icon = Image.fromarray(icon_arr).resize(
                (CONTENT_SIZE, CONTENT_SIZE), Image.Resampling.LANCZOS
            )
            canvas.paste(icon, paste_pos, icon)
            used_icon = True

    if not used_icon:
        paste_dots(canvas, 5, dot_color)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, 'JPEG', quality=95)


def process_team(
    team_slug: str,
    output_dir: Path,
    first_token_only: bool = False,
) -> bool:
    """
    Apply the team-dice priority flow for one team.
    Returns True if a team dice was produced, False if skipped/removed.
    """
    output_path = output_dir / team_slug / 'dice' / f'{team_slug}-dice-team.jpg'

    # 1. Config override: config/teams/{team}/dice/dice.jpg
    config_override = CONFIG_TEAMS_DIR / team_slug / 'dice' / 'dice.jpg'
    if config_override.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config_override, output_path)
        logger.info(f'  config override → {output_path}')
        return True

    # 2. Token-based generation
    tokens_dir = output_dir / team_slug / 'tokens'
    if tokens_dir.exists() and any(tokens_dir.glob('*.png')):
        colors = extract_token_colors(tokens_dir, first_token_only=first_token_only)
        if colors:
            bg_color, dot_color = colors
            n = 1 if first_token_only else len(list(tokens_dir.glob('*.png')))
            note = '(first token)' if first_token_only else f'({n} tokens)'
            logger.info(f'  bg={list(bg_color)}  dots={list(dot_color)}  {note}')
            icon_path = (
                EXTRACTED_DIR / team_slug / 'icons'
                / f'{team_slug}-icon-token-transparent.png'
            )
            generate_team_dice(icon_path, output_path, bg_color, dot_color)
            logger.info(f'  -> {output_path}')
            return True

    # 3. No source — remove stale file if present
    if output_path.exists():
        output_path.unlink()
        logger.info('  no tokens/override → removed stale team dice')
    else:
        logger.info('  no tokens/override → skip')
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Generate or clean team dice textures'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--team', nargs='+', metavar='SLUG', help='Team slug(s) to process')
    group.add_argument('--all', action='store_true', help='Process all teams')
    parser.add_argument(
        '--first-token', action='store_true',
        help='Use only the first token image (quick visual test)'
    )
    parser.add_argument('--output-dir', type=Path, default=Path('output'))
    args = parser.parse_args()

    team_config = load_team_config()
    if args.team:
        teams = args.team
    else:
        # Skip teams already marked done; re-run with --team <slug> to force
        teams = sorted(
            slug for slug, cfg in team_config.items()
            if not cfg.get('dice_ready')
        )
    total = len(teams)
    generated = 0
    skipped = 0

    for i, slug in enumerate(teams, 1):
        name = team_config.get(slug, {}).get('canonical_name', slug)
        logger.info(f'[{i}/{total}] {name}')
        if process_team(slug, args.output_dir, first_token_only=args.first_token):
            generated += 1
        else:
            skipped += 1

    logger.info(f'\nDone — generated: {generated}  skipped/removed: {skipped}')


if __name__ == '__main__':
    main()
