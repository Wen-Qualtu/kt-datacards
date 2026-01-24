"""
Script to update all card box JSON files to add token bag updating functionality.

This script modifies the performUpdate function in each card box's Lua script
to also update token bags (nested infinite bags) with cache-busting URLs.
"""

import json
from pathlib import Path


def update_lua_script(lua_script: str) -> str:
    """
    Update the Lua script to add token bag updating functionality.
    
    Modifies the performUpdate function to:
    1. Detect nested bags (token dispenser bags)
    2. Update token bags inside them with cache-busting URLs
    3. Respawn the token dispenser bag with updated contents
    """
    
    # The updated performUpdate function that handles nested token bags
    new_perform_update = r"""function performUpdate(newTimestamp)
  local bagObjList = self.getObjects()
  broadcastToAll("Updating rules, tokens, and box texture... Please wait and do NOT click other buttons.", {1, 1, 0})
  
  local cacheBust = math.random(1, 999999)
  local processedCount = 0
  local totalToProcess = #bagObjList
  local initialBagCount = totalToProcess
  
  -- Clone the bag contents list
  local objectsToUpdate = {}
  for _, obj in ipairs(bagObjList) do
    table.insert(objectsToUpdate, obj.guid)
  end

  -- Helper function to check if object is in bag by GUID
  local function isObjectInBag(newGuid)
    local bagContents = self.getObjects()
    for _, item in ipairs(bagContents) do
      if item.guid == newGuid then
        return true
      end
    end
    return false
  end
  
  -- Helper function to update token bags (nested infinite bags)
  local function updateTokenBag(bagObj)
    local bagData = bagObj.getData()
    local updated = false
    
    -- Update the token dispenser bag's own mesh
    if bagData.CustomMesh and bagData.CustomMesh.MeshURL then
      bagData.CustomMesh.MeshURL = bagData.CustomMesh.MeshURL:gsub("%?v=%d+", "") .. "?v=" .. cacheBust
      updated = true
    end
    
    -- Update each contained token bag
    if bagData.ContainedObjects then
      for _, tokenBag in ipairs(bagData.ContainedObjects) do
        -- Update token bag mesh
        if tokenBag.CustomMesh and tokenBag.CustomMesh.MeshURL then
          tokenBag.CustomMesh.MeshURL = tokenBag.CustomMesh.MeshURL:gsub("%?v=%d+", "") .. "?v=" .. cacheBust
        end
        
        -- Update contained tokens
        if tokenBag.ContainedObjects then
          for _, token in ipairs(tokenBag.ContainedObjects) do
            if token.CustomImage and token.CustomImage.ImageURL then
              token.CustomImage.ImageURL = token.CustomImage.ImageURL:gsub("%?v=%d+", "") .. "?v=" .. cacheBust
            end
          end
        end
      end
    end
    
    return updated, bagData
  end
  
  -- Process objects one at a time sequentially
  local function processNextObject(index)
    if index > #objectsToUpdate then
      -- All done - now update the bag texture and mesh last
      Wait.time(function()
        local bagCustom = self.getCustomObject()
        if bagCustom then
          if bagCustom.diffuse then
            bagCustom.diffuse = bagCustom.diffuse:gsub("%?v=%d+", "") .. "?v=" .. cacheBust
          end
          if bagCustom.mesh then
            bagCustom.mesh = bagCustom.mesh:gsub("%?v=%d+", "") .. "?v=" .. cacheBust
          end
          self.setCustomObject(bagCustom)
          self.reload()
        end
        
        -- Update timestamp if we got a new one
        if newTimestamp then
          lastUpdate = newTimestamp
          updateSave()
        end
        
        broadcastToAll("Update complete! All " .. processedCount .. " objects, tokens, box texture, and mesh refreshed.", {0, 1, 0})
      end, 0.5)
      return
    end
    
    local guid = objectsToUpdate[index]
    local obj = self.takeObject({guid = guid, position = self.getPosition() + Vector(0, 10, 0), smooth = false})
    
    Wait.condition(
      function()
        local newGuid = nil
        
        if obj.type == "Deck" then
          local deckData = obj.getData()
          if deckData.CustomDeck then
            for deckID, deck in pairs(deckData.CustomDeck) do
              deck.FaceURL = deck.FaceURL:gsub("%?v=%d+", "") .. "?v=" .. cacheBust
              deck.BackURL = deck.BackURL:gsub("%?v=%d+", "") .. "?v=" .. cacheBust
            end
            
            obj.destruct()
            local newDeck = spawnObjectData({data = deckData, position = self.getPosition() + Vector(0, 10, 0)})
            
            Wait.condition(
              function()
                newGuid = newDeck.getGUID()
                self.putObject(newDeck)
                processedCount = processedCount + 1
                broadcastToAll("Updated " .. processedCount .. " of " .. totalToProcess, {0, 0.7, 1})
                
                Wait.condition(
                  function()
                    processNextObject(index + 1)
                  end,
                  function()
                    return isObjectInBag(newGuid)
                  end,
                  10
                )
              end,
              function() return newDeck ~= nil and not newDeck.spawning end,
              5
            )
          else
            newGuid = obj.getGUID()
            self.putObject(obj)
            processedCount = processedCount + 1
            
            Wait.condition(
              function()
                processNextObject(index + 1)
              end,
              function()
                return isObjectInBag(newGuid)
              end,
              10
            )
          end
        elseif obj.type == "Bag" then
          -- This is a nested bag (likely a token dispenser bag)
          local updated, bagData = updateTokenBag(obj)
          
          if updated then
            local oldPos = obj.getPosition()
            obj.destruct()
            local newBag = spawnObjectData({data = bagData, position = oldPos})
            
            Wait.condition(
              function()
                newGuid = newBag.getGUID()
                self.putObject(newBag)
                processedCount = processedCount + 1
                broadcastToAll("Updated " .. processedCount .. " of " .. totalToProcess .. " (including token bags)", {0, 0.7, 1})
                
                Wait.condition(
                  function()
                    processNextObject(index + 1)
                  end,
                  function()
                    return isObjectInBag(newGuid)
                  end,
                  10
                )
              end,
              function() return newBag ~= nil and not newBag.spawning end,
              5
            )
          else
            newGuid = obj.getGUID()
            self.putObject(obj)
            processedCount = processedCount + 1
            
            Wait.condition(
              function()
                processNextObject(index + 1)
              end,
              function()
                return isObjectInBag(newGuid)
              end,
              10
            )
          end
        else
          local customObj = obj.getCustomObject()
          if customObj and (customObj.face or customObj.back) then
            if customObj.face then
              customObj.face = customObj.face:gsub("%?v=%d+", "") .. "?v=" .. cacheBust
            end
            if customObj.back then
              customObj.back = customObj.back:gsub("%?v=%d+", "") .. "?v=" .. cacheBust
            end
            obj.setCustomObject(customObj)
            obj.reload()
            
            Wait.time(function()
              newGuid = obj.getGUID()
              self.putObject(obj)
              processedCount = processedCount + 1
              broadcastToAll("Updated " .. processedCount .. " of " .. totalToProcess, {0, 0.7, 1})
              
              Wait.condition(
                function()
                  processNextObject(index + 1)
                end,
                function()
                  return isObjectInBag(newGuid)
                end,
                10
              )
            end, 0.5)
          else
            newGuid = obj.getGUID()
            self.putObject(obj)
            processedCount = processedCount + 1
            
            Wait.condition(
              function()
                processNextObject(index + 1)
              end,
              function()
                return isObjectInBag(newGuid)
              end,
              10
            )
          end
        end
      end,
      function() return obj ~= nil and not obj.spawning end,
      5
    )
  end
  
  -- Start processing first object
  processNextObject(1)
end"""
    
    # Find and replace the performUpdate function
    # Look for "function performUpdate" and find the matching "end"
    start_marker = "function performUpdate("
    start_idx = lua_script.find(start_marker)
    
    if start_idx == -1:
        print("WARNING: Could not find performUpdate function")
        return lua_script
    
    # Find the matching end for this function
    # Count function/end pairs to find the right end
    func_count = 0
    search_start = start_idx
    end_idx = -1
    
    while True:
        next_func = lua_script.find("function ", search_start + 1)
        next_end = lua_script.find("\r\nend\r\n", search_start + 1)
        
        if next_end == -1:
            # Try without \r\n
            next_end = lua_script.find("\nend\n", search_start + 1)
            if next_end == -1:
                next_end = lua_script.find("\nend", search_start + 1)
        
        if next_end == -1:
            print("WARNING: Could not find end of performUpdate function")
            return lua_script
        
        # Check if there's a function before this end
        if next_func != -1 and next_func < next_end:
            func_count += 1
            search_start = next_func
        else:
            if func_count == 0:
                # This is our matching end
                end_idx = next_end
                break
            else:
                func_count -= 1
                search_start = next_end
    
    # Include the "end" in our replacement
    end_idx = lua_script.find("\n", end_idx) + 1
    
    # Replace the function
    updated_script = lua_script[:start_idx] + new_perform_update + "\r\n" + lua_script[end_idx:]
    
    return updated_script


def update_card_box_file(file_path: Path):
    """Update a single card box JSON file."""
    print(f"Processing: {file_path.name}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Update the LuaScript in ObjectStates[0]
    if 'ObjectStates' in data and len(data['ObjectStates']) > 0:
        card_box = data['ObjectStates'][0]
        
        if 'LuaScript' in card_box:
            original_script = card_box['LuaScript']
            updated_script = update_lua_script(original_script)
            
            if updated_script != original_script:
                card_box['LuaScript'] = updated_script
                
                # Save the updated file
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                
                print(f"  ✓ Updated {file_path.name}")
            else:
                print(f"  - No changes needed for {file_path.name}")
        else:
            print(f"  ⚠ No LuaScript found in {file_path.name}")
    else:
        print(f"  ⚠ Invalid structure in {file_path.name}")


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
    
    print(f"Found {len(card_box_files)} card box files\n")
    
    for file_path in sorted(card_box_files):
        update_card_box_file(file_path)
    
    print(f"\n✓ Processed {len(card_box_files)} files")


if __name__ == '__main__':
    main()
