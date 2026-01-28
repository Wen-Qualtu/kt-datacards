"""
Sync token timestamps from token bags to card box LuaScriptState.

This ensures card boxes know when their tokens were last updated.
"""

import json
from pathlib import Path
from datetime import datetime


def get_token_timestamp(team_slug: str) -> str:
    """Get timestamp from token bag JSON file."""
    token_file = Path(f"tts_objects/tokens/{team_slug}/{team_slug}-tokenbag.json")
    
    if not token_file.exists():
        return ""
    
    # Use file modification time as timestamp
    timestamp = token_file.stat().st_mtime
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def update_card_box_timestamp(card_box_file: Path, team_slug: str):
    """Update a card box JSON with token timestamp in LuaScriptState."""
    if not card_box_file.exists():
        print(f"  ⚠ Skipping {card_box_file.name} (not found)")
        return False
    
    # Load the card box JSON
    with open(card_box_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Get the bag object (first ObjectState)
    if not data.get('ObjectStates') or len(data['ObjectStates']) == 0:
        print(f"  ⚠ Skipping {card_box_file.name} (no ObjectStates)")
        return False
    
    bag = data['ObjectStates'][0]
    lua_script_state = bag.get('LuaScriptState', '')
    
    if not lua_script_state:
        print(f"  ⚠ Skipping {card_box_file.name} (no LuaScriptState)")
        return False
    
    # Parse the script state
    try:
        state = json.loads(lua_script_state)
    except json.JSONDecodeError:
        print(f"  ⚠ Skipping {card_box_file.name} (invalid JSON in LuaScriptState)")
        return False
    
    # Get token timestamp
    token_timestamp = get_token_timestamp(team_slug)
    
    if not token_timestamp:
        # No tokens for this team
        return False
    
    # Check if already has the correct timestamp
    existing_ts = state.get('lastTokenUpdate', '')
    if existing_ts == token_timestamp:
        print(f"  ✓ {card_box_file.stem} (already up to date: {token_timestamp[:16]})")
        return False
    
    # Update the timestamp
    state['lastTokenUpdate'] = token_timestamp
    
    # Save back to bag
    bag['LuaScriptState'] = json.dumps(state)
    
    # Write back to file
    with open(card_box_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    print(f"  ✓ {card_box_file.stem}: {token_timestamp[:16]}")
    return True


def main():
    print("Syncing token timestamps to card boxes...")
    print("=" * 60)
    
    # Get all token directories
    tokens_dir = Path('tts_objects')
    
    if not tokens_dir.exists():
        print("No tokens directory found!")
        return
    
    updated = 0
    skipped = 0
    
    for team_dir in sorted(tokens_dir.iterdir()):
        if not team_dir.is_dir() or team_dir.name == 'display-table':
            continue
        
        # Check if tokens subfolder exists
        if not (team_dir / 'tokens').exists():
            continue
        
        team_slug = team_dir.name
        
        # Map team slug back to card box name
        # Load tts-card-boxes.json to get the proper name
        card_boxes_file = Path('output_v2/tts-card-boxes.json')
        
        if not card_boxes_file.exists():
            print("Error: tts-card-boxes.json not found")
            return
        
        with open(card_boxes_file, 'r', encoding='utf-8') as f:
            card_boxes = json.load(f)
        
        # Find the team name
        team_name = None
        for box in card_boxes:
            if box['team'] == team_slug:
                team_name = box['name']
                break
        
        if not team_name:
            continue
        
        # Find the card box JSON
        card_box_file = Path(f"tts_objects/{team_slug}/{team_name} Cards.json")
        
        if update_card_box_timestamp(card_box_file, team_slug):
            updated += 1
        else:
            skipped += 1
    
    print("=" * 60)
    print(f"✓ Complete! Updated: {updated} | Skipped: {skipped}")


if __name__ == '__main__':
    main()
