"""
Step 5c: Generate Team Box Textures

Priority per team:
  1. config/teams/{team}/box/card-box-texture.jpg exists  -> use as-is (manual override)
  2. warcom icons exist in layers/warcom/extracted/{team}/icons/ -> auto-generate texture
  3. neither available -> step 6 will fall back to config/defaults/box/ texture

In practice almost all teams will hit case 2. Case 1 is for manual overrides that
should survive regeneration. Case 3 covers new teams while their icons are unavailable.

Usage:
    python pipelines/kt-app/steps/5c_generate_box_textures.py
    python pipelines/kt-app/steps/5c_generate_box_textures.py --teams angels-of-death kasrkin
    python pipelines/kt-app/steps/5c_generate_box_textures.py --force   # re-generate even case-1 textures
"""

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Optional, Set

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Load generate_box_texture tool as a module (avoids needing __init__.py in tools/)
_spec = importlib.util.spec_from_file_location(
    "generate_box_texture",
    PROJECT_ROOT / "tools" / "generate_box_texture.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
generate_for_team = _mod.generate_for_team

EXTRACTED_DIR = PROJECT_ROOT / "layers" / "warcom" / "extracted"
CONFIG_DIR = PROJECT_ROOT / "config"
TEMPLATE_PATH = PROJECT_ROOT / "tools" / "resources" / "box-side.png"


def load_teams() -> list[str]:
    config_path = PROJECT_ROOT / "config" / "team-config.yaml"
    with open(config_path) as f:
        return sorted(yaml.safe_load(f).get("teams", {}).keys())


def has_icons(slug: str) -> bool:
    landscape = EXTRACTED_DIR / slug / "icons" / f"{slug}-icon-landscape.jpg"
    portrait = EXTRACTED_DIR / slug / "icons" / f"{slug}-icon-portrait.jpg"
    return landscape.exists() and portrait.exists()


def run(team_filter: Optional[Set[str]] = None, force: bool = False) -> dict[str, int]:
    if not TEMPLATE_PATH.exists():
        print(f"ERROR: Template not found: {TEMPLATE_PATH}")
        sys.exit(1)

    teams = load_teams()
    if team_filter:
        teams = [t for t in teams if t in team_filter]

    counts = {"generated": 0, "manual_override": 0, "no_icons": 0, "failed": 0}

    for slug in teams:
        texture = CONFIG_DIR / "teams" / slug / "box" / "card-box-texture.jpg"

        # Priority 1: manual override — texture exists and we're not forcing
        if texture.exists() and not force:
            counts["manual_override"] += 1
            continue

        # Priority 2: auto-generate from warcom icons
        if has_icons(slug):
            print(f"  [generate] {slug}")
            ok = generate_for_team(slug, EXTRACTED_DIR, CONFIG_DIR, TEMPLATE_PATH)
            if ok:
                counts["generated"] += 1
            else:
                print(f"  WARNING: generation failed for {slug}")
                counts["failed"] += 1
            continue

        # Priority 3: no icons and no existing texture — step 6 will use default
        if not texture.exists():
            print(f"  [default]  {slug}  (no icons, step 6 will use default box)")
            counts["no_icons"] += 1

    return counts


def main():
    parser = argparse.ArgumentParser(description="Step 5c: Generate team box textures")
    parser.add_argument("--teams", nargs="+", metavar="TEAM", help="Specific teams to process")
    parser.add_argument(
        "--force", action="store_true",
        help="Re-generate even for teams that already have a texture (overrides manual configs)"
    )
    args = parser.parse_args()

    team_filter = set(args.teams) if args.teams else None

    print("=== Step 5c: Generate Box Textures ===")
    counts = run(team_filter, args.force)

    print(
        f"\nGenerated: {counts['generated']}"
        f"  Manual override (kept): {counts['manual_override']}"
        f"  No icons (will use default): {counts['no_icons']}"
        f"  Failed: {counts['failed']}"
    )


if __name__ == "__main__":
    main()
