#!/usr/bin/env python3
"""
Replace TTS preview images with official Warhammer Community team icons.

The icons from Warhammer Community are higher quality and more consistent
than the extracted box texture previews.
"""

from pathlib import Path
import shutil
import json


def load_team_metadata():
    """Load the metadata about available team icons."""
    metadata_file = Path(__file__).parent.parent / "config" / "team-icons-raw" / "teams_metadata.json"
    with open(metadata_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_existing_tts_teams():
    """Get list of teams that have TTS preview images."""
    teams_dir = Path(__file__).parent.parent / "config" / "teams"
    if not teams_dir.exists():
        return []
    
    teams = []
    for team_dir in tts_image_dir.iterdir():
        if team_dir.is_dir() and team_dir.name != 'default':
            teams.append(team_dir.name)
    return teams


def match_team_slug(tts_team_name, available_icons):
    """
    Match a TTS team name to an available icon slug.
    
    TTS team names use hyphens (e.g., 'angels-of-death')
    Icon slugs also use hyphens (e.g., 'angels-of-death')
    
    Some teams might need special mapping.
    """
    # Create a mapping of icon slugs
    icon_slugs = {icon['slug']: icon for icon in available_icons}
    
    # Direct match
    if tts_team_name in icon_slugs:
        return icon_slugs[tts_team_name]
    
    # Special mappings for teams with different names
    special_mappings = {
        'wolf-scouts': 'scout-squad',  # Wolf Scouts might be part of Scout Squad
        'wrecka-krew': 'kommandos',     # Orks - might match Kommandos
        'battleclade': 'hunter-clade',  # AdMech naming
        'canoptek-circle': 'hierotek-circle',  # Necron naming difference
        'deathwatch': 'angels-of-death',  # Space Marines variant
        'vespids-stingwing': 'vespid-stingwings',  # Singular vs plural
        'goremongers': 'fellgor-ravagers',  # Chaos warband
        'ratlings': 'imperial-navy-breachers',  # Imperial guard variant
        'raveners': 'gellerpox-infected',  # Could also be a tyranid/chaos option
    }
    
    if tts_team_name in special_mappings:
        mapped_slug = special_mappings[tts_team_name]
        if mapped_slug in icon_slugs:
            return icon_slugs[mapped_slug]
    
    return None


def main():
    """Replace TTS preview images with official team icons."""
    project_root = Path(__file__).parent.parent
    raw_icons_dir = project_root / "config" / "team-icons-raw"
    teams_dir = project_root / "config" / "teams"
    
    print("Replacing TTS Preview Images with Official Icons")
    print("=" * 60)
    
    # Load available icons
    icons_metadata = load_team_metadata()
    print(f"\nAvailable icons: {len(icons_metadata)}")
    
    # Get existing TTS teams
    tts_teams = get_existing_tts_teams()
    print(f"TTS teams with previews: {len(tts_teams)}")
    
    if not tts_teams:
        print("\nNo TTS preview directories found.")
        return
    
    print("\nMapping and replacing icons...\n")
    
    replaced = 0
    not_found = 0
    
    for tts_team in sorted(tts_teams):
        # Try to match to an icon
        icon_data = match_team_slug(tts_team, icons_metadata)
        
        if icon_data:
            # Copy the raw icon (500x500) to TTS preview location
            source = raw_icons_dir / f"{icon_data['slug']}.png"
            dest_dir = teams_dir / tts_team / "tts-image"
            dest = dest_dir / f"{tts_team}-preview.png"
            
            if source.exists():
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
                print(f"  ✓ {tts_team:<30} <- {icon_data['slug']}")
                replaced += 1
            else:
                print(f"  ✗ {tts_team:<30} Source file missing: {source.name}")
                not_found += 1
        else:
            print(f"  ⚠ {tts_team:<30} No matching icon found")
            not_found += 1
    
    print(f"\n{'='*60}")
    print(f"✓ Replaced: {replaced}")
    if not_found > 0:
        print(f"⚠ Not found: {not_found}")
    
    print("\nNext step: Regenerate TTS objects to use new previews:")
    print("  poetry run python script/generate_tts_objects.py")


if __name__ == "__main__":
    main()
