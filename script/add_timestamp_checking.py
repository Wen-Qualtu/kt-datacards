"""
Update card box Lua scripts to add smart timestamp checking for token bag updates.

This modifies the updateTokenBag() function to:
1. Fetch tts-token-bags.json to get the remote timestamp
2. Compare with the stored lastTokenUpdate timestamp
3. Only update if remote is newer
4. Save the new timestamp after updating
"""

import json
from pathlib import Path
import re


def slugify(text: str) -> str:
    """Convert team name to slug format."""
    return text.lower().replace(' ', '-').replace("'", '')


def update_token_bag_function_with_timestamp_check(lua_script: str, team_slug: str) -> str:
    """
    Replace the updateTokenBag function with a version that checks timestamps.
    """
    
    # GitHub URLs
    github_base = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"
    
    # New updateTokenBag function with timestamp checking
    new_function = f'''-- Token bag update function with smart timestamp checking
function updateTokenBag()
  local teamSlug = "{team_slug}"
  local TOKEN_BAG_URL = "{github_base}/tts_objects/tokens/" .. teamSlug .. "/" .. teamSlug .. "-tokenbag.json"
  local TOKEN_METADATA_URL = "{github_base}/output_v2/tts-token-bags.json"
  
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
  
  -- Check if we need to update by comparing timestamps
  if lastTokenUpdate ~= "" then
    broadcastToAll("Checking for token bag updates...", {{1, 1, 0}})
    
    -- Fetch metadata to check if update is needed
    WebRequest.get(TOKEN_METADATA_URL, function(request)
      if request.is_error then
        broadcastToAll("Could not check for token updates. Forcing refresh...", {{1, 0.5, 0}})
        performTokenUpdate(tokenBagGUID, TOKEN_BAG_URL, true)
        return
      end
      
      -- Parse JSON to find this team's last_modified timestamp
      local success, tokenMetadata = pcall(function() return JSON.decode(request.text) end)
      if not success or not tokenMetadata then
        broadcastToAll("Could not parse token metadata. Forcing refresh...", {{1, 0.5, 0}})
        performTokenUpdate(tokenBagGUID, TOKEN_BAG_URL, true)
        return
      end
      
      -- Find our team in the list
      local remoteTimestamp = ""
      for _, entry in ipairs(tokenMetadata) do
        if entry.team == teamSlug then
          remoteTimestamp = entry.last_modified or ""
          break
        end
      end
      
      if remoteTimestamp == "" then
        broadcastToAll("Could not find team in token metadata. Forcing refresh...", {{1, 0.5, 0}})
        performTokenUpdate(tokenBagGUID, TOKEN_BAG_URL, true)
        return
      end
      
      -- Compare timestamps
      if remoteTimestamp == lastTokenUpdate then
        broadcastToAll("Token bags already up to date! (Last: " .. lastTokenUpdate .. ")", {{0, 1, 0}})
        return
      else
        broadcastToAll("Token bag update available! Local: " .. lastTokenUpdate .. " | Remote: " .. remoteTimestamp, {{0, 0.7, 1}})
        performTokenUpdate(tokenBagGUID, TOKEN_BAG_URL, false, remoteTimestamp)
      end
    end)
  else
    -- No timestamp info, force update
    broadcastToAll("No token timestamp info. Forcing refresh...", {{1, 1, 0}})
    performTokenUpdate(tokenBagGUID, TOKEN_BAG_URL, true)
  end
end

-- Perform the actual token bag update
function performTokenUpdate(tokenBagGUID, tokenBagURL, skipTimestampFetch, newTimestamp)
  local cacheBust = math.random(1, 999999)
  
  broadcastToAll("Updating token bags from GitHub... Please wait.", {{1, 1, 0}})
  
  -- Fetch the token bag JSON from GitHub with cache busting
  WebRequest.get(tokenBagURL .. "?v=" .. cacheBust, function(request)
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
              -- Update timestamp if we got a new one
              if newTimestamp then
                lastTokenUpdate = newTimestamp
                updateSave()
              elseif skipTimestampFetch then
                -- Fetch timestamp from metadata if we skipped it earlier
                local TOKEN_METADATA_URL = "{github_base}/output_v2/tts-token-bags.json"
                WebRequest.get(TOKEN_METADATA_URL, function(metaRequest)
                  if not metaRequest.is_error then
                    local success, tokenMetadata = pcall(function() return JSON.decode(metaRequest.text) end)
                    if success and tokenMetadata then
                      for _, entry in ipairs(tokenMetadata) do
                        if entry.team == "{team_slug}" then
                          lastTokenUpdate = entry.last_modified or ""
                          updateSave()
                          break
                        end
                      end
                    end
                  end
                end)
              end
              
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
    
    # Find and replace the old updateTokenBag function
    # Pattern to match from "-- Token bag update function" or "function updateTokenBag()" 
    # to the end of the function (matching end before next function or click_update_rules)
    
    # Find the start of updateTokenBag
    pattern_start = r'(?:-- Token bag update function\n)?function updateTokenBag\(\)'
    match = re.search(pattern_start, lua_script)
    
    if not match:
        print(f"  WARNING: Could not find updateTokenBag function")
        return lua_script
    
    start_idx = match.start()
    
    # Find the matching end - look for the end before the next function definition
    # Count nested function/end pairs
    search_pos = match.end()
    depth = 1
    
    while depth > 0 and search_pos < len(lua_script):
        # Find next function or end
        next_func = lua_script.find('\\nfunction ', search_pos)
        next_end = lua_script.find('\\nend\\n', search_pos)
        
        if next_end == -1:
            next_end = lua_script.find('\\nend\\r\\n', search_pos)
        
        if next_end == -1:
            print(f"  WARNING: Could not find end of updateTokenBag")
            return lua_script
        
        # Check if there's a function before this end
        if next_func != -1 and next_func < next_end:
            depth += 1
            search_pos = next_func + 1
        else:
            depth -= 1
            if depth == 0:
                # This is our matching end - include it in the replacement
                end_idx = lua_script.find('\\n', next_end + 5) + 1  # +5 to skip past \\nend\\n
                break
            search_pos = next_end + 1
    
    if depth != 0:
        print(f"  WARNING: Could not find matching end for updateTokenBag")
        return lua_script
    
    # Replace the function
    updated_script = lua_script[:start_idx] + new_function + "\\r\\n" + lua_script[end_idx:]
    
    return updated_script


def update_lua_state_to_include_token_timestamp(lua_state: str) -> str:
    """Add lastTokenUpdate to the LuaScriptState if not present."""
    try:
        state = json.loads(lua_state)
        if 'lastTokenUpdate' not in state:
            state['lastTokenUpdate'] = ""
        return json.dumps(state)
    except:
        # If parsing fails, return original
        return lua_state


def update_onload_and_updatesave_functions(lua_script: str) -> str:
    """Update onload and updateSave functions to handle lastTokenUpdate."""
    
    # Update onload to load lastTokenUpdate
    # Find: lastUpdate = loaded_data.lastUpdate or ""
    # Replace with version that also loads lastTokenUpdate
    onload_pattern = r'(lastUpdate = loaded_data\.lastUpdate or "")'
    onload_replacement = r'\\1\\r\\n    lastTokenUpdate = loaded_data.lastTokenUpdate or ""'
    
    if re.search(onload_pattern, lua_script):
        lua_script = re.sub(onload_pattern, onload_replacement, lua_script)
    else:
        # Try alternate pattern in else block
        onload_pattern_else = r'(lastUpdate = ""\n    teamSlug = "")'
        onload_replacement_else = r'lastUpdate = ""\\r\\n    teamSlug = ""\\r\\n    lastTokenUpdate = ""'
        lua_script = re.sub(onload_pattern_else, onload_replacement_else, lua_script)
    
    # Update updateSave to save lastTokenUpdate
    # Find: ["lastUpdate"]=lastUpdate, ["teamSlug"]=teamSlug}
    # Replace with version that also saves lastTokenUpdate
    updatesave_pattern = r'(\\["lastUpdate"\\]=lastUpdate, \\["teamSlug"\\]=teamSlug)'
    updatesave_replacement = r'\\1, ["lastTokenUpdate"]=lastTokenUpdate'
    
    lua_script = re.sub(updatesave_pattern, updatesave_replacement, lua_script)
    
    return lua_script


def update_card_box_file(file_path: Path):
    """Update a single card box JSON file with timestamp checking."""
    print(f"Processing: {file_path.name}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if 'ObjectStates' not in data or len(data['ObjectStates']) == 0:
        print(f"  ⚠ No ObjectStates found")
        return False
    
    card_box = data['ObjectStates'][0]
    
    # Skip if no token bag
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
        print(f"  - No token dispenser bag - skipping")
        return False
    
    # Extract team slug
    team_name = token_bag['Nickname'].replace(' tokens', '')
    team_slug = slugify(team_name)
    
    # Update the Lua script
    if 'LuaScript' not in card_box:
        print(f"  ⚠ No LuaScript found")
        return False
    
    original_script = card_box['LuaScript']
    
    # Check if already has performTokenUpdate (our new version)
    if 'function performTokenUpdate(' in original_script:
        print(f"  - Already has timestamp checking")
        return False
    
    # Update the script
    updated_script = update_token_bag_function_with_timestamp_check(original_script, team_slug)
    updated_script = update_onload_and_updatesave_functions(updated_script)
    
    if updated_script != original_script:
        card_box['LuaScript'] = updated_script
        
        # Update LuaScriptState to include lastTokenUpdate
        if 'LuaScriptState' in card_box:
            card_box['LuaScriptState'] = update_lua_state_to_include_token_timestamp(card_box['LuaScriptState'])
        
        # Save the updated file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print(f"  ✓ Added timestamp checking for {team_slug}")
        return True
    else:
        print(f"  - No changes made")
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
