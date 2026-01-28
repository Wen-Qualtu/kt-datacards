"""
Migrate TTS objects to new folder structure.

Old structure:
  tts_objects/{Team Name} Cards.json
  tts_objects/{Team Name} Cards.png
  tts_objects/tokens/{team-slug}/{team-slug}-tokenbag.json
  tts_objects/tokens/{team-slug}/*.png

New structure:
  tts_objects/{team-slug}/{Team Name} Cards.json
  tts_objects/{team-slug}/{Team Name} Cards.png
  tts_objects/{team-slug}/tokens/{team-slug}-tokenbag.json
  tts_objects/{team-slug}/tokens/*.png
"""

import json
import shutil
from pathlib import Path


def get_team_slug_from_name(team_name: str) -> str:
    """Convert team display name to slug format."""
    return team_name.lower().replace(' ', '-')


def migrate_tts_structure():
    """Migrate TTS objects to new folder structure."""
    tts_dir = Path('tts_objects')
    
    if not tts_dir.exists():
        print(f"Error: {tts_dir} not found")
        return
    
    # Load team mapping from tts-card-boxes.json
    card_boxes_file = Path('output_v2/tts-card-boxes.json')
    if not card_boxes_file.exists():
        print(f"Error: {card_boxes_file} not found")
        return
    
    with open(card_boxes_file, 'r', encoding='utf-8') as f:
        card_boxes = json.load(f)
    
    # Create mapping of team name to slug
    team_mapping = {box['name']: box['team'] for box in card_boxes}
    
    print("Starting TTS objects migration...")
    print("=" * 60)
    
    # Track what we've processed
    migrated_count = 0
    skipped_count = 0
    
    # Find all card box JSON files in root of tts_objects
    for card_file in sorted(tts_dir.glob('*Cards.json')):
        team_name = card_file.stem.replace(' Cards', '')
        
        # Skip if already in a team folder
        if card_file.parent != tts_dir:
            continue
        
        # Get the slug
        team_slug = team_mapping.get(team_name)
        if not team_slug:
            print(f"⚠️  Skipping {team_name}: no slug mapping found")
            skipped_count += 1
            continue
        
        # Create new team folder
        new_team_dir = tts_dir / team_slug
        new_team_dir.mkdir(exist_ok=True)
        
        # Move card box JSON and PNG
        png_file = card_file.with_suffix('.png')
        
        new_json_path = new_team_dir / card_file.name
        new_png_path = new_team_dir / png_file.name
        
        print(f"\n📦 {team_name} ({team_slug})")
        
        # Move JSON
        if card_file.exists() and not new_json_path.exists():
            shutil.move(str(card_file), str(new_json_path))
            print(f"  ✓ Moved {card_file.name}")
        elif new_json_path.exists():
            print(f"  ⊙ {card_file.name} already in new location")
        
        # Move PNG
        if png_file.exists() and not new_png_path.exists():
            shutil.move(str(png_file), str(new_png_path))
            print(f"  ✓ Moved {png_file.name}")
        elif new_png_path.exists():
            print(f"  ⊙ {png_file.name} already in new location")
        
        # Move tokens folder if it exists
        old_tokens_dir = tts_dir / 'tokens' / team_slug
        new_tokens_dir = new_team_dir / 'tokens'
        
        if old_tokens_dir.exists():
            if not new_tokens_dir.exists():
                shutil.move(str(old_tokens_dir), str(new_tokens_dir))
                print(f"  ✓ Moved tokens folder")
            else:
                print(f"  ⊙ Tokens folder already in new location")
        
        migrated_count += 1
    
    # Clean up empty tokens folder
    old_tokens_root = tts_dir / 'tokens'
    if old_tokens_root.exists() and not list(old_tokens_root.iterdir()):
        old_tokens_root.rmdir()
        print(f"\n🗑️  Removed empty {old_tokens_root}")
    
    print("\n" + "=" * 60)
    print(f"✓ Migration complete!")
    print(f"  Migrated: {migrated_count} teams")
    if skipped_count > 0:
        print(f"  Skipped: {skipped_count} teams")


if __name__ == '__main__':
    migrate_tts_structure()
