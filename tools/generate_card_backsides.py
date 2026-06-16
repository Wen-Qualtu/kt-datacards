#!/usr/bin/env python3
"""
Generate team-specific card-backside images (landscape + portrait).

Each backside is the dark background texture centred-cropped to the target
size with the team token icon composited at ~60 % scale, centred.

Default output sizes  (matching config/defaults/card-backside/):
  landscape : 645 × 407
  portrait  : 407 × 645

Sources (all from config/defaults/box/ so a single swap updates everything):
  background : config/defaults/box/card-box-background.jpeg
  icon       : layers/warcom/extracted/{team}/icons/{team}-icon-token.jpg

Override check (pipeline integration):
  config/teams/{team}/card-backside/default-backside-landscape.jpg  → keep as-is
  config/teams/{team}/card-backside/default-backside-portrait.jpg   → keep as-is
  (team-prefixed variants also checked, same as step 4)

Output:
  output/{team}/card-backside/default-backside-landscape.jpg
  output/{team}/card-backside/default-backside-portrait.jpg

Usage:
  python tools/generate_card_backsides.py                     # all teams → output/
  python tools/generate_card_backsides.py angels-of-death     # single team
  python tools/generate_card_backsides.py all --out-dir dev/test-output/card-backsides
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageFilter

# ---------------------------------------------------------------------------
# Size config
# ---------------------------------------------------------------------------

LANDSCAPE_SIZE = (645, 407)
PORTRAIT_SIZE  = (407, 645)

# Icon scale: fraction of the shorter canvas dimension
ICON_SCALE = 0.62

# ---------------------------------------------------------------------------
# Helpers (shared with generate_box_texture_v2 approach)
# ---------------------------------------------------------------------------

def _crop_and_resize(src: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Centre-crop src to target aspect ratio then resize."""
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
    """Make near-black pixels transparent."""
    arr = np.array(icon.convert("RGB"))
    brightness = arr.max(axis=2)
    alpha = np.where(brightness < threshold, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([arr, alpha]), "RGBA")


def _paste_icon_centred(canvas: Image.Image, icon_rgba: Image.Image,
                        target_w: int, target_h: int) -> None:
    """Scale icon to ICON_SCALE of the shorter side, paste centred."""
    shorter = min(target_w, target_h)
    max_dim = int(shorter * ICON_SCALE)
    iw, ih = icon_rgba.size
    scale = min(max_dim / iw, max_dim / ih)
    new_w, new_h = int(iw * scale), int(ih * scale)
    icon_scaled = icon_rgba.resize((new_w, new_h), Image.LANCZOS)
    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2
    canvas.paste(icon_scaled, (x, y), mask=icon_scaled.split()[3])


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------

def generate_backsides(
    team_slug: str,
    canonical_name: str,
    background_path: Path,
    icon_path: Path,
    out_landscape: Path,
    out_portrait: Path,
) -> bool:
    """Generate both orientations for one team."""
    try:
        bg_raw = Image.open(background_path)

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
# CLI / pipeline helpers
# ---------------------------------------------------------------------------

def has_override(team_slug: str, config_dir: Path) -> bool:
    """Return True if both manual override backsides already exist."""
    base = config_dir / "teams" / team_slug / "card-backside"
    landscape_candidates = [
        base / f"{team_slug}-backside-landscape.jpg",
        base / "default-backside-landscape.jpg",
    ]
    portrait_candidates = [
        base / f"{team_slug}-backside-portrait.jpg",
        base / "default-backside-portrait.jpg",
    ]
    return (any(p.exists() for p in landscape_candidates) and
            any(p.exists() for p in portrait_candidates))


def main():
    parser = argparse.ArgumentParser(
        description="Generate team card-backside images (landscape + portrait)"
    )
    parser.add_argument(
        "team", nargs="?", default="all",
        help='Team slug or "all" (default: all)'
    )
    parser.add_argument(
        "--base-dir", type=Path, default=None,
        help="Project root (default: parent of this script)"
    )
    parser.add_argument(
        "--out-dir", type=Path, default=None,
        help="Override output root (default: <base>/output)"
    )
    parser.add_argument(
        "--background", type=Path, default=None,
        help="Override background image"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-generate even when manual overrides exist in config/teams/"
    )
    args = parser.parse_args()

    base       = args.base_dir or Path(__file__).resolve().parent.parent
    background = args.background or (base / "config" / "defaults" / "box" / "card-box-background.jpeg")
    icons_dir  = base / "layers" / "warcom" / "extracted"
    out_root   = args.out_dir or (base / "output")
    config_dir = base / "config"

    if not background.exists():
        print(f"ERROR: background not found: {background}")
        sys.exit(1)

    with open(base / "config" / "team-config.yaml") as fh:
        all_teams: dict = yaml.safe_load(fh).get("teams", {})

    if args.team == "all":
        targets = list(all_teams.items())
    elif args.team in all_teams:
        targets = [(args.team, all_teams[args.team])]
    else:
        print(f"ERROR: unknown team '{args.team}'")
        sys.exit(1)

    ok = fail = skipped = 0
    for slug, data in targets:
        canonical  = data.get("canonical_name", slug.replace("-", " ").title())
        icon_path  = icons_dir / slug / "icons" / f"{slug}-icon-token.jpg"
        out_ls     = out_root / slug / "card-backside" / f"{slug}-backside-landscape.jpg"
        out_pt     = out_root / slug / "card-backside" / f"{slug}-backside-portrait.jpg"

        print(f"[{slug}]")

        if not args.force and has_override(slug, config_dir):
            print(f"  skip (manual override in config/teams/)")
            skipped += 1
            continue

        if generate_backsides(slug, canonical, background, icon_path, out_ls, out_pt):
            ok += 1
        else:
            fail += 1

    if len(targets) > 1:
        print(f"\nDone: {ok} OK, {skipped} skipped (override), {fail} failed")


if __name__ == "__main__":
    main()
