"""
Update card boxes for consistency and better cache busting:
1. Rename lastUpdate -> lastCardUpdate
2. Use timestamps for cache busting instead of random numbers
"""

import json
from pathlib import Path
import re


def update_card_box(file_path: Path):
    """Update a single card box with the new naming and cache busting."""
    print(f"Processing: {file_path.name}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if 'ObjectStates' not in data or len(data['ObjectStates']) == 0:
        return False
    
    card_box = data['ObjectStates'][0]
    
    # Update Lua script
    lua_script = card_box.get('LuaScript', '')
    if not lua_script:
        return False
    
    # 1. Rename lastUpdate to lastCardUpdate (all occurrences)
    lua_script = lua_script.replace('lastUpdate', 'lastCardUpdate')
    
    # 2. Update card cache busting to use timestamp
    # In performUpdate function, change cache bust from random to timestamp
    # Find: local cacheBust = math.random(1, 999999)
    # After: local cacheBust = (lastCardUpdate or ""):gsub("[^0-9]", "")
    
    # For the main performUpdate function (cards)
    lua_script = re.sub(
        r'function performUpdate\(newTimestamp\)\s*\n\s*local bagObjList = self\.getObjects\(\)\s*\n\s*broadcastToAll\("Updating rules[^"]*"\s*,\s*\{1,\s*1,\s*0\}\)\s*\n\s*\n\s*local cacheBust = math\.random\(1,\s*999999\)',
        r'function performUpdate(newTimestamp)\n  local bagObjList = self.getObjects()\n  broadcastToAll("Updating rules and box texture... Please wait and do NOT click other buttons.", {1, 1, 0})\n  \n  local cacheBust = newTimestamp or (lastCardUpdate or ""):gsub("[^0-9]", "")',
        lua_script
    )
    
    # 3. Update token cache busting to use timestamp
    # In performTokenUpdate function
    lua_script = re.sub(
        r'function performTokenUpdate\(tokenBagGUID,\s*tokenBagURL,\s*fetchTimestamp,\s*newTimestamp\)\s*\n\s*local cacheBust = math\.random\(1,\s*999999\)',
        r'function performTokenUpdate(tokenBagGUID, tokenBagURL, fetchTimestamp, newTimestamp)\n  local cacheBust = newTimestamp or (lastTokenUpdate or ""):gsub("[^0-9]", "")',
        lua_script
    )
    
    card_box['LuaScript'] = lua_script
    
    # Update LuaScriptState
    lua_state = card_box.get('LuaScriptState', '')
    if lua_state:
        try:
            state = json.loads(lua_state)
            # Rename lastUpdate to lastCardUpdate if it exists
            if 'lastUpdate' in state:
                state['lastCardUpdate'] = state.pop('lastUpdate')
                card_box['LuaScriptState'] = json.dumps(state)
        except:
            pass
    
    # Save
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    print(f"  ✓ Updated")
    return True


def main():
    tts_dir = Path('tts_objects')
    card_boxes = list(tts_dir.glob('*/*Cards.json'))
    
    print(f"Found {len(card_boxes)} card boxes\\n")
    
    updated = 0
    for box in sorted(card_boxes):
        try:
            if update_card_box(box):
                updated += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    print(f"\\n✓ Updated {updated} card boxes")


if __name__ == '__main__':
    main()
