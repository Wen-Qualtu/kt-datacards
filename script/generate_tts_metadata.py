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
    """Get ISO format timestamp from file's modification time (fallback only)."""
    if not file_path.exists():
        return ""
    
    timestamp = os.path.getmtime(file_path)
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def extract_timestamp_from_json(json_file: Path, timestamp_key: str) -> str:
    """Extract timestamp from LuaScriptState inside a TTS JSON file."""
    if not json_file.exists():
        return ""
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Get the first ObjectState (the bag/deck)
        if not data.get('ObjectStates') or len(data['ObjectStates']) == 0:
            return ""
        
        lua_script_state = data['ObjectStates'][0].get('LuaScriptState', '')
        if not lua_script_state:
            return ""
        
        # Parse the LuaScriptState JSON
        state = json.loads(lua_script_state)
        return state.get(timestamp_key, "")
    except Exception as e:
        print(f"    Warning: Could not extract {timestamp_key} from {json_file.name}: {e}")
        return ""


def generate_combined_metadata(team_filter=None):
    """Generate unified tts-metadata.json with both cards and tokens.

    When team_filter is a non-empty list of team slugs only those teams are
    refreshed; all other teams' entries are preserved from the existing file.
    """
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

        if team_filter and team_slug not in team_filter:
            continue
        
        # Find the card box file and extract timestamp from LuaScriptState
        # Files are stored in team subfolders: tts_objects/{team_slug}/{Team Name} Cards.json
        card_box_file = tts_objects_dir / team_slug / f"{team_name} Cards.json"
        cards_timestamp = extract_timestamp_from_json(card_box_file, 'lastCardUpdate')
        
        # Fallback to file modification time if extraction fails
        if not cards_timestamp:
            cards_timestamp = get_file_timestamp(card_box_file)
            print(f"    Warning: Using file mtime for {team_name} (no LuaScriptState)")
        
        metadata_dict[team_slug] = {
            "team": team_slug,
            "name": team_name,
            "cards_url": entry['url'],
            "cards_last_modified": cards_timestamp
        }
        
        print(f"  * {team_name}: cards={cards_timestamp[:16] if cards_timestamp else 'N/A'}")
    
    # Now add token information
    tts_teams_dir = Path('tts_objects')
    
    if tts_teams_dir.exists():
        print("\nProcessing token bags...")
        for team_dir in sorted(tts_teams_dir.iterdir()):
            if not team_dir.is_dir() or team_dir.name == 'display-table':
                continue

            team_slug = team_dir.name

            if team_filter and team_slug not in team_filter:
                continue
            token_bag_file = team_dir / 'tokens' / f"{team_slug}-tokenbag.json"
            
            if not token_bag_file.exists():
                continue
            
            # Extract timestamp from LuaScriptState
            tokens_timestamp = extract_timestamp_from_json(token_bag_file, 'lastTokenUpdate')
            
            # Fallback to file modification time if extraction fails
            if not tokens_timestamp:
                tokens_timestamp = get_file_timestamp(token_bag_file)
                print(f"    Warning: Using file mtime for {team_slug} tokens (no LuaScriptState)")
            
            # Build URL
            tokens_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/tts_objects/{team_slug}/tokens/{team_slug}-tokenbag.json"
            
            # Add to existing entry or create new one
            if team_slug in metadata_dict:
                metadata_dict[team_slug]["tokens_url"] = tokens_url
                metadata_dict[team_slug]["tokens_last_modified"] = tokens_timestamp
                print(f"  * {metadata_dict[team_slug]['name']}: tokens={tokens_timestamp[:16] if tokens_timestamp else 'N/A'}")
            else:
                # Token-only team (shouldn't happen but handle it)
                team_name = team_slug.replace('-', ' ').title()
                metadata_dict[team_slug] = {
                    "team": team_slug,
                    "name": team_name,
                    "tokens_url": tokens_url,
                    "tokens_last_modified": tokens_timestamp
                }
                print(f"  * {team_name} (tokens only): {tokens_timestamp[:16] if tokens_timestamp else 'N/A'}")
    
    # Convert dict to sorted list
    metadata = [metadata_dict[slug] for slug in sorted(metadata_dict.keys())]

    # Save to output_v2/tts-metadata.json
    output_file = Path('output_v2/tts-metadata.json')
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if team_filter and output_file.exists():
        # Preserve existing entries for teams not in the filter,
        # then append the freshly-generated filtered entries.
        existing = json.load(open(output_file, encoding='utf-8'))
        preserved = [e for e in existing if e.get('team') not in team_filter]
        metadata = preserved + metadata
        print(f"  Merged: updated {len(team_filter)} team(s), preserved {len(preserved)} others")

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
        f.write('\n')
    
    print(f"\nGenerated {output_file}")
    print(f"  Total teams: {len(metadata)}")
    teams_with_tokens = sum(1 for t in metadata if "tokens_url" in t)
    print(f"  Teams with tokens: {teams_with_tokens}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate TTS metadata JSON')
    parser.add_argument('--teams', nargs='+', metavar='TEAM',
                        help='Only update entries for these team slugs')
    args = parser.parse_args()

    print("Generating unified TTS metadata...")
    print("=" * 60)
    if args.teams:
        print(f"  Team filter: {args.teams}")
    generate_combined_metadata(team_filter=args.teams)
    
    print("\n" + "=" * 60)
    print("Metadata generation complete!")


if __name__ == '__main__':
    main()
