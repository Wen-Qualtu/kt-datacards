"""
Step 5d: Generate Team Card Backsides

Generates one landscape and one portrait backside image per team and stores
them in layers/kt-app/extracted/{team}/card-backside/ so that step 4 can
reuse a single file instead of re-deriving it for every card.

Priority:
  1. config/teams/{team}/card-backside/ has a manual override → skip (keep override)
  2. Auto-generate: dark background + centred team icon

Output per team:
  layers/kt-app/extracted/{team}/card-backside/{team}-backside-landscape.jpg
  layers/kt-app/extracted/{team}/card-backside/{team}-backside-portrait.jpg

Usage:
  python pipelines/kt-app/steps/5d_generate_card_backsides.py
  python pipelines/kt-app/steps/5d_generate_card_backsides.py --teams angels-of-death kasrkin
  python pipelines/kt-app/steps/5d_generate_card_backsides.py --force
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, Set

import numpy as np
import yaml
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[3]

EXTRACTED_DIR   = PROJECT_ROOT / "layers" / "warcom" / "extracted"
LAYERS_DIR      = PROJECT_ROOT / "layers" / "kt-app" / "extracted"
CONFIG_DIR      = PROJECT_ROOT / "config"
BACKGROUND_PATH = CONFIG_DIR / "defaults" / "box" / "card-box-background.jpeg"

# ---------------------------------------------------------------------------
# Size config
# ---------------------------------------------------------------------------

LANDSCAPE_SIZE = (645, 407)
PORTRAIT_SIZE  = (407, 645)
ICON_SCALE     = 0.62   # fraction of shorter canvas dimension

# ---------------------------------------------------------------------------
# Image helpers
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
    shorter  = min(target_w, target_h)
    max_dim  = int(shorter * ICON_SCALE)
    iw, ih   = icon_rgba.size
    scale    = min(max_dim / iw, max_dim / ih)
    new_w, new_h = int(iw * scale), int(ih * scale)
    icon_scaled  = icon_rgba.resize((new_w, new_h), Image.LANCZOS)
    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2
    canvas.paste(icon_scaled, (x, y), mask=icon_scaled.split()[3])


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------

def generate_backsides(team_slug: str, canonical_name: str,
                       background_path: Path, icon_path: Path,
                       out_landscape: Path, out_portrait: Path) -> bool:
    try:
        bg_raw    = Image.open(background_path)
        icon_rgba = None
        if icon_path.exists():
            icon_rgba = _remove_dark_background(Image.open(icon_path))
        else:
            print(f"  WARNING: icon not found: {icon_path}")

        for target_w, target_h, out_path in [
            (*LANDSCAPE_SIZE, out_landscape),
            (*PORTRAIT_SIZE,  out_portrait),
        ]:
            canvas = _crop_and_resize(bg_raw, target_w, target_h).convert("RGBA")
            if icon_rgba is not None:
                _paste_icon_centred(canvas, icon_rgba, target_w, target_h)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            canvas.convert("RGB").save(str(out_path), "JPEG", quality=95)
            print(f"  OK  {out_path}")

        return True

    except Exception as exc:
        import traceback
        print(f"  ERROR: {exc}")
        traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Override check
# ---------------------------------------------------------------------------

def has_override(team_slug: str, config_dir: Path) -> bool:
    base = config_dir / "teams" / team_slug / "card-backside"
    has_ls = any((base / n).exists() for n in [
        f"{team_slug}-backside-landscape.jpg",
        "default-backside-landscape.jpg",
    ])
    has_pt = any((base / n).exists() for n in [
        f"{team_slug}-backside-portrait.jpg",
        "default-backside-portrait.jpg",
    ])
    return has_ls and has_pt


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

def load_teams() -> list[tuple[str, dict]]:
    with open(CONFIG_DIR / "team-config.yaml") as f:
        return sorted(yaml.safe_load(f).get("teams", {}).items())


def run(team_filter: Optional[Set[str]] = None, force: bool = False) -> dict[str, int]:
    teams = load_teams()
    if team_filter:
        teams = [(s, d) for s, d in teams if s in team_filter]

    counts = {"generated": 0, "override": 0, "failed": 0}

    for slug, data in teams:
        canonical = data.get("canonical_name", slug.replace("-", " ").title())
        icon_path = EXTRACTED_DIR / slug / "icons" / f"{slug}-icon-token.jpg"
        out_dir   = LAYERS_DIR / slug / "card-backside"
        out_ls    = out_dir / f"{slug}-backside-landscape.jpg"
        out_pt    = out_dir / f"{slug}-backside-portrait.jpg"

        print(f"[{slug}]")

        if not force and has_override(slug, CONFIG_DIR):
            print(f"  skip (manual override in config/teams/)")
            counts["override"] += 1
            continue

        if generate_backsides(slug, canonical, BACKGROUND_PATH, icon_path, out_ls, out_pt):
            counts["generated"] += 1
        else:
            counts["failed"] += 1

    return counts


def main():
    parser = argparse.ArgumentParser(description="Step 5d: Generate team card backsides")
    parser.add_argument("--teams", nargs="+", metavar="TEAM", help="Specific teams to process")
    parser.add_argument(
        "--force", action="store_true",
        help="Re-generate even for teams with a manual override in config/teams/"
    )
    args = parser.parse_args()

    team_filter = set(args.teams) if args.teams else None

    print("=== Step 5d: Generate Card Backsides ===")
    counts = run(team_filter, args.force)
    print(
        f"\nGenerated: {counts['generated']}"
        f"  Override (kept): {counts['override']}"
        f"  Failed: {counts['failed']}"
    )


if __name__ == "__main__":
    main()
