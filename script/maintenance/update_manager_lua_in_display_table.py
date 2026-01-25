"""Update the Manager bag's LuaScript in the display table JSON."""

import json
from pathlib import Path

def main():
    workspace_dir = Path(__file__).parent.parent
    display_table_path = workspace_dir / "tts_objects" / "display-table" / "kt_all_teams_grid.json"
    lua_template_path = workspace_dir / "config" / "defaults" / "tts-script" / "display-table-manager-script.lua"
    
    # Load the template Lua script
    with open(lua_template_path, 'r', encoding='utf-8') as f:
        new_lua = f.read()
    
    # Load the display table JSON
    with open(display_table_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Find and update the Manager bag
    updated = False
    for obj in data.get('ObjectStates', []):
        if obj.get('Nickname') == 'KT Display Manager' and obj.get('Name') == 'Bag':
            obj['LuaScript'] = new_lua
            updated = True
            print(f"✓ Updated Manager bag LuaScript")
            break
    
    if not updated:
        print("✗ Manager bag not found!")
        return
    
    # Save the updated JSON
    with open(display_table_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Display table saved")

if __name__ == '__main__':
    main()
