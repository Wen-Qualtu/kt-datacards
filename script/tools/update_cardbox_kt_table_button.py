"""Update card box Lua scripts to add KT table button and separate placement logic.

This script:
1. Reads the template Lua script from config/defaults/tts-script/
2. Updates all card box JSON files in tts_objects/
3. Replaces the LuaScript with the new version that has:
   - Separate "Place" button (relative positioning only)
   - New "KT table" button (global coordinates for workshop table)
"""

import json
from pathlib import Path


def update_cardbox_lua(cardbox_path: Path, new_lua_script: str) -> bool:
    """Update a card box's Lua script with the new template."""
    print(f"Processing: {cardbox_path.name}")
    
    try:
        # Load the card box JSON
        with open(cardbox_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'ObjectStates' not in data or len(data['ObjectStates']) == 0:
            print(f"  ⚠ No ObjectStates found in {cardbox_path.name}")
            return False
        
        card_box = data['ObjectStates'][0]
        
        # Check if LuaScript exists
        if 'LuaScript' not in card_box:
            print(f"  ⚠ No LuaScript found in {cardbox_path.name}")
            return False
        
        # Update the LuaScript
        old_script = card_box['LuaScript']
        card_box['LuaScript'] = new_lua_script
        
        # Save the updated JSON
        with open(cardbox_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print(f"  ✓ Updated {cardbox_path.name}")
        return True
        
    except Exception as e:
        print(f"  ✗ Error updating {cardbox_path.name}: {e}")
        return False


def main():
    # Read the template Lua script
    template_path = Path('config/defaults/tts-script/tts-update-rules-in-box-script.lua')
    
    if not template_path.exists():
        print(f"Error: Template file not found at {template_path}")
        return
    
    print(f"Reading template from {template_path}")
    with open(template_path, 'r', encoding='utf-8') as f:
        new_lua_script = f.read()
    
    print(f"Template loaded ({len(new_lua_script)} characters)\n")
    
    # Find all card box JSON files
    tts_objects_dir = Path('tts_objects')
    if not tts_objects_dir.exists():
        print(f"Error: {tts_objects_dir} directory not found")
        return
    
    # Find all *Cards.json files (excluding display-table directory)
    card_box_files = []
    for team_dir in tts_objects_dir.iterdir():
        if team_dir.is_dir() and team_dir.name != 'display-table':
            box_files = list(team_dir.glob('*Cards.json'))
            card_box_files.extend(box_files)
    
    if not card_box_files:
        print("No card box files found")
        return
    
    print(f"Found {len(card_box_files)} card box files\n")
    print("=" * 60)
    
    # Update each file
    updated_count = 0
    for box_file in sorted(card_box_files):
        if update_cardbox_lua(box_file, new_lua_script):
            updated_count += 1
    
    print("=" * 60)
    print(f"\n✓ Successfully updated {updated_count} of {len(card_box_files)} card box files")
    print("\nChanges made:")
    print("  • Added new 'KT table' button on the left side of the box")
    print("  • 'Place' button now uses only relative positioning (old behavior)")
    print("  • 'KT table' button places cards on global coordinates for workshop table")
    print("\nButton layout on box:")
    print("   update     setup")
    print("KT          BOX")
    print("    place       recall")


if __name__ == '__main__':
    main()
