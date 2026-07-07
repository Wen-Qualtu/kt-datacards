"""Backside extraction — one-off per team, consumes the artwork layer.

layers/integration/{team}/artwork/icons/{team}-icon-token.jpg
   ->  layers/integration/{team}/card-backside/{team}-backside-{landscape,portrait}.jpg

Auto-generates one landscape and one portrait card back (dark background + centred
team icon) so ``generate_card_images`` can reuse a single file instead of
re-deriving it per card. A manual override in ``config/teams/{team}/card-backside/``
is respected (skipped unless ``--force``).

PORT-FROM: pipelines/kt-app/steps/5d_generate_card_backsides.py
SOURCE-DECISION: source-agnostic — drives off the shared artwork icon, so it does
  not matter which track produced it.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from ..utils import paths
from ..utils.state import StateIndex, StateManager

logger = logging.getLogger(__name__)

LANDSCAPE_SIZE = (645, 407)
PORTRAIT_SIZE = (407, 645)
ICON_SCALE = 0.62  # fraction of the shorter canvas dimension

BACKGROUND_PATH = paths.DEFAULTS / "box" / "card-box-background.jpeg"


# ---------------------------------------------------------------------------
# Image helpers (verbatim from the legacy step)
# ---------------------------------------------------------------------------
def _crop_and_resize(src: Image.Image, target_w: int, target_h: int) -> Image.Image:
    img = src.convert("RGB")
    sw, sh = img.size
    ratio = target_w / target_h
    if sw / sh > ratio:
        new_w = int(sh * ratio)
        x0 = (sw - new_w) // 2
        img = img.crop((x0, 0, x0 + new_w, sh))
    else:
        new_h = int(sw / ratio)
        y0 = (sh - new_h) // 2
        img = img.crop((0, y0, sw, y0 + new_h))
    return img.resize((target_w, target_h), Image.LANCZOS)


def _remove_dark_background(icon: Image.Image, threshold: int = 40) -> Image.Image:
    arr = np.array(icon.convert("RGB"))
    brightness = arr.max(axis=2)
    alpha = np.where(brightness < threshold, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([arr, alpha]), "RGBA")


def _paste_icon_centred(canvas: Image.Image, icon_rgba: Image.Image,
                        target_w: int, target_h: int) -> None:
    shorter = min(target_w, target_h)
    max_dim = int(shorter * ICON_SCALE)
    iw, ih = icon_rgba.size
    scale = min(max_dim / iw, max_dim / ih)
    new_w, new_h = int(iw * scale), int(ih * scale)
    icon_scaled = icon_rgba.resize((new_w, new_h), Image.LANCZOS)
    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2
    canvas.paste(icon_scaled, (x, y), mask=icon_scaled.split()[3])


def _generate_backsides(background_path: Path, icon_path: Path,
                        out_landscape: Path, out_portrait: Path) -> bool:
    try:
        bg_raw = Image.open(background_path)
        icon_rgba = None
        if icon_path.exists():
            icon_rgba = _remove_dark_background(Image.open(icon_path))
        else:
            logger.warning(f"  icon not found: {icon_path}")

        for target_w, target_h, out_path in [
            (*LANDSCAPE_SIZE, out_landscape),
            (*PORTRAIT_SIZE, out_portrait),
        ]:
            canvas = _crop_and_resize(bg_raw, target_w, target_h).convert("RGBA")
            if icon_rgba is not None:
                _paste_icon_centred(canvas, icon_rgba, target_w, target_h)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            canvas.convert("RGB").save(str(out_path), "JPEG", quality=95)
            logger.info(f"  OK  {out_path.name}")
        return True
    except Exception as exc:
        logger.error(f"  ERROR generating backsides: {exc}")
        return False


def _has_override(team: str) -> bool:
    base = paths.team_config_dir(team) / "card-backside"
    has_ls = any((base / n).exists() for n in [
        f"{team}-backside-landscape.jpg",
        "default-backside-landscape.jpg",
    ])
    has_pt = any((base / n).exists() for n in [
        f"{team}-backside-portrait.jpg",
        "default-backside-portrait.jpg",
    ])
    return has_ls and has_pt


def _icon_path(team: str) -> Path:
    return paths.artwork_team_dir(team) / "icons" / f"{team}-icon-token.jpg"


def get_all_teams() -> list[str]:
    """All teams that have an artwork token icon to build a backside from."""
    if not paths.INTEGRATION.exists():
        return []
    return sorted(
        d.name for d in paths.INTEGRATION.iterdir()
        if d.is_dir() and _icon_path(d.name).exists()
    )


def run(teams: Optional[list] = None, source=None, force: bool = False):
    """Orchestrator entry point. Shared step — ``source`` is ignored."""
    if teams is None:
        teams = get_all_teams()
    if not teams:
        logger.error("No teams found with a token icon (run extract_artwork first)")
        return {"generated": 0, "override": 0, "failed": 0}

    logger.info(f"extract_backsides: {len(teams)} team(s)")

    counts = {"generated": 0, "override": 0, "failed": 0, "skipped": 0}
    for team in teams:
        logger.info(f"[{team}]")
        if not force and _has_override(team):
            logger.info("  skip (manual override in config/teams/)")
            counts["override"] += 1
            continue

        state = StateManager(team)
        inputs = [_icon_path(team), BACKGROUND_PATH]
        if state.can_skip("extract_backsides", inputs, force):
            logger.info("  unchanged, skip")
            counts["skipped"] += 1
            continue

        out_dir = paths.integration_team_dir(team) / "card-backside"
        out_ls = out_dir / f"{team}-backside-landscape.jpg"
        out_pt = out_dir / f"{team}-backside-portrait.jpg"

        if _generate_backsides(BACKGROUND_PATH, _icon_path(team), out_ls, out_pt):
            counts["generated"] += 1
            state.record_output("extract_backsides", "backside-landscape.jpg", out_ls)
            state.record_output("extract_backsides", "backside-portrait.jpg", out_pt)
            state.record_inputs("extract_backsides", inputs)
            state.mark_complete("extract_backsides")
            state.save()
        else:
            counts["failed"] += 1

    StateIndex().rebuild_and_save()
    logger.info(
        f"extract_backsides done: generated={counts['generated']} "
        f"override={counts['override']} skipped={counts['skipped']} failed={counts['failed']}"
    )
    return counts
