"""
Step 5c: Generate Team Box Textures

Composites per-team box textures from:
- tools/resources/box-side.png  (template panel)
- layers/warcom/extracted/{team}/icons/{team}-icon-landscape.jpg
- layers/warcom/extracted/{team}/icons/{team}-icon-portrait.jpg
- Team name text overlay

Output: config/teams/{team}/box/card-box-texture.jpg
        (read by step 6 which copies textures into output/)

Teams without warcom icons are skipped (they keep their existing or default texture).

Usage:
    python pipelines/kt-app/steps/5c_generate_box_textures.py
    python pipelines/kt-app/steps/5c_generate_box_textures.py --teams angels-of-death kasrkin
    python pipelines/kt-app/steps/5c_generate_box_textures.py --force
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


def load_team_config() -> dict:
    config_path = PROJECT_ROOT / "config" / "team-config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f).get("teams", {})


def teams_with_icons(team_filter: Optional[Set[str]] = None) -> list[str]:
    """Return sorted team slugs that have both warcom landscape and portrait icons."""
    teams_config = load_team_config()
    result = []
    for slug in teams_config:
        if team_filter and slug not in team_filter:
            continue
        landscape = EXTRACTED_DIR / slug / "icons" / f"{slug}-icon-landscape.jpg"
        portrait = EXTRACTED_DIR / slug / "icons" / f"{slug}-icon-portrait.jpg"
        if landscape.exists() and portrait.exists():
            result.append(slug)
    return sorted(result)


def run(team_filter: Optional[Set[str]] = None, force: bool = False) -> tuple[int, int, int]:
    if not TEMPLATE_PATH.exists():
        print(f"ERROR: Template not found: {TEMPLATE_PATH}")
        sys.exit(1)

    teams = teams_with_icons(team_filter)
    if not teams:
        print("No teams with warcom icons found.")
        return 0, 0, 0

    generated = skipped = failed = 0
    for slug in teams:
        output = CONFIG_DIR / "teams" / slug / "box" / "card-box-texture.jpg"
        if not force and output.exists():
            skipped += 1
            continue
        print(f"  [{slug}]")
        ok = generate_for_team(slug, EXTRACTED_DIR, CONFIG_DIR, TEMPLATE_PATH)
        if ok:
            generated += 1
        else:
            failed += 1

    return generated, skipped, failed


def main():
    parser = argparse.ArgumentParser(description="Step 5c: Generate team box textures")
    parser.add_argument("--teams", nargs="+", metavar="TEAM", help="Specific teams to process")
    parser.add_argument("--force", action="store_true", help="Regenerate even if texture already exists")
    args = parser.parse_args()

    team_filter = set(args.teams) if args.teams else None

    print("=== Step 5c: Generate Box Textures ===")
    if not args.force:
        print("(pass --force to regenerate existing textures)")

    generated, skipped, failed = run(team_filter, args.force)

    print(f"\nGenerated: {generated}  Skipped: {skipped}  Failed: {failed}")


if __name__ == "__main__":
    main()
