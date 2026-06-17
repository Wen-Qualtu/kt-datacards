-- constants

local SCRIPT_VERSION = "v2.0"

-- Workshop table detection - looks for unique tag on that specific table
local WORKSHOP_TABLE_TAG = "KT_Ploy_Holders"

-- Custom placement positions for workshop table
local WORKSHOP_POSITIONS = {
  Blue = {
    strategy_ploys = {
      {x=-18.00, y=1, z=-27.00},
      {x=-13.23, y=1, z=-27.05},
      {x=-8.73, y=1, z=-27.05},
      {x=-4.23, y=1, z=-27.05}
    },
    firefight_ploys = {
      {x=-17.75, y=1, z=-37.69},
      {x=-13.25, y=1, z=-37.69},
      {x=-8.75, y=1, z=-37.69},
      {x=-4.25, y=1, z=-37.69}
    },
    faction_rules = {
      {x=1.83, y=1, z=-37.63}, -- First: Astartes
      {x=5.61, y=1, z=-37.63}, -- Second: Marks of Chaos
      {x=9.88, y=1, z=-37.63}  -- Rest: Deck at this position
    },
    equipment = {
      {x=1.07, y=1, z=-27.04}
    },
    datacards = {
      {x=-26.88, y=1, z=-22.71}
    },
    token_guide = {
      {x=-28.41, y=1, z=-27.87}
    },
    token_bag = {
      {x=-26.41, y=1, z=-28.47}
    },
    operative_selection = {
      {x=-31.18, y=1, z=-22.63}
    },
    dice_dark  = { {x=31.00, y=0.73, z=-10.75} },
    dice_light = { {x=31.00, y=0.73, z=-11.50} },
    dice_team  = { {x=31.00, y=0.73, z=-12.25} }
  },
  Red = {
    strategy_ploys = {
      {x=-18.01, y=1, z=27.00},
      {x=-13.51, y=1, z=27.00},
      {x=-9.01, y=1, z=27.00},
      {x=-4.51, y=1, z=27.00}
    },
    firefight_ploys = {
      {x=-17.95, y=1, z=37.58},
      {x=-13.45, y=1, z=37.58},
      {x=-8.95, y=1, z=37.59},
      {x=-4.45, y=1, z=37.58}
    },
    faction_rules = {
      {x=1.27, y=1, z=37.59}, -- First: Astartes
      {x=5.46, y=1, z=37.56}, -- Second: Khorne (marks of chaos)
      {x=9.66, y=1, z=37.56}  -- Rest: Deck at this position
    },
    equipment = {
      {x=0.73, y=1, z=27.08}
    },
    datacards = {
      {x=-26.50, y=1, z=22.21}
    },
    token_guide = {
      {x=-29.98, y=1, z=25.45}
    },
    token_bag = {
      {x=-27.76, y=1, z=26.15}
    },
    operative_selection = {
      {x=-30.27, y=1, z=22.32}
    },
    dice_dark  = { {x=31.00, y=0.73, z=10.75} },
    dice_light = { {x=31.00, y=0.73, z=11.50} },
    dice_team  = { {x=31.00, y=0.73, z=12.25} }
  }
}

local BUTTON_SETUP_TOKENS = {
  label="Reset",
  click_function="click_setup", function_owner=self,
  position={0,0.3,-2}, rotation={0,180,0},
  height=350, width=800,
  font_size=250, color={0,0,0}, font_color={1,1,1}
}
local BUTTON_SETUP_BOX = {
  label="Reset",
  click_function="click_setup",
  function_owner=self,
  position={-2,-2.5,-1}, rotation={0,270,0},
  height=350, width=800,
  font_size=250, color={0,0,0}, font_color={1,1,1}
}
local BUTTON_RECALL = {
  label="Recall",
  click_function="click_recall", function_owner=self,
  position={1.75,-2.5,-1}, rotation={0,270,0},
  height=350, width=800,
  font_size=250, color={1,0,0}, font_color={1,1,1}
}
local BUTTON_PLACE = {
  label="Place",
  click_function="click_place",
  function_owner=self,
  position={1.75,-2.5,1}, rotation={0,270,0},
  height=350, width=800,
  font_size=250, color={0.2,0.95,0}, font_color={0,0,0}
}
local BUTTON_PLACE_KT_TABLE = {
  label="KT table",
  click_function="click_place_kt_table",
  function_owner=self,
  position={0,-2.5,2.5}, rotation={0,180,0},
  height=350, width=800,
  font_size=200, color={0.95,0.6,0}, font_color={0,0,0}
}
local BUTTON_UPDATE = {
  label="Update",
  click_function="click_update_rules",
  function_owner=self,
  position={-2,-2.5,1}, rotation={0,270,0},
  height=350, width=800,
  font_size=250, color={0,0.5,1}, font_color={1,1,1}
}
local BUTTON_CANCEL = {
  label="Cancel",
  click_function="click_cancel",
  function_owner=self,
  position={0,0.3,-2}, rotation={0,180,0},
  height=350, width=1100,
  font_size=250, color={0,0,0}, font_color={1,1,1}
}
local BUTTON_SUBMIT = {
  label="Submit",
  click_function="click_submit", function_owner=self,
  position={0,0.3,-2.8}, rotation={0,180,0},
  height=350, width=1100,
  font_size=250, color={0,0,0}, font_color={1,1,1}
}
local BUTTON_RESET = {
  label="Reset",
  click_function="click_reset",
  function_owner=self,
  position={-2,0.3,0}, rotation={0,270,0},
  height=350, width=800,
  font_size=250, color={0,0,0}, font_color={1,1,1}
}

-- functional utils
local function transmute(t, vfn, kfn)
    local out = {}
    local c = 1
    for k,v in pairs(t) do
        local value = vfn(v,c,t)
        local key = kfn ~= nil and kfn(v,c,t) or k
        if (value and key) then
            out[key] = value
        end
        c = c + 1
    end
    return out
end

local function round(num, dec)
  local mult = 10^(dec or 0)
  return math.floor(num * mult + 0.5) / mult
end

-- object utils
local function setOutline(list, enabled)
  local count = 0

  if (next(list) == nil) then
    return count
  end

  for guid in pairs(list) do
    count = count + 1
    local obj = getObjectFromGUID(guid)
    if (obj ~= nil and enabled == false) then obj.highlightOff() end
    if (obj ~= nil and enabled == true) then obj.highlightOn({1,1,1}) end
  end

  return count
end

local function readRotation()
  local r1, r2, r3 = self.getRotation():get()
  return round(r2)
end

local function changeButtons(variant)
  self.clearButtons()

  if(variant == 'before_setup') then
    self.createButton(BUTTON_SETUP_TOKENS)
  elseif (variant == 'in_setup') then
    self.createButton(BUTTON_CANCEL)
    self.createButton(BUTTON_SUBMIT)
    self.createButton(BUTTON_RESET)
  elseif (variant == 'done_setup') then
    self.createButton(BUTTON_PLACE)
    self.createButton(BUTTON_RECALL)
    self.createButton(BUTTON_PLACE_KT_TABLE)
  end
end

local function setupContextMenu()
  self.clearContextMenu()
  self.addContextMenuItem("Update", function(playerColor)
    click_update_rules()
  end)
  self.addContextMenuItem("Reset", function(playerColor)
    click_setup()
  end)
  self.addContextMenuItem("Clear Layout", function(playerColor)
    customLayout = {}
    drawnCardLayout = {}
    broadcastToAll("Custom layout cleared. Place will use default relative positions.", {1, 0.5, 0})
    updateSave()
  end)
end

function compare_coords(p1, p2, rotation)
  local deltaPos = {}
  r = math.rad(rotation)

  z = ((-p2.x * math.sin(r) + p2.z * math.cos(r)))
  x = ((p2.x * math.cos(r) + p2.z * math.sin(r)))

  deltaPos.x = (p1.x+x)
  deltaPos.y = (p1.y+p2.y)
  deltaPos.z = (p1.z+z)

  return deltaPos
end

--state utils
local function readList()
  return transmute(
    getObjectsWithTag(self.getGMNotes()),
    function(obj)
      local selfPos = self.getPosition()
      local objPos = obj.getPosition()
      local deltaPos = {}
      deltaPos.x = (objPos.x-selfPos.x)
      deltaPos.y = (objPos.y-selfPos.y)
      deltaPos.z = (objPos.z-selfPos.z)
      local pos, rot = deltaPos, obj.getRotation()

      return {
        pos={x=round(pos.x,4), y=round(pos.y,4), z=round(pos.z,4)},
        rot={x=round(rot.x,4), y=round(rot.y,4), z=round(rot.z,4)},
        lock=obj.getLock()
      }
    end,
    function(obj)
      return obj.guid
    end
  )
end

function updateSave()
  local data_to_save = {
    ["ml"]=memoryList,
    ["rr"]=relativeRotation,
    ["lastCardUpdate"]=lastCardUpdate,
    ["lastTokenUpdate"]=lastTokenUpdate,
    ["teamSlug"]=teamSlug,
    ["tokenBagPositions"]=tokenBagPositions,
    ["deckUnpackTracking"]=deckUnpackTracking,
    ["customLayout"]=customLayout,
    ["deckCardRegistry"]=deckCardRegistry,
    ["drawnCardLayout"]=drawnCardLayout
  }
  saved_data = JSON.encode(data_to_save)
  self.script_state = saved_data
end

function onload(saved_data)
  
  -- Save original box state for reset functionality
  if not originalBoxJSON then
    originalBoxJSON = self.getJSON()
  end
  
  if saved_data ~= "" then
    local loaded_data = JSON.decode(saved_data)
    memoryList = loaded_data.ml
    relativeRotation = loaded_data.rr
    -- lastCardUpdate stores when this box's JSON file was last generated
    lastCardUpdate = loaded_data.lastCardUpdate or loaded_data.lastUpdate or ""
    lastTokenUpdate = loaded_data.lastTokenUpdate or ""
    teamSlug = loaded_data.teamSlug or ""
    tokenBagPositions = loaded_data.tokenBagPositions or {}
    deckUnpackTracking = loaded_data.deckUnpackTracking or {}
    customLayout = {}
    deckCardRegistry = loaded_data.deckCardRegistry or {}
    drawnCardLayout = {}
  else
    memoryList = {}
    relativeRotation = readRotation()
    -- Force old timestamp to always trigger updates
    lastCardUpdate = "1900-01-01T00:00:00"
    lastTokenUpdate = ""
    teamSlug = ""
    tokenBagPositions = {}
    deckUnpackTracking = {}
    customLayout = {}
    deckCardRegistry = {}
    drawnCardLayout = {}
  end

  if next(memoryList) == nil then
    changeButtons('before_setup')
  else
    changeButtons('done_setup')
  end
  
  -- Setup context menu for update functions (right-click)
  setupContextMenu()
end

-- handlers for buttons
function click_setup()
  -- Reset: Only works after recall - clears bag contents and respawns fresh objects
  
  -- Check if we have a setup (memoryList exists)
  if next(memoryList) == nil then
    broadcastToAll("No setup found. Please use Update button to get latest version.", {1, 0.5, 0})
    return
  end
  
  if not originalBoxJSON then
    broadcastToAll("ERROR: No original box data available", {1, 0, 0})
    return
  end
  
  broadcastToAll("Resetting box to original state...", {1, 1, 0})
  
  -- Step 1: Delete any placed objects on table
  local deletedCount = 0
  for guid, entry in pairs(memoryList) do
    local obj = getObjectFromGUID(guid)
    if obj ~= nil and not obj.isDestroyed() then
      obj.destruct()
      deletedCount = deletedCount + 1
    end
  end
  
  -- Delete unpacked cards
  if next(deckUnpackTracking) ~= nil then
    for originalDeckGuid, trackingData in pairs(deckUnpackTracking) do
      for _, cardGuid in ipairs(trackingData.cardGuids) do
        local card = getObjectFromGUID(cardGuid)
        if card ~= nil and not card.isDestroyed() then
          card.destruct()
          deletedCount = deletedCount + 1
        end
      end
    end
  end
  
  if deletedCount > 0 then
    broadcastToAll("Deleted " .. deletedCount .. " placed objects", {0.7, 0.7, 0.7})
  end
  
  -- Step 2: Clear bag contents
  Wait.time(function()
    local bagContents = self.getObjects()
    for _, item in ipairs(bagContents) do
      local obj = self.takeObject({guid = item.guid})
      if obj then
        obj.destruct()
      end
    end
    
    broadcastToAll("Cleared bag contents", {0.7, 0.7, 0.7})
    
    -- Step 3: Parse original box and respawn fresh objects
    Wait.time(function()
      local success, parsed = pcall(function() return JSON.decode(originalBoxJSON) end)
      if not success or not parsed then
        broadcastToAll("ERROR: Could not parse original box JSON", {1, 0, 0})
        return
      end
      
      local boxData = parsed.ObjectStates and parsed.ObjectStates[1] or parsed
      local expectedObjects = boxData.ContainedObjects or {}
      
      if #expectedObjects == 0 then
        broadcastToAll("ERROR: No objects in original box", {1, 0, 0})
        return
      end
      
      broadcastToAll("Spawning " .. #expectedObjects .. " fresh objects...", {1, 1, 0})
      
      -- Spawn each object back into the bag
      for _, objData in ipairs(expectedObjects) do
        self.putObject(spawnObjectData({
          data = objData
        }))
      end
      
      -- Step 4: Rebuild memoryList from original box data
      Wait.time(function()
        -- Restore memoryList from original box's LuaScriptState
        if boxData.LuaScriptState and boxData.LuaScriptState ~= "" then
          local success, savedState = pcall(function() return JSON.decode(boxData.LuaScriptState) end)
          if success and savedState and savedState.ml then
            memoryList = {}
            local count = 0
            for k, v in pairs(savedState.ml) do
              memoryList[k] = {
                pos = {x=v.pos.x, y=v.pos.y, z=v.pos.z},
                rot = {x=v.rot.x, y=v.rot.y, z=v.rot.z},
                lock = v.lock
              }
              count = count + 1
            end
            relativeRotation = savedState.rr or readRotation()
            broadcastToAll("Restored " .. count .. " object positions", {0.7, 0.7, 0.7})
          else
            memoryList = {}
            relativeRotation = readRotation()
          end
        else
          memoryList = {}
          relativeRotation = readRotation()
        end
        
        placementMetadata = nil
        deckUnpackTracking = {}
        
        changeButtons('done_setup')
        updateSave()
        broadcastToAll("✓ Reset complete - ready to place!", {0, 1, 0})
      end, 1.0)
    end, 0.5)
  end, 0.5)
end

function click_cancel()
  setOutline(memoryList, false)

  memoryList = memoryListBackup
  relativeRotation = relativeRotationBackup

  if next(memoryList) == nil then
    changeButtons('before_setup')
  else
    changeButtons('done_setup')
  end

  broadcastToAll("Selection Canceled", {1,1,1})
end

function click_submit()
  memoryList = readList()
  if (next(memoryList) == nil) then
    broadcastToAll("You cannot submit without any selections.", {0.75, 0.25, 0.25})
  else
    changeButtons('done_setup')

    local count = setOutline(memoryList, false)
    broadcastToAll(count.." Objects Saved", {1,1,1})

    updateSave()
  end
end

function click_reset()
  setOutline(memoryList, false)
  memoryList = {}
  drawnCardLayout = {}

  relativeRotation = readRotation()

  changeButtons('before_setup')

  broadcastToAll("Tool Reset", {1,1,1})
  updateSave()
end

-- Helper function to check if we're on the workshop table
local function isWorkshopTable()
  -- Check for objects with the workshop-specific tag
  local workshopObjects = getObjectsWithTag(WORKSHOP_TABLE_TAG)
  
  if workshopObjects and #workshopObjects > 0 then
    return true
  else
    return false
  end
end

-- Helper function to determine card type from object tags or name
local function determineCardType(obj)
  if not obj then
    return nil
  end
  
  -- First try to get type from tags (most reliable)
  local tags = obj.getTags()
  for _, tag in ipairs(tags) do
    if tag == "KTCardsStrategyPloy" or tag == "KTCardsStrategicPloy" then
      return "strategy_ploys"
    elseif tag == "KTCardsFirefightPloy" or tag == "KTCardsTacticalPloy" then
      return "firefight_ploys"
    elseif tag == "KTCardsFactionRule" or tag == "KTCardsTacOp" then
      return "faction_rules"
    elseif tag == "KTCardsEquipment" or tag == "KTCardsEquipments" then
      return "equipment"
    elseif tag == "KTCardsDatacard" or tag == "KTCardsDatacards" then
      return "datacards"
    elseif tag == "KTCardsTokenGuide" then
      return "token_guide"
    elseif tag == "KTCardsTokenBag" then
      return "token_bag"
    elseif tag == "KTCardsOperativeSelection" then
      return "operative_selection"
    elseif tag == "KTDice_Dark" then
      return "dice_dark"
    elseif tag == "KTDice_Light" then
      return "dice_light"
    elseif tag == "KTDice_Team" then
      return "dice_team"
    end
  end

  -- Fallback: try to determine from object name
  local name = obj.getName()
  if not name or name == "" then
    return nil
  end

  local nameLower = string.lower(name)
  
  -- Check for specific card types based on name patterns
  if string.find(nameLower, "strategic ploy") or string.find(nameLower, "strategy ploy") then
    return "strategy_ploys"
  elseif string.find(nameLower, "tactical ploy") or string.find(nameLower, "firefight ploy") then
    return "firefight_ploys"
  elseif string.find(nameLower, "faction rule") or string.find(nameLower, "tac op") then
    return "faction_rules"
  elseif string.find(nameLower, "equipment") then
    return "equipment"
  elseif string.find(nameLower, "datacard") then
    return "datacards"
  elseif string.find(nameLower, "markertoken") and string.find(nameLower, "guide") then
    return "token_guide"
  elseif string.find(nameLower, "token") then
    return "token_bag"
  elseif string.find(nameLower, "operative selection") then
    return "operative_selection"
  end
  
  return nil
end

-- Helper function to get custom position for workshop table
local function getWorkshopPosition(playerColor, cardType, index)
  local positions = WORKSHOP_POSITIONS[playerColor]
  if not positions then
    return nil
  end
  
  local areaPositions = positions[cardType]
  if not areaPositions or #areaPositions == 0 then
    return nil
  end
  
  -- For faction_rules: first card in slot 1, second in slot 2, rest in slot 3
  if cardType == "faction_rules" then
    if index == 1 then
      return areaPositions[1]
    elseif index == 2 then
      return areaPositions[2]
    else
      return areaPositions[3]
    end
  end
  
  -- For other types, use modulo to wrap around if we have more cards than positions
  local posIndex = ((index - 1) % #areaPositions) + 1
  return areaPositions[posIndex]
end

-- Save current absolute positions of all placed items for use by Place
function click_save_layout()
  broadcastToAll("Layout save is disabled in this release. Place will use default positions.", {1, 0.5, 0})
  return
end

function click_place(obj, player_color, alt_click)
  local bagObjList = self.getObjects()
  local currentRotation = readRotation()
  local selfPos = self.getPosition()
  
  -- If memory list is empty, cannot place (need to Setup first)
  if next(memoryList) == nil then
    broadcastToAll("Memory list empty - please click Setup first", {1, 0.5, 0})
    return
  end
  
  -- Check if we're switching from KT table mode to regular mode
  if placementMetadata and placementMetadata.mode == "kt_table" then
    broadcastToAll("Cannot switch from KT table to regular - please Recall first", {1, 0.5, 0})
    return
  end
  
  -- Always use relative positioning (old behavior)
  local newMemoryList = {}
  
  -- Count total objects to place
  local totalObjects = 0
  for _ in pairs(memoryList) do
    totalObjects = totalObjects + 1
  end
  local processedObjects = 0
  
  for guid, entry in pairs(memoryList) do
    local obj = getObjectFromGUID(guid)
    local rot = { x=entry.rot.x, y=entry.rot.y, z=entry.rot.z }
    local rotationAdjustment = currentRotation - relativeRotation

    rot.y = rot.y + rotationAdjustment
    if (rot.y > 360) then
      rot.y = rot.y - 360
    elseif (rot.y < 0) then
      rot.y = rot.y + 360
    end
    
    -- If object is in bag, take it out first
    if obj == nil then
      for _, bagObj in ipairs(bagObjList) do
        if bagObj.guid == guid then
          obj = self.takeObject({
            guid=guid,
            position=selfPos + Vector(0, 5, 0),
            rotation=rot,
            smooth=false
          })
          break
        end
      end
    end
    
    -- Always process (wait for takeObject to complete if needed)
    Wait.frames(function()
      -- Re-get the object in case it was just taken from bag
      local placedObj = getObjectFromGUID(guid)
      if placedObj and not placedObj.isDestroyed() then
        if customLayout and customLayout[guid] then
          -- Use saved absolute position from Save Layout
          local savedPos = customLayout[guid]
          placedObj.setPosition(savedPos.pos)
          placedObj.setRotation(savedPos.rot)
          placedObj.setLock(savedPos.lock)
        else
          -- Use relative positioning
          local deltaPos = compare_coords(selfPos, entry.pos, rotationAdjustment)
          placedObj.setPosition(deltaPos)
          placedObj.setRotation(rot)
          placedObj.setLock(entry.lock)
        end
        newMemoryList[guid] = entry
        -- Register deck card GUIDs, memoryList entry, and custom position so Recall
        -- can regroup and restore the deck even if Save Layout cleared memoryList.
        if placedObj.type == "Deck" then
          local cardGuids = {}
          for _, card in ipairs(placedObj.getObjects()) do
            table.insert(cardGuids, card.guid)
          end
          deckCardRegistry[guid] = {
            cardGuids = cardGuids,
            memoryEntry = entry,
            customEntry = customLayout and customLayout[guid] or nil,
            cardType = determineCardType(placedObj)
          }
        end
      end
      
      -- Track completion
      processedObjects = processedObjects + 1
      if processedObjects >= totalObjects then
        -- All objects processed, update memoryList
        memoryList = {}
        for k,v in pairs(newMemoryList) do
          memoryList[k] = v
        end
        -- Track placement metadata
        placementMetadata = {
          mode = "regular",
          timestamp = os.time()
        }
        broadcastToAll("Objects Placed", {1,1,1})
        updateSave()
        -- Phase 2: extract any drawn cards from their parent decks
        if next(drawnCardLayout) ~= nil then
          Wait.time(function()
            for cardGuid, cardInfo in pairs(drawnCardLayout) do
              local cardObj = getObjectFromGUID(cardGuid)
              if cardObj ~= nil and not cardObj.isDestroyed() then
                -- Card already on table; just move it to its saved position
                cardObj.setPosition(cardInfo.pos)
                cardObj.setRotation(cardInfo.rot)
                cardObj.setLock(cardInfo.lock)
              else
                -- Card is inside its parent deck; extract it
                local deckObj = getObjectFromGUID(cardInfo.deckGuid)
                if deckObj and deckObj.type == "Deck" then
                  local capturedPos = cardInfo.pos
                  local capturedRot = cardInfo.rot
                  local capturedLock = cardInfo.lock
                  local capturedCardGuid = cardGuid
                  deckObj.takeObject({
                    guid = capturedCardGuid,
                    position = {x=deckObj.getPosition().x, y=deckObj.getPosition().y+3, z=deckObj.getPosition().z},
                    smooth = false,
                    callback_function = function(extracted)
                      Wait.frames(function()
                        if extracted and not extracted.isDestroyed() then
                          extracted.setPosition(capturedPos)
                          extracted.setRotation(capturedRot)
                          extracted.setLock(capturedLock)
                        end
                      end, 2)
                    end
                  })
                end
              end
            end
          end, 1.5)
        end
      end
    end, 2)
  end
end

function click_place_kt_table(obj, player_color, alt_click)
  local bagObjList = self.getObjects()
  local currentRotation = readRotation()
  
  -- Get the player color from the clicking player
  if not player_color or player_color == "" then
    player_color = Player.getPlayers()[1] and Player.getPlayers()[1].color or "White"
  end
  
  -- If memory list is empty, cannot place (need to Setup first)
  if next(memoryList) == nil then
    broadcastToAll("Memory list empty - please click Setup first", {1, 0.5, 0})
    return
  end
  
  -- Check if we're switching modes or colors - block these operations
  if placementMetadata then
    if placementMetadata.mode == "regular" then
      broadcastToAll("Cannot switch from regular placement to KT table - please Recall first", {1, 0, 0})
      return
    elseif placementMetadata.player_color and placementMetadata.player_color ~= player_color then
      broadcastToAll("Cannot switch from " .. placementMetadata.player_color .. " to " .. player_color .. " - please Recall first", {1, 0, 0})
      return
    end
  end
  
  -- Check if we're on the workshop table
  local useWorkshopPositions = isWorkshopTable()
  
  if not useWorkshopPositions then
    broadcastToAll("KT table not detected. Use 'Place' button for standard placement.", {1, 0.5, 0})
    return
  end
  
  if useWorkshopPositions then
    -- Only use workshop positions if we have them defined for this player color
    if WORKSHOP_POSITIONS[player_color] then
      broadcastToAll("Placement for " .. player_color .. " player on KT table", {0.2, 1, 0.2})
      
      -- Check for existing cards at workshop positions
      local hasCollision = false
      local collisionCount = 0
      
      for cardType, positions in pairs(WORKSHOP_POSITIONS[player_color]) do
        for _, pos in ipairs(positions) do
          -- Search for objects near this position (larger radius to catch decks/bags)
          local nearbyObjects = Physics.cast({
            origin = {pos.x, pos.y + 2, pos.z},
            direction = {0, -1, 0},
            type = 2, -- Sphere cast
            size = {2, 2, 2},
            max_distance = 3
          })
          
          for _, hit in ipairs(nearbyObjects) do
            local hitObj = hit.hit_object
            -- Check for Card, Deck, or Custom_Model_Bag
            if hitObj and (hitObj.type == "Card" or hitObj.type == "Deck" or hitObj.type == "Custom_Model_Bag") and hitObj ~= self then
              hasCollision = true
              collisionCount = collisionCount + 1
              break
            end
          end
          if hasCollision then break end
        end
        if hasCollision then break end
      end
      
      if hasCollision then
        broadcastToAll("Cannot place cards: Workshop positions occupied (" .. collisionCount .. " found). Please recall cards first.", {1, 0.2, 0.2})
        return
      end
    else
      -- No workshop positions defined for this color
      broadcastToAll("No KT table positions defined for " .. player_color .. " player.", {1, 0.5, 0})
      return
    end
  end

  -- Track card indices per type for proper placement
  local cardTypeIndices = {}
  
  -- Count total objects to place
  local totalObjects = 0
  for _ in pairs(memoryList) do
    totalObjects = totalObjects + 1
  end
  local processedObjects = 0
  
  for guid, entry in pairs(memoryList) do
    local obj = getObjectFromGUID(guid)
    local selfPos = self.getPosition()
    
    -- For workshop placement, we'll use absolute rotations (not relative to box)
    -- We'll still take objects out with temporary relative rotation, but fix it later
    local rot = { x=entry.rot.x, y=entry.rot.y, z=entry.rot.z }
    local rotationAdjustment = currentRotation - relativeRotation

    rot.y = rot.y + rotationAdjustment
    if (rot.y > 360) then
      rot.y = rot.y - 360
    elseif (rot.y < 0) then
      rot.y = rot.y + 360
    end
    
    -- If object is in bag, take it out first
    if obj == nil then
      for _, bagObj in ipairs(bagObjList) do
        if bagObj.guid == guid then
          obj = self.takeObject({
            guid=guid,
            position=selfPos + Vector(0, 5, 0),
            rotation=rot,
            smooth=false
          })
          break
        end
      end
    end
    
    -- Wait for object to exist
    if obj ~= nil then
      Wait.frames(function()
        -- Determine card type (use stored cardType from previous placement if available)
        local cardType = (entry and entry.cardType) or determineCardType(obj)
        
        -- Use workshop positions
        local shouldUseWorkshop = useWorkshopPositions and player_color and cardType and WORKSHOP_POSITIONS[player_color] ~= nil
        
        if shouldUseWorkshop then
          -- Initialize index for this card type if not exists
          if not cardTypeIndices[cardType] then
            cardTypeIndices[cardType] = 1
          end
          
          -- For workshop placement, use ABSOLUTE rotation (ignore box rotation)
          -- Blue faces north (Y=180), Red faces south (Y=0)
          local absoluteRotY = (player_color == "Red") and 0 or 180
          local absoluteRot = {x=0, y=absoluteRotY, z=0}
          
          -- Token bags need 90 degree rotation adjustment
          local tokenBagRotY = (player_color == "Red") and 90 or 270
          local tokenBagRot = {x=0, y=tokenBagRotY, z=0}
          
          -- Check if this is a deck
          if obj.type == "Deck" then
            -- For datacards and equipment, keep as deck. For faction_rules, unpack first 2 then keep rest as deck
            if cardType == "datacards" or cardType == "equipment" or cardType == "token_guide" then
              -- Place entire deck at position
              local customPos = getWorkshopPosition(player_color, cardType, cardTypeIndices[cardType])
              if customPos then
                obj.setPosition(customPos)
                obj.setRotation(absoluteRot)
                obj.setLock(entry.lock)
                local regEntry = {
                  pos = {x=customPos.x - selfPos.x, y=customPos.y - selfPos.y, z=customPos.z - selfPos.z},
                  rot = entry.rot,
                  lock = entry.lock,
                  cardType = cardType
                }
                cardTypeIndices[cardType] = cardTypeIndices[cardType] + 1
                -- Register for drawn-card detection in Recall
                local cardGuids = {}
                for _, card in ipairs(obj.getObjects()) do
                  table.insert(cardGuids, card.guid)
                end
                deckCardRegistry[obj.guid] = {
                  cardGuids = cardGuids,
                  memoryEntry = entry,
                  customEntry = nil
                }
              end
            elseif cardType == "faction_rules" then
              -- Unpack first 2 cards, keep rest as deck at position 3
              local originalDeckGuid = guid
              local deckSize = #obj.getObjects()
              local cardsToUnpack = math.min(2, deckSize)
              deckUnpackTracking[originalDeckGuid] = {
                name = obj.getName(),
                description = obj.getDescription(),
                cardGuids = {},
                originalEntry = entry,
                cardType = cardType
              }
              
              -- Unpack first 2 cards individually
              for i = 1, cardsToUnpack do
                local customPos = getWorkshopPosition(player_color, cardType, cardTypeIndices[cardType])
                if customPos then
                  local card = obj.takeObject({
                    position = customPos,
                    rotation = absoluteRot,
                    smooth = false
                  })
                  if card then
                    card.setLock(entry.lock)
                    table.insert(deckUnpackTracking[originalDeckGuid].cardGuids, card.guid)
                  end
                  cardTypeIndices[cardType] = cardTypeIndices[cardType] + 1
                end
              end
              
              -- If there are remaining cards, place them as deck at position 3
              if deckSize > 2 and obj and not obj.isDestroyed() then
                local customPos = getWorkshopPosition(player_color, cardType, 3)
                if customPos then
                  obj.setPosition(customPos)
                  obj.setRotation(absoluteRot)
                  obj.setLock(entry.lock)
                  table.insert(deckUnpackTracking[originalDeckGuid].cardGuids, obj.guid)
                end
              end
            else
              -- Unpack all cards for ploys and other types
              local originalDeckGuid = guid
              -- Save all card GUIDs before the loop so we can detect the
              -- deck-collapse case: when takeObject reduces a Deck to 1 card,
              -- TTS collapses it to a standalone Card synchronously.  The final
              -- loop iteration can no longer call takeObject on the destroyed deck
              -- reference, leaving that last card untracked at the deck's position.
              local allCardGuids = {}
              for _, cardInfo in ipairs(obj.getObjects()) do
                table.insert(allCardGuids, cardInfo.guid)
              end
              local deckSize = #allCardGuids
              deckUnpackTracking[originalDeckGuid] = {
                name = obj.getName(),
                description = obj.getDescription(),
                cardGuids = {},
                originalEntry = entry,
                cardType = cardType
              }

              for i = 1, deckSize do
                local customPos = getWorkshopPosition(player_color, cardType, cardTypeIndices[cardType])
                if customPos then
                  local card = obj.takeObject({
                    position = customPos,
                    rotation = absoluteRot,
                    smooth = false
                  })
                  if card then
                    card.setLock(entry.lock)
                    table.insert(deckUnpackTracking[originalDeckGuid].cardGuids, card.guid)
                  end
                  cardTypeIndices[cardType] = cardTypeIndices[cardType] + 1
                end
              end

              -- Collapsed-card recovery: if the deck collapsed to a standalone Card
              -- during the loop (last takeObject on a 2-card deck destroys the deck
              -- reference), that final card is never taken and sits untracked at the
              -- deck's original position.  Only run this if fewer cards were tracked
              -- than the deck had — this guards against GUID-mismatch false-positives.
              if #deckUnpackTracking[originalDeckGuid].cardGuids < #allCardGuids then
                local trackedSet = {}
                for _, cguid in ipairs(deckUnpackTracking[originalDeckGuid].cardGuids) do
                  trackedSet[cguid] = true
                end
                for _, cguid in ipairs(allCardGuids) do
                  if cguid ~= nil and not trackedSet[cguid] then
                    local remainingCard = getObjectFromGUID(cguid)
                    if remainingCard ~= nil and not remainingCard.isDestroyed() then
                      -- Just track it (no move) — Phase 2 recall will include it in group().
                      table.insert(deckUnpackTracking[originalDeckGuid].cardGuids, cguid)
                      trackedSet[cguid] = true
                    end
                  end
                end
              end
            end
          else
            -- Single card or other object
            local customPos = getWorkshopPosition(player_color, cardType, cardTypeIndices[cardType])
            if customPos then
              obj.setPosition(customPos)
              if cardType == "token_bag" then
                obj.setRotation(tokenBagRot)
              elseif cardType == "dice_dark" or cardType == "dice_light" or cardType == "dice_team" then
                obj.setRotation({x=270, y=0, z=0})
              else
                obj.setRotation(absoluteRot)
              end
              obj.setLock(entry.lock)
              cardTypeIndices[cardType] = cardTypeIndices[cardType] + 1
            else
              -- Fallback to relative positioning
              local deltaPos = compare_coords(selfPos, entry.pos, rotationAdjustment)
              obj.setPosition(deltaPos)
              obj.setRotation(rot)
              obj.setLock(entry.lock)
            end
          end
        else
          -- Fallback to relative positioning
          local deltaPos = compare_coords(selfPos, entry.pos, rotationAdjustment)
          if obj and not obj.isDestroyed() then
            obj.setPosition(deltaPos)
            obj.setRotation(rot)
            obj.setLock(entry.lock)
          end
        end
        
        -- Track completion
        processedObjects = processedObjects + 1
        if processedObjects >= totalObjects then
          -- Track placement metadata
          placementMetadata = {
            mode = "kt_table",
            player_color = player_color,
            timestamp = os.time()
          }
          broadcastToAll("Objects Placed on KT table", {1,1,1})
          updateSave()
        end
      end, 2)
    end
  end
end

-- Rebuild decks from individual cards after recall
function click_recall()
  local totalInList = 0
  for _ in pairs(memoryList) do totalInList = totalInList + 1 end

  if totalInList == 0 and next(drawnCardLayout) == nil then
    broadcastToAll("No objects to recall. Memory list is empty.", {1, 0.5, 0})
    return
  end

  broadcastToAll("Recalling objects...", {1, 1, 0})

  -- ── Auto-detect drawn cards if Recall is called without a prior Save Layout ─
  -- drawnCardLayout is normally populated by click_save_layout. If the user skips
  -- that step, we reconstruct it now from deckCardRegistry.
  if next(drawnCardLayout) == nil and next(deckCardRegistry) ~= nil then
    local bagContents = {}
    for _, item in ipairs(self.getObjects()) do bagContents[item.guid] = true end
    for deckGuid, registry in pairs(deckCardRegistry) do
      if not bagContents[deckGuid] then
        local deckObj = getObjectFromGUID(deckGuid)
        if deckObj ~= nil and deckObj.type == "Deck" and not deckObj.isDestroyed() then
          -- Partial draw: find cards that left the deck
          local inDeck = {}
          for _, c in ipairs(deckObj.getObjects()) do inDeck[c.guid] = true end
          for _, cardGuid in ipairs(registry.cardGuids) do
            if not inDeck[cardGuid] and not bagContents[cardGuid] then
              local cardObj = getObjectFromGUID(cardGuid)
              if cardObj ~= nil and not cardObj.isDestroyed() then
                local p, r = cardObj.getPosition(), cardObj.getRotation()
                drawnCardLayout[cardGuid] = {deckGuid=deckGuid, pos={x=p.x,y=p.y,z=p.z}, rot={x=r.x,y=r.y,z=r.z}, lock=cardObj.getLock()}
              end
            end
          end
        else
          -- Full draw: deck is gone, all registered cards on table are drawn
          for _, cardGuid in ipairs(registry.cardGuids) do
            if not bagContents[cardGuid] then
              local cardObj = getObjectFromGUID(cardGuid)
              if cardObj ~= nil and not cardObj.isDestroyed() then
                local p, r = cardObj.getPosition(), cardObj.getRotation()
                drawnCardLayout[cardGuid] = {deckGuid=deckGuid, pos={x=p.x,y=p.y,z=p.z}, rot={x=r.x,y=r.y,z=r.z}, lock=cardObj.getLock()}
              end
            end
          end
        end
      end
    end
  end

  -- ── Pre-compute: KT table tracked GUIDs (excluded from regular loop) ───────
  local trackedGuids = {}
  for _, trackingData in pairs(deckUnpackTracking) do
    for _, cguid in ipairs(trackingData.cardGuids) do
      trackedGuids[cguid] = true
    end
  end

  -- ── Phase 1: Re-merge drawn cards into their parent decks ─────────────────
  -- Group drawn cards by their parent deck GUID.
  -- Skip entries whose deckGuid is in deckUnpackTracking — those decks are fully
  -- unpacked by the KT button and will be rebuilt by Phase 2, not Phase 1.
  local drawnByDeck = {}
  for cardGuid, cardInfo in pairs(drawnCardLayout) do
    local cardObj = getObjectFromGUID(cardGuid)
    if cardObj ~= nil and not cardObj.isDestroyed() then
      local dGuid = cardInfo.deckGuid
      if not deckUnpackTracking[dGuid] then
        if not drawnByDeck[dGuid] then
          drawnByDeck[dGuid] = {cards = {}, deckEntry = memoryList[dGuid]}
        end
        table.insert(drawnByDeck[dGuid].cards, {guid=cardGuid, obj=cardObj})
      end
    end
  end

  -- These deck GUIDs are handled in Phase 1; skip them in the regular loop.
  local drawnDeckGuids = {}
  for deckGuid, _ in pairs(drawnByDeck) do drawnDeckGuids[deckGuid] = true end

  -- Helper: reset scale to default before stowing back in the box.
  -- KT table tiles can scale cards; this ensures the box always stores clean originals.
  -- Scale reset is skipped for non-card objects (e.g. token bags / 3D models).
  local function stow(obj)
    if obj ~= nil and not obj.isDestroyed() then
      if obj.type == "Card" or obj.type == "Deck" then
        obj.setScale({1, 1, 1})
      end
      self.putObject(obj)
    end
  end

  -- pendingOps counts async merge operations still in flight.
  -- doFinalRecall() runs only when all are done.
  local pendingOps = 0

  local function doFinalRecall()
    -- ── Phase 2: KT table deck reconstruction (deckUnpackTracking) ───────────
    -- Build a job list first, then process sequentially.
    -- Simultaneous group() calls for multiple decks (e.g. strategy + firefight ploys)
    -- can silently fail in TTS, leaving cards loose. Serialising them avoids this.
    local bagGuids = {}
    for _, item in ipairs(self.getObjects()) do bagGuids[item.guid] = true end

    local unpackJobs = {}
    for origGuid, trackingData in pairs(deckUnpackTracking) do
      local objects = {}
      local missingGuids = {}
      for _, cguid in ipairs(trackingData.cardGuids) do
        if bagGuids[cguid] then
          table.insert(missingGuids, "IN_BAG:"..cguid)
        else
          local obj = getObjectFromGUID(cguid)
          if obj ~= nil and not obj.isDestroyed() then
            table.insert(objects, obj)
          else
            table.insert(missingGuids, "NOT_FOUND:"..cguid)
          end
        end
      end
      local dbgMsg = "[DEBUG] KT recall "..tostring(trackingData.cardType).." tracked="..#trackingData.cardGuids.." found="..#objects
      if #missingGuids > 0 then dbgMsg = dbgMsg.." missing="..#missingGuids end
      print(dbgMsg)
      if #objects > 0 then
        table.insert(unpackJobs, {origGuid=origGuid, trackingData=trackingData, objects=objects})
      end
    end

    -- ── Phase 3 (deferred) — runs only after all unpack jobs finish ───────────
    local function doPhase3()
      for guid, _ in pairs(memoryList) do
        if not trackedGuids[guid] and not drawnDeckGuids[guid] then
          local obj = getObjectFromGUID(guid)
          stow(obj)
        end
      end
      placementMetadata = nil
      deckUnpackTracking = {}
      deckCardRegistry = {}
      customLayout = {}
      drawnCardLayout = {}
      changeButtons('done_setup')
      updateSave()
      broadcastToAll("✓ Objects recalled - ready to place again!", {0, 1, 0})
    end

    if #unpackJobs == 0 then
      doPhase3()
      return
    end

    local unpackIdx = 0
    local function processNextUnpackJob()
      unpackIdx = unpackIdx + 1
      if unpackIdx > #unpackJobs then
        doPhase3()
        return
      end

      local job = unpackJobs[unpackIdx]
      local origGuid = job.origGuid
      local trackingData = job.trackingData
      local objects = job.objects

      local baseDeck = nil
      local looseCards = {}
      for _, obj in ipairs(objects) do
        if obj.type == "Deck" then baseDeck = obj
        else table.insert(looseCards, obj) end
      end

      if baseDeck ~= nil then
        -- Partial unpack: one deck remains; merge loose cards back into it.
        for _, card in ipairs(looseCards) do baseDeck.putObject(card) end
        local capturedDeck = baseDeck
        local capturedEntry = trackingData.originalEntry
        local capturedCardType = trackingData.cardType
        local capturedGuids = trackingData.cardGuids
        local capturedObjects = objects
        Wait.time(function()
          if capturedDeck ~= nil and not capturedDeck.isDestroyed() then
            stow(capturedDeck)
            for _, cguid in ipairs(capturedGuids) do
              if cguid ~= capturedDeck.guid then memoryList[cguid] = nil end
            end
            if capturedEntry then
              local restoredEntry = capturedEntry
              if capturedCardType then
                restoredEntry = {pos=restoredEntry.pos, rot=restoredEntry.rot, lock=restoredEntry.lock, cardType=capturedCardType}
              end
              memoryList[capturedDeck.guid] = restoredEntry
            end
          else
            for _, obj in ipairs(capturedObjects) do stow(obj) end
          end
          processNextUnpackJob()
        end, 1.5)

      else
        -- Full unpack: all cards are loose; use group() to reassemble, then stow.
        local capturedOrigGuid = origGuid
        local capturedEntry = trackingData.originalEntry
        local capturedCardType = trackingData.cardType
        local capturedCardGuids = trackingData.cardGuids
        if #objects >= 2 then
          print("[DEBUG] group() called for "..tostring(trackingData.cardType).." with "..#objects.." objects")
          for _, obj in ipairs(objects) do obj.setLock(false) end
          local grouped = group(objects)
          Wait.frames(function() -- 10 frames for reliable group() completion
            local newDeck = (grouped and #grouped > 0) and grouped[1] or nil
            if newDeck ~= nil and not newDeck.isDestroyed() then
              print("[DEBUG] group() SUCCESS for "..tostring(trackingData.cardType).." newGuid="..newDeck.guid)
              local newGuid = newDeck.guid
              stow(newDeck)
              for _, cguid in ipairs(capturedCardGuids) do memoryList[cguid] = nil end
              local restoredEntry = capturedEntry or memoryList[capturedOrigGuid]
              if restoredEntry and capturedCardType then
                restoredEntry = {pos=restoredEntry.pos, rot=restoredEntry.rot, lock=restoredEntry.lock, cardType=capturedCardType}
              end
              memoryList[newGuid] = restoredEntry
              if newGuid ~= capturedOrigGuid then
                memoryList[capturedOrigGuid] = nil
                for _, cardInfo in pairs(drawnCardLayout) do
                  if cardInfo.deckGuid == capturedOrigGuid then cardInfo.deckGuid = newGuid end
                end
              end
            else
              -- group() failed: stow individual cards as fallback
              print("[DEBUG] group() FAILED for "..tostring(trackingData.cardType).." grouped="..tostring(grouped).." len="..(grouped and #grouped or 0))
              for _, obj in ipairs(objects) do stow(obj) end
            end
            processNextUnpackJob()
          end, 10)
        elseif #objects == 1 then
          print("[DEBUG] single-card path for "..tostring(trackingData.cardType).." guid="..objects[1].guid)
          local singleCard = objects[1]
          local singleGuid = singleCard.guid
          stow(singleCard)
          -- Fix memoryList: if single card guid differs from original deck guid, remap
          local restoredEntry = trackingData.originalEntry
          if restoredEntry and trackingData.cardType then
            restoredEntry = {pos=restoredEntry.pos, rot=restoredEntry.rot, lock=restoredEntry.lock, cardType=trackingData.cardType}
          end
          if singleGuid ~= origGuid then
            if restoredEntry then memoryList[singleGuid] = restoredEntry end
            memoryList[origGuid] = nil
          else
            if restoredEntry then memoryList[origGuid] = restoredEntry end
          end
          processNextUnpackJob()
        else
          processNextUnpackJob()
        end
      end
    end

    processNextUnpackJob()
  end

  local function onMergeDone()
    pendingOps = pendingOps - 1
    if pendingOps == 0 then doFinalRecall() end
  end

  -- ── Launch merge operations ───────────────────────────────────────────────
  -- Partial draws run in parallel (simple putObject + 1.5s wait each).
  -- Full draws are queued and processed one-at-a-time: simultaneous spawnObjectData
  -- calls for multiple large deck JSONs will freeze TTS.
  local fullDrawJobs = {}

  for deckGuid, group in pairs(drawnByDeck) do
    local deckObj = getObjectFromGUID(deckGuid)

    if deckObj ~= nil and deckObj.type == "Deck" and not deckObj.isDestroyed() then
      -- Partial draw: put cards back into existing deck, then stow.
      pendingOps = pendingOps + 1
      for _, cardInfo in ipairs(group.cards) do
        deckObj.putObject(cardInfo.obj)
      end
      local capturedDeck = deckObj
      Wait.time(function()
        if capturedDeck ~= nil and not capturedDeck.isDestroyed() then
          stow(capturedDeck)
        end
        onMergeDone()
      end, 1.5)

    else
      local registry = deckCardRegistry[deckGuid]
      if registry then
        -- Full draw with registry: add to sequential queue.
        table.insert(fullDrawJobs, {deckGuid=deckGuid, group=group, registry=registry})
      else
        -- No JSON fallback: stow individual cards synchronously (no pending op).
        for _, cardInfo in ipairs(group.cards) do
          stow(cardInfo.obj)
        end
        memoryList[deckGuid] = nil
      end
    end
  end

  -- Process full-draw queue sequentially using TTS group().
  -- group() reassembles existing Card objects into a Deck — no spawn/destroy needed.
  -- Cards are processed one deck at a time to keep TTS load manageable.
  if #fullDrawJobs > 0 then
    pendingOps = pendingOps + 1
    local jobIdx = 0
    local function processNextFullDraw()
      jobIdx = jobIdx + 1
      if jobIdx > #fullDrawJobs then
        onMergeDone()  -- entire batch done
        return
      end
      local job = fullDrawJobs[jobIdx]
      local capturedOldGuid = job.deckGuid
      local capturedEntry = job.registry.memoryEntry or job.group.deckEntry
      local capturedCustom = job.registry.customEntry or customLayout[capturedOldGuid]
      local capturedCardType = job.registry.cardType
      -- Include cardType in restored entry so KT place can identify the deck type
      local restoredEntry = capturedEntry
      if restoredEntry and capturedCardType then
        restoredEntry = {pos=restoredEntry.pos, rot=restoredEntry.rot, lock=restoredEntry.lock, cardType=capturedCardType}
      end

      -- Collect live Card objects for this deck
      local cardObjs = {}
      for _, cardInfo in ipairs(job.group.cards) do
        if not cardInfo.obj.isDestroyed() then
          table.insert(cardObjs, cardInfo.obj)
        end
      end

      if #cardObjs == 0 then
        -- Nothing to regroup; clean up memoryList and move on
        memoryList[capturedOldGuid] = nil
        processNextFullDraw()
        return
      end

      if #cardObjs == 1 then
        -- Single card: stow it directly (no deck needed)
        stow(cardObjs[1])
        if restoredEntry then memoryList[capturedOldGuid] = restoredEntry end
        processNextFullDraw()
        return
      end

      -- Multiple cards: use group() to reassemble into a Deck.
      -- group() works on the existing Card objects — no spawn, no destroy.
      local grouped = group(cardObjs)
      Wait.frames(function()
        local newDeck = (grouped and #grouped > 0) and grouped[1] or nil
        if newDeck ~= nil and not newDeck.isDestroyed() then
          local newGuid = newDeck.guid
          stow(newDeck)
          -- group() always produces a new GUID; remap references
          if newGuid ~= capturedOldGuid then
            memoryList[newGuid] = restoredEntry
            memoryList[capturedOldGuid] = nil
            if capturedCustom then
              customLayout[newGuid] = capturedCustom
              customLayout[capturedOldGuid] = nil
            end
            if deckCardRegistry[capturedOldGuid] then
              deckCardRegistry[newGuid] = deckCardRegistry[capturedOldGuid]
              deckCardRegistry[capturedOldGuid] = nil
            end
            -- Remap drawnCardLayout entries so Place Phase 2 can re-extract cards
            for _, cardInfo in pairs(drawnCardLayout) do
              if cardInfo.deckGuid == capturedOldGuid then
                cardInfo.deckGuid = newGuid
              end
            end
          else
            if restoredEntry then memoryList[newGuid] = restoredEntry end
            if capturedCustom then customLayout[newGuid] = capturedCustom end
          end
        else
          -- group() failed: fall back to stowing individual cards
          for _, cardObj in ipairs(cardObjs) do
            stow(cardObj)
          end
          memoryList[capturedOldGuid] = nil
        end
        processNextFullDraw()
      end, 3)
    end
    processNextFullDraw()  -- kick off the queue
  end

  -- If nothing needed merging, go straight to final recall.
  if pendingOps == 0 then doFinalRecall() end
end

function click_update_rules()
  -- Check if we need to update by comparing timestamps
  if teamSlug == "" then
    broadcastToAll("Cannot update: team slug not configured", {1, 0.5, 0})
    return
  end
  
  broadcastToAll("Checking for updates...", {1, 1, 0})
  
  -- Build team-urls.json URL from this box's mesh URL so branch/path stay in sync.
  local data = self.getData() or {}
  local meshUrl = ((data.CustomMesh or {}).MeshURL) or ""
  if meshUrl == "" then
    broadcastToAll("Cannot check updates: missing box mesh URL", {1, 0.5, 0})
    return
  end
  local cleanMeshUrl = string.match(meshUrl, "^[^?]+") or meshUrl
  local baseUrl = string.match(cleanMeshUrl, "^(.-)/output/")
  if not baseUrl or baseUrl == "" then
    broadcastToAll("Cannot check updates: could not parse repository URL", {1, 0.5, 0})
    return
  end
  local metadataUrl = baseUrl .. "/output/team-urls.json?v=" .. tostring(os.time())
  WebRequest.get(metadataUrl, function(request)
    if request.is_error then
      broadcastToAll("Could not check for updates: " .. request.error, {1, 0.5, 0})
      return
    end
    
    -- Parse JSON to find this team's latest modified timestamp and box URL
    local success, metadata = pcall(function() return JSON.decode(request.text) end)
    if not success or not metadata then
      broadcastToAll("Could not parse update info.", {1, 0.5, 0})
      return
    end

    -- Find our team in keyed metadata map (or legacy list fallback)
    local remoteTimestamp = ""
    local cardsUrl = ""

    local teamEntry = metadata[teamSlug]
    if not teamEntry then
      for _, entry in ipairs(metadata) do
        if entry and entry.team == teamSlug then
          teamEntry = entry
          break
        end
      end
    end

    if teamEntry then
      -- New lightweight summary mode
      remoteTimestamp = teamEntry.modified or ""

      -- Backward compatibility with older global shape
      if remoteTimestamp == "" and teamEntry.box then
        remoteTimestamp = teamEntry.box.modified or ""
      end
      if teamEntry.box then
        cardsUrl = teamEntry.box.url or ""
      end
    end
    
    if remoteTimestamp == "" then
      broadcastToAll("Could not find team in update list.", {1, 0.5, 0})
      return
    end
    
    -- Compare timestamps (treat remote <= local as up to date).
    -- Normalize to the first 14 digits (YYYYMMDDHHMMSS) so values with extra
    -- microsecond/timezone digits (e.g. remote isoformat) don't compare as
    -- artificially larger than a plain local timestamp.
    local function toTimestampNumber(ts)
      local num = tostring(ts or ""):gsub("[^%d]", "")
      num = string.sub(num, 1, 14)
      return tonumber(num) or 0
    end
    local localStamp = toTimestampNumber(lastCardUpdate)
    local remoteStamp = toTimestampNumber(remoteTimestamp)
    
    if lastCardUpdate ~= "" and remoteStamp ~= 0 and localStamp >= remoteStamp then
      broadcastToAll("Already up to date! (Last: " .. lastCardUpdate .. ")", {0, 1, 0})
      return
    end
    
    local function download_and_spawn(updatedCardsUrl, effectiveRemoteTimestamp)
      if not updatedCardsUrl or updatedCardsUrl == "" then
        broadcastToAll("Could not find team box URL in update metadata.", {1, 0.5, 0})
        return
      end

      broadcastToAll("Update available! Downloading new version...", {0, 0.7, 1})
      broadcastToAll("Local: " .. (lastCardUpdate ~= "" and lastCardUpdate or "unknown") .. " | Remote: " .. effectiveRemoteTimestamp, {0.7, 0.7, 0.7})

      local cacheBust = tostring(effectiveRemoteTimestamp or ""):gsub("[^%d]", "")
      local separator = string.find(updatedCardsUrl, "?", 1, true) and "&" or "?"
      local url = updatedCardsUrl .. separator .. "v=" .. cacheBust

      WebRequest.get(url, function(webReturn)
      if webReturn.is_error then
        broadcastToAll("Failed to download update: " .. webReturn.error, {1, 0.5, 0})
        return
      end

      -- The downloaded box file may be EITHER:
      --   (a) a bare object (new format): { "GUID": ..., "Name": ..., ... }
      --   (b) a full save-file wrapper (legacy/published boxes still in use):
      --       { "SaveName": ..., ..., "ObjectStates": [ {box} ] }
      -- We support both so users with old published boxes can still self-update.
      --
      -- CRITICAL: we must NOT run Lua patterns on the ~400KB-1MB payload.
      -- MoonSharp throws "pattern too complex" even on simple anchored patterns
      -- at that size. All scanning below uses byte ops and plain string.find
      -- (4th arg = true), both of which are O(n) native C# in TTS.
      local saveText = webReturn.text
      local saveLen = #saveText
      local function isSpace(b) return b == 32 or b == 9 or b == 10 or b == 13 end

      -- Skip leading whitespace
      local startIdx = 1
      while startIdx <= saveLen and isSpace(saveText:byte(startIdx)) do
        startIdx = startIdx + 1
      end

      if startIdx > saveLen or saveText:byte(startIdx) ~= 123 then -- 123 = '{'
        broadcastToAll("Invalid update data received.", {1, 0.5, 0})
        return
      end

      -- Read the first JSON key (between the first pair of quotes after '{')
      local keyOpenIdx = startIdx + 1
      while keyOpenIdx <= saveLen and isSpace(saveText:byte(keyOpenIdx)) do
        keyOpenIdx = keyOpenIdx + 1
      end
      local firstKey = ""
      if keyOpenIdx <= saveLen and saveText:byte(keyOpenIdx) == 34 then -- 34 = '"'
        local keyCloseIdx = saveText:find('"', keyOpenIdx + 1, true)
        if keyCloseIdx then
          firstKey = saveText:sub(keyOpenIdx + 1, keyCloseIdx - 1)
        end
      end

      local objJson
      if firstKey == "SaveName" or firstKey == "ObjectStates" then
        -- (b) Save-file wrapper. Slice the inner box object with plain ops.
        -- The first occurrence of "ObjectStates" is the real top-level key (it
        -- precedes the object body whose LuaScript may contain escaped
        -- \"ObjectStates\" text), so a first-match slice is safe.
        local osIdx = saveText:find('"ObjectStates"', 1, true)
        local colonIdx = osIdx and saveText:find(':', osIdx + 14, true)
        local bracketIdx = colonIdx and saveText:find('[', colonIdx + 1, true)
        local boxStart = bracketIdx and saveText:find('{', bracketIdx + 1, true)

        -- Walk back from end of file to find the box's closing '}'.
        -- Tail structure: ... } ] }  (with possible whitespace between).
        local endIdx = saveLen
        while endIdx > 0 and isSpace(saveText:byte(endIdx)) do endIdx = endIdx - 1 end
        if endIdx == 0 or saveText:byte(endIdx) ~= 125 then -- '}' wrapper close
          broadcastToAll("Invalid update data received.", {1, 0.5, 0})
          return
        end
        endIdx = endIdx - 1
        while endIdx > 0 and isSpace(saveText:byte(endIdx)) do endIdx = endIdx - 1 end
        if endIdx == 0 or saveText:byte(endIdx) ~= 93 then -- ']' array close
          broadcastToAll("Invalid update data received.", {1, 0.5, 0})
          return
        end
        endIdx = endIdx - 1
        while endIdx > 0 and isSpace(saveText:byte(endIdx)) do endIdx = endIdx - 1 end
        if endIdx == 0 or saveText:byte(endIdx) ~= 125 then -- '}' box close
          broadcastToAll("Invalid update data received.", {1, 0.5, 0})
          return
        end

        if not boxStart or boxStart > endIdx then
          broadcastToAll("Invalid update data received.", {1, 0.5, 0})
          return
        end
        objJson = saveText:sub(boxStart, endIdx)
      else
        -- (a) Bare object: hand the raw text (minus any leading whitespace)
        -- straight to spawnObjectJSON, which parses natively in C#.
        objJson = (startIdx == 1) and saveText or saveText:sub(startIdx)
      end

      if objJson == "" or objJson:sub(1, 1) ~= "{" then
        broadcastToAll("Invalid update data received.", {1, 0.5, 0})
        return
      end

      -- Store current position, rotation, and lock state
      local currentPos = self.getPosition()
      local currentRot = self.getRotation()
      local currentLock = self.getLock()

      -- Spawn next to the current box to avoid overlap. The new box is identical
      -- to the repo JSON; we don't mutate it (the generated LuaScriptState
      -- already carries lastCardUpdate, so no injection is needed).
      local spawnPos = currentPos + Vector(5, 0, 0)

      broadcastToAll("Spawning updated card box...", {1, 1, 0})

      local spawnedObj = spawnObjectJSON({
        json = objJson,
        position = spawnPos,
        rotation = currentRot
      })

      if spawnedObj == nil then
        broadcastToAll("Update failed: could not spawn new box.", {1, 0.5, 0})
        return
      end

      Wait.condition(
        function()
          -- Wait a moment for script state to initialize
          Wait.time(function()
            if spawnedObj == nil or spawnedObj.isDestroyed() then
              broadcastToAll("Update failed during spawn.", {1, 0.5, 0})
              return
            end

            spawnedObj.setLock(currentLock)

            -- Destroy old box after new one is ready
            self.destruct()

            -- Move new box to original position
            Wait.time(function()
              spawnedObj.setPositionSmooth(currentPos, false, true)
              spawnedObj.setRotationSmooth(currentRot, false, true)
              broadcastToAll("Card box updated successfully!", {0, 1, 0})
            end, 0.5)
          end, 0.5)
        end,
        function() return spawnedObj ~= nil and not spawnedObj.spawning end,
        10
      )
      end)
    end

    download_and_spawn(cardsUrl, remoteTimestamp)
  end)
end
