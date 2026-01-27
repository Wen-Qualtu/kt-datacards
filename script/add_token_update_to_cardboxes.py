"""
Add token bag update functionality to all card box JSON files.

This script adds a function to update token bags by fetching them from GitHub
and respawning them with cache-busting.
"""

import json
from pathlib import Path
import re


def slugify(text: str) -> str:
    """Convert team name to slug format."""
    return text.lower().replace(' ', '-').replace("'", '')


def add_token_update_function(lua_script: str, team_slug: str) -> str:
    """
    Add token bag update function to the Lua script.
    
    The function will:
    1. Find the token dispenser bag
    2. Fetch the updated JSON from GitHub
    3. Destroy the old bag and spawn the new one
    4. Put it back in the card box
    """
    
    # GitHub base URL
    github_base = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"
    
    # Function to update token bags
    token_update_function = f'''
-- Token bag update function
function updateTokenBag()
  local teamSlug = "{team_slug}"
  local TOKEN_BAG_URL = "{github_base}/tts_objects/tokens/" .. teamSlug .. "/" .. teamSlug .. "-tokenbag.json"
  local cacheBust = math.random(1, 999999)
  
  -- Find the token dispenser bag
  local bagObjList = self.getObjects()
  local tokenBagGUID = nil
  
  for _, obj in ipairs(bagObjList) do
    if obj.nickname and obj.nickname:match(" tokens$") then
      tokenBagGUID = obj.guid
      break
    end
  end
  
  if not tokenBagGUID then
    broadcastToAll("Token bag not found in card box", {{1, 0.5, 0}})
    return
  end
  
  broadcastToAll("Updating token bags from GitHub... Please wait.", {{1, 1, 0}})
  
  -- Fetch the token bag JSON from GitHub with cache busting
  WebRequest.get(TOKEN_BAG_URL .. "?v=" .. cacheBust, function(request)
    if request.is_error then
      broadcastToAll("Could not fetch token bag: " .. request.error, {{1, 0, 0}})
      return
    end
    
    -- Parse the JSON
    local success, tokenBagData = pcall(function() return JSON.decode(request.text) end)
    if not success or not tokenBagData or not tokenBagData.ObjectStates or #tokenBagData.ObjectStates == 0 then
      broadcastToAll("Could not parse token bag JSON", {{1, 0, 0}})
      return
    end
    
    -- Get the token bag object data
    local newTokenBagData = tokenBagData.ObjectStates[1]
    
    -- Take out the old token bag
    local oldTokenBag = self.takeObject({{
      guid = tokenBagGUID,
      position = self.getPosition() + Vector(0, 10, 0),
      smooth = false
    }})
    
    Wait.condition(
      function()
        -- Remember the old position and rotation
        local oldPos = oldTokenBag.getPosition()
        local oldRot = oldTokenBag.getRotation()
        
        -- Destroy the old bag
        oldTokenBag.destruct()
        
        -- Spawn the new token bag
        local newTokenBag = spawnObjectData({{
          data = newTokenBagData,
          position = oldPos,
          rotation = oldRot
        }})
        
        Wait.condition(
          function()
            -- Put it back in the card box
            self.putObject(newTokenBag)
            
            Wait.time(function()
              broadcastToAll("Token bags updated successfully!", {{0, 1, 0}})
            end, 0.5)
          end,
          function() return newTokenBag ~= nil and not newTokenBag.spawning end,
          5,
          function() broadcastToAll("Timeout spawning new token bag", {{1, 0, 0}}) end
        )
      end,
      function() return oldTokenBag ~= nil and not oldTokenBag.spawning end,
      5,
      function() broadcastToAll("Timeout taking out old token bag", {{1, 0, 0}}) end
    )
  end)
end
'''
    
    # Find where to insert the function - before the click_update_rules function
    insert_marker = "function click_update_rules()"
    insert_pos = lua_script.find(insert_marker)
    
    if insert_pos == -1:
        print(f"  WARNING: Could not find click_update_rules function for {team_slug}")
        return lua_script
    
    # Insert the new function before click_update_rules
    updated_script = lua_script[:insert_pos] + token_update_function + "\\r\\n" + lua_script[insert_pos:]
    
    # Now modify click_update_rules to call updateTokenBag after performUpdate completes
    # We need to add a call at the end of performUpdate
    # Find the line where it says "Update complete! All X cards..."
    success_message_pattern = r'broadcastToAll\("Update complete! All " \.\. processedCount \.\. " cards, box texture, and mesh refreshed\."'
    
    # Replace with a version that also updates tokens
    replacement = 'broadcastToAll("Update complete! All " .. processedCount .. " cards, box texture, and mesh refreshed. Now updating tokens...", {0, 1, 0})\\r\\n        Wait.time(function() updateTokenBag() end, 1.0)'
    
    updated_script = re.sub(success_message_pattern, replacement, updated_script)
    
    return updated_script


def update_card_box_file(file_path: Path):
    """Update a single card box JSON file with token bag update functionality."""
    print(f"Processing: {file_path.name}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if 'ObjectStates' not in data or len(data['ObjectStates']) == 0:
        print(f"  ⚠ No ObjectStates found")
        return False
    
    card_box = data['ObjectStates'][0]
    
    if 'ContainedObjects' not in card_box:
        print(f"  ⚠ No ContainedObjects found")
        return False
    
    # Find the token dispenser bag to get the team slug
    token_bag = None
    for obj in card_box['ContainedObjects']:
        nickname = obj.get('Nickname', '')
        if nickname.endswith(' tokens') and obj.get('Name') == 'Custom_Model_Bag':
            token_bag = obj
            break
    
    if not token_bag:
        print(f"  ⚠ No token dispenser bag found - skipping")
        return False
    
    # Extract team slug
    team_name = token_bag['Nickname'].replace(' tokens', '')
    team_slug = slugify(team_name)
    
    # Update the Lua script
    if 'LuaScript' in card_box:
        original_script = card_box['LuaScript']
        
        # Check if already has updateTokenBag function
        if 'function updateTokenBag()' in original_script:
            print(f"  - Already has token bag update function")
            return False
        
        updated_script = add_token_update_function(original_script, team_slug)
        
        if updated_script != original_script:
            card_box['LuaScript'] = updated_script
            
            # Save the updated file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            print(f"  ✓ Added token bag update for {team_slug}")
            return True
        else:
            print(f"  - No changes made")
            return False
    else:
        print(f"  ⚠ No LuaScript found")
        return False


def main():
    tts_objects_dir = Path('tts_objects')
    
    if not tts_objects_dir.exists():
        print(f"Error: {tts_objects_dir} directory not found")
        return
    
    # Find all card box JSON files
    card_box_files = list(tts_objects_dir.glob('*Cards.json'))
    
    if not card_box_files:
        print("No card box files found")
        return
    
    print(f"Found {len(card_box_files)} card box files\\n")
    
    updated_count = 0
    for file_path in sorted(card_box_files):
        try:
            if update_card_box_file(file_path):
                updated_count += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\\n✓ Updated {updated_count} of {len(card_box_files)} files")


if __name__ == '__main__':
    main()
