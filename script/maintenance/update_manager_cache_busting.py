"""
Update KT Display Manager bag to use smart timestamp-based cache busting
instead of random numbers when loading card boxes from GitHub.
"""

import json
from pathlib import Path


def update_manager_bag():
    """Update the Display Manager bag with smart cache busting."""
    manager_path = Path("dev/examples/KT Display Manager.json")
    
    if not manager_path.exists():
        print(f"❌ Manager bag not found at: {manager_path}")
        return False
    
    print(f"Loading: {manager_path.name}")
    
    with open(manager_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Get the bag object
    bag = data['ObjectStates'][0]
    lua_script = bag['LuaScript']
    
    # Replace the random cache busting with timestamp-based approach
    # Find: local cacheBust = math.random(1, 999999)
    #       local url = box.url .. "?v=" .. cacheBust
    # Replace with: Use box.last_modified timestamp (stripped to numbers)
    
    # The pattern in the JSON uses \r\n for line endings
    old_pattern = '    local box = teamBoxes[index]\r\n    local cacheBust = math.random(1, 999999)\r\n    local url = box.url .. "?v=" .. cacheBust'
    
    new_pattern = '    local box = teamBoxes[index]\r\n    -- Use timestamp for cache busting (strip non-numeric characters)\r\n    local cacheBust = box.last_modified and box.last_modified:gsub("[^0-9]", "") or math.random(1, 999999)\r\n    local url = box.url .. "?v=" .. cacheBust'
    
    if old_pattern in lua_script:
        lua_script = lua_script.replace(old_pattern, new_pattern)
        bag['LuaScript'] = lua_script
        
        # Save back
        with open(manager_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print("  ✓ Updated cache busting to use timestamps")
        print("  ℹ Now uses box.last_modified from tts-card-boxes.json")
        print("  ℹ Falls back to random if timestamp unavailable")
        return True
    else:
        print("  ⚠ Pattern not found - may already be updated or format changed")
        return False


def main():
    print("Updating KT Display Manager with smart cache busting...\n")
    
    if update_manager_bag():
        print("\n✓ Manager bag updated successfully!")
        print("\nNote: The bag itself won't auto-update in existing saves.")
        print("Users will need to replace it manually or from the workshop.")
    else:
        print("\n✗ Update failed - check the pattern manually")


if __name__ == '__main__':
    main()
