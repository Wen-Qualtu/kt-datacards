#!/usr/bin/env python3
"""Test extraction on specific teams to verify colors."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract_token_colors import extract_color_families_from_tokens

def test_team(team_slug):
    """Test color extraction for a specific team."""
    output_dir = Path("output")
    token_dir = output_dir / team_slug / "tokens"
    
    if not token_dir.exists():
        print(f"❌ {team_slug}: No tokens directory")
        return
    
    token_files = [f for f in token_dir.glob("*.png") if not f.stem.endswith('-icon')]
    if not token_files:
        print(f"❌ {team_slug}: No token files")
        return
    
    colors = extract_color_families_from_tokens(token_files[:3])
    
    if colors:
        back = colors['back_color']
        front = colors['front_color']
        print(f"✓ {team_slug:30} - back: rgb({back[0]:3}, {back[1]:3}, {back[2]:3})  front: rgb({front[0]:3}, {front[1]:3}, {front[2]:3})")
    else:
        print(f"❌ {team_slug}: No colors extracted")

if __name__ == "__main__":
    print("Testing color extraction on specific teams:\n")
    test_team("canoptek-circle")
    test_team("celestian-insidiants")
    test_team("brood-brothers")
    test_team("hearthkyn-salvagers")
