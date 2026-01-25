"""
Generate tts-metadata.json with timestamps for both cards and tokens.

This creates a unified metadata file containing:
- Team slug
- Team name
- Card box URL and timestamp (prefixed with cards_)
- Token bag URL and timestamp (prefixed with tokens_)
"""

import json
from pathlib import Path
from datetime import datetime
import os


def get_file_timestamp(file_path: Path) -> str:
    """Get ISO format timestamp of file's last modification."""
    if not file_path.exists():
        return ""
    
    timestamp = os.path.getmtime(file_path)
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def generate_combined_metadata():
    """Generate unified tts-metadata.json with both cards and tokens."""
    # First, get card boxes from existing tts-card-boxes.json
    card_boxes_file = Path('output_v2/tts-card-boxes.json')
    
    if not card_boxes_file.exists():
        print(f"Error: {card_boxes_file} not found")
        return
    
    with open(card_boxes_file, 'r', encoding='utf-8') as f:
        card_boxes = json.load(f)
    
    # Build metadata dict keyed by team slug
    metadata_dict = {}
    tts_objects_dir = Path('tts_objects')
    
    print("Processing card boxes...")
    for entry in card_boxes:
        team_slug = entry['team']
        team_name = entry['name']
        
        # Find the card box file for timestamp
        card_box_file = tts_objects_dir / f"{team_name} Cards.json"
        cards_timestamp = get_file_timestamp(card_box_file)
        
        metadata_dict[team_slug] = {
            "team": team_slug,
            "name": team_name,
            "cards_url": entry['url'],
            "cards_last_modified": cards_timestamp
        }
        
        print(f"  ✓ {team_name}: cards={cards_timestamp[:16]}")
    
    # Now add token information
    tokens_dir = Path('tts_objects/tokens')
    
    if tokens_dir.exists():
        print("\nProcessing token bags...")
        for team_dir in sorted(tokens_dir.iterdir()):
            if not team_dir.is_dir():
                continue
            
            team_slug = team_dir.name
            token_bag_file = team_dir / f"{team_slug}-tokenbag.json"
            
            if not token_bag_file.exists():
                continue
            
            # Get timestamp
            tokens_timestamp = get_file_timestamp(token_bag_file)
            
            # Build URL
            tokens_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/tts_objects/tokens/{team_slug}/{team_slug}-tokenbag.json"
            
            # Add to existing entry or create new one
            if team_slug in metadata_dict:
                metadata_dict[team_slug]["tokens_url"] = tokens_url
                metadata_dict[team_slug]["tokens_last_modified"] = tokens_timestamp
                print(f"  ✓ {metadata_dict[team_slug]['name']}: tokens={tokens_timestamp[:16]}")
            else:
                # Token-only team (shouldn't happen but handle it)
                team_name = team_slug.replace('-', ' ').title()
                metadata_dict[team_slug] = {
                    "team": team_slug,
                    "name": team_name,
                    "tokens_url": tokens_url,
                    "tokens_last_modified": tokens_timestamp
                }
                print(f"  ✓ {team_name} (tokens only): {tokens_timestamp[:16]}")
    
    # Convert dict to sorted list
    metadata = [metadata_dict[slug] for slug in sorted(metadata_dict.keys())]
    
    # Save to output_v2/tts-metadata.json
    output_file = Path('output_v2/tts-metadata.json')
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✓ Generated {output_file}")
    print(f"  Total teams: {len(metadata)}")
    teams_with_tokens = sum(1 for t in metadata if "tokens_url" in t)
    print(f"  Teams with tokens: {teams_with_tokens}")


def main():
    print("Generating unified TTS metadata...")
    print("=" * 60)
    generate_combined_metadata()
    
    print("\n" + "=" * 60)
    print("✓ Metadata generation complete!")


if __name__ == '__main__':
    main()
