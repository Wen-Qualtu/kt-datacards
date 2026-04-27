#!/usr/bin/env python3
"""
Fix token bag rotation to 270° (rotated left) in all token bag files and card boxes.
"""

import json
from pathlib import Path


def fix_rotation_in_tokenbag(tokenbag_path: Path) -> bool:
    """Fix rotation in standalone token bag file."""
    with open(tokenbag_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    modified = False
    
    if not data.get('ObjectStates') or len(data['ObjectStates']) == 0:
        return False
    
    token_bag = data['ObjectStates'][0]
    
    # Check if rotation needs to be changed
    transform = token_bag.get('Transform', {})
    old_rot = transform.get('rotY')
    if old_rot != 270.0:
        transform['rotY'] = 270.0
        modified = True
        print(f"  Updated rotation in {tokenbag_path.name}: {old_rot} -> 270.0")
    
    if modified:
        with open(tokenbag_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    return modified


def fix_rotation_in_cardbox(cardbox_path: Path) -> bool:
    """Fix rotation of token bag in card box's LuaScriptState saved positions."""
    with open(cardbox_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    modified = False
    
    if not data.get('ObjectStates') or len(data['ObjectStates']) == 0:
        return False
    
    card_box = data['ObjectStates'][0]
    
    # Find the token bag GUID first
    token_bag_guid = None
    contained_objects = card_box.get('ContainedObjects', [])
    for obj in contained_objects:
        nickname = obj.get('Nickname', '').lower()
        if 'token' in nickname and obj.get('Name') == 'Custom_Model_Bag':
            token_bag_guid = obj.get('GUID')
            break
    
    if not token_bag_guid:
        return False
    
    # Update the LuaScriptState's saved position for the token bag
    lua_script_state = card_box.get('LuaScriptState', '')
    if lua_script_state:
        try:
            state_data = json.loads(lua_script_state)
            ml = state_data.get('ml', {})
            
            if token_bag_guid in ml:
                token_bag_entry = ml[token_bag_guid]
                rot = token_bag_entry.get('rot', {})
                old_y = rot.get('y', 0)
                
                if old_y != 270.0:
                    rot['y'] = 270.0
                    card_box['LuaScriptState'] = json.dumps(state_data, separators=(',', ': '))
                    modified = True
                    print(f"  Updated token bag saved rotation in LuaScriptState: {old_y} -> 270.0")
        except json.JSONDecodeError:
            pass  # Skip if state is not valid JSON
    
    if modified:
        with open(cardbox_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    return modified


def main():
    """Main function to fix token bag rotations."""
    print("Fixing token bag rotations to 270°...")
    
    tts_objects_dir = Path("tts_objects")
    
    # Fix standalone token bag files
    print("\nProcessing standalone token bag files...")
    tokenbag_files = list(tts_objects_dir.glob("*/tokens/*-tokenbag.json"))
    modified_count = 0
    
    for tokenbag_path in sorted(tokenbag_files):
        team_slug = tokenbag_path.parent.parent.name
        print(f"\n{team_slug}:")
        
        if fix_rotation_in_tokenbag(tokenbag_path):
            modified_count += 1
        else:
            print(f"  ✓ Already at 270°")
    
    print(f"\nModified {modified_count} standalone token bag files")
    
    # Fix card box files
    print("\n" + "="*60)
    print("Processing card box files...")
    cardbox_files = list(tts_objects_dir.glob("*/*Cards.json"))
    cardbox_files = [f for f in cardbox_files if f.parent.name != 'tts_objects']
    modified_count = 0
    
    for cardbox_path in sorted(cardbox_files):
        team_slug = cardbox_path.parent.name
        print(f"\n{team_slug}:")
        
        if fix_rotation_in_cardbox(cardbox_path):
            modified_count += 1
        else:
            print(f"  ✓ Card box at 270°, token bag at 270°")
    
    print(f"\n{'='*60}")
    print(f"Complete! Modified {modified_count} card box files")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
