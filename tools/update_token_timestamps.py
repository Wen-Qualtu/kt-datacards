"""
Clean approach to add timestamp checking to card boxes.

This script:
1. Removes the old updateTokenBag function completely
2. Adds the new version with timestamp checking
3. Updates onload and updateSave functions
4. Updates LuaScriptState
"""

import json
from pathlib import Path


def slugify(text: str) -> str:
    """Convert team name to slug format."""
    return text.lower().replace(' ', '-').replace("'", '')


def get_new_token_update_functions(team_slug: str) -> str:
    """Generate the new token update functions with timestamp checking."""
    github_base = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"
    
    return f'''
-- Token bag update function with smart timestamp checking
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
function performTokenUpdate(tokenBagGUID, tokenBagURL, fetchTimestamp, newTimestamp)
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
              -- Update timestamp
              if newTimestamp then
                lastTokenUpdate = newTimestamp
                updateSave()
                broadcastToAll("Token bags updated successfully!", {{0, 1, 0}})
              elseif fetchTimestamp then
                -- Fetch timestamp from metadata
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
                  broadcastToAll("Token bags updated successfully!", {{0, 1, 0}})
                end)
              else
                broadcastToAll("Token bags updated successfully!", {{0, 1, 0}})
              end
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


def update_card_box(file_path: Path):
    """Update a single card box with timestamp checking."""
    print(f"Processing: {file_path.name}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if 'ObjectStates' not in data or len(data['ObjectStates']) == 0:
        return False
    
    card_box = data['ObjectStates'][0]
    
    # Find token bag
    token_bag = None
    if 'ContainedObjects' in card_box:
        for obj in card_box['ContainedObjects']:
            if obj.get('Nickname', '').endswith(' tokens') and obj.get('Name') == 'Custom_Model_Bag':
                token_bag = obj
                break
    
    if not token_bag:
        print(f"  - No tokens")
        return False
    
    team_name = token_bag['Nickname'].replace(' tokens', '')
    team_slug = slugify(team_name)
    
    # Update Lua script
    lua_script = card_box.get('LuaScript', '')
    
    # Remove old token update functions
    # Find "-- Token bag update function" or "function updateTokenBag()" and remove everything until next major function
    start_markers = [
        '\\n-- Token bag update function\\n',
        '\\n\\n-- Token bag update function\\n',
        '\\nfunction updateTokenBag()\\n'
    ]
    
    for marker in start_markers:
        if marker in lua_script:
            start_idx = lua_script.find(marker)
            # Find the end - look for the next "function click_" or end of script
            end_idx = lua_script.find('\\nfunction click_', start_idx + 1)
            if end_idx == -1:
                end_idx = len(lua_script)
            
            # Remove the old function
            lua_script = lua_script[:start_idx] + lua_script[end_idx:]
            break
    
    # Add new functions before click_update_rules
    insert_pos = lua_script.find('\\nfunction click_update_rules()')
    if insert_pos == -1:
        insert_pos = lua_script.find('function click_update_rules()')
    
    if insert_pos == -1:
        print(f"  ⚠ Could not find click_update_rules")
        return False
    
    new_functions = get_new_token_update_functions(team_slug)
    lua_script = lua_script[:insert_pos] + new_functions + '\\r\\n' + lua_script[insert_pos:]
    
    # Update onload function to load lastTokenUpdate
    if 'lastUpdate = loaded_data.lastUpdate or ""' in lua_script:
        lua_script = lua_script.replace(
            'lastUpdate = loaded_data.lastUpdate or ""',
            'lastUpdate = loaded_data.lastUpdate or ""\\r\\n    lastTokenUpdate = loaded_data.lastTokenUpdate or ""'
        )
    
    if 'lastUpdate = ""\\r\\n    teamSlug = ""' in lua_script:
        lua_script = lua_script.replace(
            'lastUpdate = ""\\r\\n    teamSlug = ""',
            'lastUpdate = ""\\r\\n    teamSlug = ""\\r\\n    lastTokenUpdate = ""'
        )
    
    # Update updateSave function to save lastTokenUpdate
    if '["lastUpdate"]=lastUpdate, ["teamSlug"]=teamSlug}' in lua_script:
        lua_script = lua_script.replace(
            '["lastUpdate"]=lastUpdate, ["teamSlug"]=teamSlug}',
            '["lastUpdate"]=lastUpdate, ["teamSlug"]=teamSlug, ["lastTokenUpdate"]=lastTokenUpdate}'
        )
    
    card_box['LuaScript'] = lua_script
    
    # Update LuaScriptState
    try:
        state = json.loads(card_box.get('LuaScriptState', '{}'))
        if 'lastTokenUpdate' not in state:
            state['lastTokenUpdate'] = ""
            card_box['LuaScriptState'] = json.dumps(state)
    except:
        pass
    
    # Save
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    print(f"  ✓ Updated {team_slug}")
    return True


def main():
    tts_dir = Path('tts_objects')
    card_boxes = list(tts_dir.glob('*Cards.json'))
    
    print(f"Found {len(card_boxes)} card boxes\\n")
    
    updated = 0
    for box in sorted(card_boxes):
        if update_card_box(box):
            updated += 1
    
    print(f"\\n✓ Updated {updated} card boxes")


if __name__ == '__main__':
    main()
