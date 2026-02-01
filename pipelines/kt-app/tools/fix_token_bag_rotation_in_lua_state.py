"""Fix token bag rotation in card box LuaScriptState.

The token bags are rotated to 270° in their Transform, but the card box's
LuaScriptState memory list still has them at 180°. This script updates the
rotation in the memory list to match the actual rotation.
"""

import json
from pathlib import Path


def fix_token_bag_rotation(card_box_path: Path) -> bool:
    """Fix token bag rotation in LuaScriptState to match Transform rotation."""
    
    with open(card_box_path, 'r') as f:
        data = json.load(f)
    
    if 'ObjectStates' not in data or len(data['ObjectStates']) == 0:
        return False
    
    card_box = data['ObjectStates'][0]
    
    # Get the card box's LuaScriptState
    lua_state_str = card_box.get('LuaScriptState', '')
    if not lua_state_str:
        return False
    
    try:
        lua_state = json.loads(lua_state_str)
    except json.JSONDecodeError:
        return False
    
    if 'ml' not in lua_state:
        return False
    
    # Find token bags in ContainedObjects
    contained_objects = card_box.get('ContainedObjects', [])
    modified = False
    
    for obj in contained_objects:
        # Look for token bags (Custom_Model_Bag)
        if obj.get('Name') == 'Custom_Model_Bag' and 'tokens' in obj.get('Nickname', '').lower():
            guid = obj.get('GUID')
            transform_rot_y = obj.get('Transform', {}).get('rotY', 0)
            
            # Check if this GUID is in the memory list
            if guid in lua_state['ml']:
                current_rot_y = lua_state['ml'][guid]['rot']['y']
                
                # If rotation doesn't match, fix it
                if abs(current_rot_y - transform_rot_y) > 0.1:
                    print(f"  Token bag '{obj.get('Nickname')}' (GUID: {guid})")
                    print(f"    Current memory rot.y: {current_rot_y}")
                    print(f"    Transform rotY: {transform_rot_y}")
                    print(f"    → Updating to {transform_rot_y}")
                    
                    lua_state['ml'][guid]['rot']['y'] = transform_rot_y
                    modified = True
    
    if modified:
        # Save the updated LuaScriptState
        card_box['LuaScriptState'] = json.dumps(lua_state)
        
        with open(card_box_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return True
    
    return False


def main():
    """Find and fix all card box files."""
    tts_objects_dir = Path('tts_objects')
    
    if not tts_objects_dir.exists():
        print(f"Error: {tts_objects_dir} not found")
        return
    
    print("Scanning for card box files with token bags...")
    
    modified_count = 0
    
    # Find all team directories
    for team_dir in sorted(tts_objects_dir.iterdir()):
        if not team_dir.is_dir():
            continue
        
        # Find card box JSON files
        for json_file in team_dir.glob('*.json'):
            if 'Cards.json' in json_file.name:
                team_name = json_file.stem.replace(' Cards', '')
                
                if fix_token_bag_rotation(json_file):
                    print(f"✓ Modified {team_name}")
                    modified_count += 1
    
    print(f"\nComplete! Modified {modified_count} card boxes")


if __name__ == '__main__':
    main()
