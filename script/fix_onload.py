import json
from pathlib import Path

def fix_onload_function():
    tts_objects_dir = Path("tts_objects")
    card_boxes = list(tts_objects_dir.glob("*Cards.json"))
    
    print(f"Found {len(card_boxes)} card boxes")
    
    fixed_count = 0
    
    for card_box_path in card_boxes:
        with open(card_box_path, 'r', encoding='utf-8') as f:
            content = f.read()
            data = json.loads(content)
        
        print(f"Processing: {card_box_path.stem}")
        
        lua_script = data['ObjectStates'][0]['LuaScript']
        
        # The corrupted pattern has literal backslash-one then backslash-r-backslash-n
        # In the string that's: chr(92) + chr(49) + chr(92) + chr(114) + chr(92) + chr(110)
        # Which is: \1\r\n when printed
        corrupted_pattern = r"relativeRotation = loaded_data.rr" + "\r\n    " + r"\1\r\n" + "    lastTokenUpdate"
        
        if corrupted_pattern in lua_script:
            # Fix it
            fixed_script = lua_script.replace(
                corrupted_pattern,
                r"relativeRotation = loaded_data.rr" + "\r\n    lastCardUpdate = loaded_data.lastCardUpdate or \"\"\r\n    lastTokenUpdate"
            )
            
            data['ObjectStates'][0]['LuaScript'] = fixed_script
            
            with open(card_box_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            print(f"  ✓ Fixed corrupted onload in {card_box_path.name}")
            fixed_count += 1
        else:
            # Also check for else branch that might be missing lastTokenUpdate
            else_pattern = r'memoryList = {}' + "\r\n    relativeRotation = readRotation()\r\n    lastCardUpdate = \"\"\r\n    teamSlug = \"\""
            if else_pattern in lua_script:
                # Add lastTokenUpdate to else block
                fixed_script = lua_script.replace(
                    else_pattern,
                    r'memoryList = {}' + "\r\n    relativeRotation = readRotation()\r\n    lastCardUpdate = \"\"\r\n    lastTokenUpdate = \"\"\r\n    teamSlug = \"\""
                )
                
                data['ObjectStates'][0]['LuaScript'] = fixed_script
                
                with open(card_box_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                
                print(f"  ✓ Added lastTokenUpdate to else block in {card_box_path.name}")
                fixed_count += 1
    
    print(f"\n✓ Done - Fixed {fixed_count} files")

if __name__ == "__main__":
    fix_onload_function()
