-- constants
local TTS_METADATA_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/tts-metadata.json"

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
    }
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
    }
  }
}

local BUTTON_SETUP_TOKENS = {
  label="Setup",
  click_function="click_setup", function_owner=self,
  position={0,0.3,-2}, rotation={0,180,0},
  height=350, width=800,
  font_size=250, color={0,0,0}, font_color={1,1,1}
}
local BUTTON_SETUP_BOX = {
  label="Setup",
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
local BUTTON_UPDATE_TOKENS = {
  label="Update Tokens",
  click_function="click_update_tokens",
  function_owner=self,
  position={2,-2.5,1}, rotation={0,270,0},
  height=350, width=800,
  font_size=250, color={0.6,0.3,1}, font_color={1,1,1}
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

local function duplicateTable(oldTable)
  local newTable = {}
  for k, v in pairs(oldTable) do
    newTable[k] = v
  end
  return newTable
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
    self.createButton(BUTTON_SETUP_BOX)
    self.createButton(BUTTON_PLACE_KT_TABLE)
    self.createButton(BUTTON_UPDATE)
  end
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
    ["tokenBagPositions"]=tokenBagPositions
  }
  saved_data = JSON.encode(data_to_save)
  self.script_state = saved_data
end

function onload(saved_data)
  
  if saved_data ~= "" then
    local loaded_data = JSON.decode(saved_data)
    memoryList = loaded_data.ml
    relativeRotation = loaded_data.rr
    -- lastCardUpdate stores when this box's JSON file was last generated
    lastCardUpdate = loaded_data.lastCardUpdate or loaded_data.lastUpdate or ""
    lastTokenUpdate = loaded_data.lastTokenUpdate or ""
    teamSlug = loaded_data.teamSlug or ""
    tokenBagPositions = loaded_data.tokenBagPositions or {}
  else
    memoryList = {}
    relativeRotation = readRotation()
    -- Force old timestamp to always trigger updates
    lastCardUpdate = "1900-01-01T00:00:00"
    lastTokenUpdate = ""
    teamSlug = ""
    tokenBagPositions = {}
  end

  if next(memoryList) == nil then
    changeButtons('before_setup')
  else
    changeButtons('done_setup')
  end
end

-- handlers for buttons
function click_setup()
  local tagTarget = self.getGMNotes()

  if (tagTarget == nil or tagTarget == '') then
    broadcastToAll('please specify a tag to target in GM notes')
    return
  end

  memoryListBackup = duplicateTable(memoryList)
  memoryList = readList()

  if (next(memoryList) == nil) then
    broadcastToAll('The tag you specified yielded in 0 objects')
    return
  end

  setOutline(memoryList, true)

  relativeRotationBackup = relativeRotation
  relativeRotation = readRotation()

  changeButtons('in_setup')
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

function click_place(obj, player_color, alt_click)
  local bagObjList = self.getObjects()
  local currentRotation = readRotation()
  local selfPos = self.getPosition()
  
  -- Check if we're switching from KT table mode to regular mode
  if placementMetadata and placementMetadata.mode == "kt_table" then
    broadcastToAll("Switching from KT table to regular placement - clearing old memory", {1, 0.7, 0})
    memoryList = {}
    -- Rebuild memory list from bag contents for fresh placement
    for _, bagEntry in ipairs(bagObjList) do
      if not memoryList[bagEntry.guid] then
        memoryList[bagEntry.guid] = {
          pos = {x=bagEntry.position.x, y=bagEntry.position.y, z=bagEntry.position.z},
          rot = {x=bagEntry.rotation.x, y=bagEntry.rotation.y, z=bagEntry.rotation.z},
          lock = bagEntry.lock or false
        }
      end
    end
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
        -- Use relative positioning
        local deltaPos = compare_coords(selfPos, entry.pos, rotationAdjustment)
        placedObj.setPosition(deltaPos)
        placedObj.setRotation(rot)
        placedObj.setLock(entry.lock)
        newMemoryList[guid] = entry
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
  
  -- Check if we're switching modes or colors - warn and clear if needed
  if placementMetadata then
    if placementMetadata.mode == "regular" then
      broadcastToAll("Switching from regular to KT table placement - clearing old memory", {1, 0.7, 0})
      memoryList = {}
      -- Rebuild memory list from bag contents
      for _, bagEntry in ipairs(bagObjList) do
        if not memoryList[bagEntry.guid] then
          memoryList[bagEntry.guid] = {
            pos = {x=bagEntry.position.x, y=bagEntry.position.y, z=bagEntry.position.z},
            rot = {x=bagEntry.rotation.x, y=bagEntry.rotation.y, z=bagEntry.rotation.z},
            lock = bagEntry.lock or false
          }
        end
      end
    elseif placementMetadata.player_color and placementMetadata.player_color ~= player_color then
      broadcastToAll("Switching from " .. placementMetadata.player_color .. " to " .. player_color .. " - clearing old memory", {1, 0.7, 0})
      memoryList = {}
      -- Rebuild memory list from bag contents
      for _, bagEntry in ipairs(bagObjList) do
        if not memoryList[bagEntry.guid] then
          memoryList[bagEntry.guid] = {
            pos = {x=bagEntry.position.x, y=bagEntry.position.y, z=bagEntry.position.z},
            rot = {x=bagEntry.rotation.x, y=bagEntry.rotation.y, z=bagEntry.rotation.z},
            lock = bagEntry.lock or false
          }
        end
      end
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

  local newMemoryList = {}
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
        -- Determine card type
        local cardType = determineCardType(obj)
        
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
                newMemoryList[obj.guid] = {
                  pos = {x=customPos.x - selfPos.x, y=customPos.y - selfPos.y, z=customPos.z - selfPos.z},
                  rot = entry.rot,
                  lock = entry.lock
                }
                cardTypeIndices[cardType] = cardTypeIndices[cardType] + 1
              end
            elseif cardType == "faction_rules" then
              -- Unpack first 2 cards, keep rest as deck at position 3
              local deckSize = #obj.getObjects()
              local cardsToUnpack = math.min(2, deckSize)
              
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
                    newMemoryList[card.guid] = {
                      pos = {x=customPos.x - selfPos.x, y=customPos.y - selfPos.y, z=customPos.z - selfPos.z},
                      rot = entry.rot,
                      lock = entry.lock
                    }
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
                  newMemoryList[obj.guid] = {
                    pos = {x=customPos.x - selfPos.x, y=customPos.y - selfPos.y, z=customPos.z - selfPos.z},
                    rot = entry.rot,
                    lock = entry.lock
                  }
                end
              end
            else
              -- Unpack all cards for ploys and other types
              local deckSize = #obj.getObjects()
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
                    newMemoryList[card.guid] = {
                      pos = {x=customPos.x - selfPos.x, y=customPos.y - selfPos.y, z=customPos.z - selfPos.z},
                      rot = entry.rot,
                      lock = entry.lock
                    }
                  end
                  cardTypeIndices[cardType] = cardTypeIndices[cardType] + 1
                end
              end
            end
          else
            -- Single card or other object
            local customPos = getWorkshopPosition(player_color, cardType, cardTypeIndices[cardType])
            if customPos then
              obj.setPosition(customPos)
              -- Token bags need 90 degree rotation adjustment
              if cardType == "token_bag" then
                obj.setRotation(tokenBagRot)
              else
                -- Use absolute rotation (Blue=180°, Red=0°)
                obj.setRotation(absoluteRot)
              end
              obj.setLock(entry.lock)
              newMemoryList[obj.guid] = memoryList[guid]
              cardTypeIndices[cardType] = cardTypeIndices[cardType] + 1
            else
              -- Fallback to relative positioning
              local deltaPos = compare_coords(selfPos, entry.pos, rotationAdjustment)
              obj.setPosition(deltaPos)
              obj.setRotation(rot)
              obj.setLock(entry.lock)
              newMemoryList[obj.guid] = memoryList[guid]
            end
          end
        else
          -- Fallback to relative positioning
          local deltaPos = compare_coords(selfPos, entry.pos, rotationAdjustment)
          if obj and not obj.isDestroyed() then
            obj.setPosition(deltaPos)
            obj.setRotation(rot)
            obj.setLock(entry.lock)
            newMemoryList[obj.guid] = memoryList[guid]
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

function click_recall()
  local recalledCount = 0
  local totalInList = 0
  
  -- Count total entries in memoryList
  for _ in pairs(memoryList) do
    totalInList = totalInList + 1
  end
  
  if totalInList == 0 then
    broadcastToAll("No objects to recall. Memory list is empty.", {1, 0.5, 0})
    return
  end
  
  broadcastToAll("Attempting to recall " .. totalInList .. " objects...", {1, 1, 0})
  
  -- Collect all objects to recall first (to handle deck reconstruction)
  local objectsToRecall = {}
  for guid, entry in pairs(memoryList) do
    local obj = getObjectFromGUID(guid)
    if obj ~= nil then
      table.insert(objectsToRecall, obj)
    else
      -- Object doesn't exist anymore (could be unpacked cards)
      broadcastToAll("Skipping missing object: " .. guid, {1, 0.7, 0})
    end
  end
  
  -- Recall all objects
  for _, obj in ipairs(objectsToRecall) do
    self.putObject(obj)
    recalledCount = recalledCount + 1
  end
  
  -- IMPORTANT: Clear memory list completely after recall
  -- This prevents stale references when switching placement modes or player colors
  memoryList = {}
  placementMetadata = nil
  
  broadcastToAll("Objects Recalled (" .. recalledCount .. " of " .. totalInList .. " items)", {1,1,1})
  broadcastToAll("Memory cleared - ready for fresh placement", {0.7, 0.7, 1})
  
  updateSave()
end

function click_update_rules()
  -- Check if we need to update by comparing timestamps
  if teamSlug == "" then
    broadcastToAll("Cannot update: team slug not configured", {1, 0.5, 0})
    return
  end
  
  broadcastToAll("Checking for updates...", {1, 1, 0})
  
  -- Fetch tts-metadata.json to check if update is needed (cache-busted)
  local metadataUrl = TTS_METADATA_URL .. "?v=" .. tostring(os.time())
  WebRequest.get(metadataUrl, function(request)
    if request.is_error then
      broadcastToAll("Could not check for updates: " .. request.error, {1, 0.5, 0})
      return
    end
    
    -- Parse JSON to find this team's last_modified timestamp and URL
    local success, ttsBoxes = pcall(function() return JSON.decode(request.text) end)
    if not success or not ttsBoxes then
      broadcastToAll("Could not parse update info.", {1, 0.5, 0})
      return
    end
    
    -- Find our team in the list
    local remoteTimestamp = ""
    local cardsUrl = ""
    for _, box in ipairs(ttsBoxes) do
      if box.team == teamSlug then
        remoteTimestamp = box.cards_last_modified or ""
        cardsUrl = box.cards_url or ""
        break
      end
    end
    
    if remoteTimestamp == "" or cardsUrl == "" then
      broadcastToAll("Could not find team in update list.", {1, 0.5, 0})
      return
    end
    
    -- Compare timestamps (treat remote <= local as up to date)
    local function toTimestampNumber(ts)
      local num = tostring(ts or ""):gsub("[^%d]", "")
      return tonumber(num) or 0
    end
    local localStamp = toTimestampNumber(lastCardUpdate)
    local remoteStamp = toTimestampNumber(remoteTimestamp)
    
    if lastCardUpdate ~= "" and remoteStamp ~= 0 and localStamp >= remoteStamp then
      broadcastToAll("Already up to date! (Last: " .. lastCardUpdate .. ")", {0, 1, 0})
      return
    end
    
    -- Update needed
    broadcastToAll("Update available! Downloading new version...", {0, 0.7, 1})
    broadcastToAll("Local: " .. (lastCardUpdate ~= "" and lastCardUpdate or "unknown") .. " | Remote: " .. remoteTimestamp, {0.7, 0.7, 0.7})
    
    -- Download and spawn new version
    local cacheBust = remoteTimestamp:gsub("[^%d]", "")
    local url = cardsUrl .. "?v=" .. cacheBust
    
    WebRequest.get(url, function(webReturn)
      if webReturn.is_error then
        broadcastToAll("Failed to download update: " .. webReturn.error, {1, 0.5, 0})
        return
      end
      
      local success, decoded = pcall(function() return JSON.decode(webReturn.text) end)
      if not success or not decoded.ObjectStates or #decoded.ObjectStates == 0 then
        broadcastToAll("Invalid update data received.", {1, 0.5, 0})
        return
      end
      
      local newBoxData = decoded.ObjectStates[1]
      
      -- Ensure the new box state matches the remote timestamp to avoid repeated updates
      if newBoxData.LuaScriptState ~= nil and newBoxData.LuaScriptState ~= "" then
        local ok, state = pcall(function() return JSON.decode(newBoxData.LuaScriptState) end)
        if ok and state then
          state.lastCardUpdate = remoteTimestamp
          if not state.teamSlug or state.teamSlug == "" then
            state.teamSlug = teamSlug
          end
          newBoxData.LuaScriptState = JSON.encode(state)
        end
      else
        newBoxData.LuaScriptState = JSON.encode({
          lastCardUpdate = remoteTimestamp,
          teamSlug = teamSlug
        })
      end
      
      -- Store current position, rotation, and lock state
      local currentPos = self.getPosition()
      local currentRot = self.getRotation()
      local currentLock = self.getLock()
      
      broadcastToAll("Spawning updated card box...", {1, 1, 0})
      
      -- Apply position and rotation to new box data
      newBoxData.Transform.posX = currentPos.x
      newBoxData.Transform.posY = currentPos.y
      newBoxData.Transform.posZ = currentPos.z
      newBoxData.Transform.rotX = currentRot.x
      newBoxData.Transform.rotY = currentRot.y
      newBoxData.Transform.rotZ = currentRot.z
      
      -- Spawn new box next to the current one to avoid overlap
      local spawnOffset = Vector(5, 0, 0)
      local spawnPos = currentPos + spawnOffset
      newBoxData.Transform.posX = spawnPos.x
      newBoxData.Transform.posY = spawnPos.y
      newBoxData.Transform.posZ = spawnPos.z
      
      local spawnedObj = spawnObjectJSON({
        json = JSON.encode(newBoxData),
        position = spawnPos
      })
      
      Wait.condition(
        function()
          -- Wait a moment for script state to initialize
          Wait.time(function()
            spawnedObj.setLock(currentLock)
            
            -- Destroy old box after new one is ready
            self.destruct()
            
            -- Move new box to original position
            Wait.time(function()
              spawnedObj.setPositionSmooth(currentPos, false, true)
              spawnedObj.setRotationSmooth(currentRot, false, true)
              broadcastToAll("✓ Card box updated successfully!", {0, 1, 0})
            end, 0.5)
          end, 0.5)
        end,
        function() return spawnedObj ~= nil and not spawnedObj.spawning end,
        10
      )
    end)
  end)
end

-- Token Bag Update Function
function click_update_tokens()
  if teamSlug == "" then
    broadcastToAll("Cannot update tokens: team not identified.", {1, 0.5, 0})
    return
  end
  
  -- Check if we need to update by comparing timestamps
  if lastTokenUpdate ~= "" then
    broadcastToAll("Checking for token updates...", {1, 1, 0})
    
    -- Fetch tts-metadata.json to check if update is needed
    WebRequest.get(TTS_METADATA_URL, function(request)
      if request.is_error then
        broadcastToAll("Could not check for token updates. Forcing refresh...", {1, 0.5, 0})
        performTokenUpdate()
        return
      end
      
      -- Parse JSON to find this team's last_modified timestamp
      local success, ttsTokenBags = pcall(function() return JSON.decode(request.text) end)
      if not success or not ttsTokenBags then
        broadcastToAll("Could not parse token update info. Forcing refresh...", {1, 0.5, 0})
        performTokenUpdate()
        return
      end
      
      -- Find our team in the list
      local remoteTimestamp = ""
      local tokenBagUrl = ""
      for _, bag in ipairs(ttsTokenBags) do
        if bag.team == teamSlug then
          remoteTimestamp = bag.tokens_last_modified or ""
          tokenBagUrl = bag.tokens_url or ""
          break
        end
      end
      
      if remoteTimestamp == "" or tokenBagUrl == "" then
        broadcastToAll("Could not find token bag in update list. Forcing refresh...", {1, 0.5, 0})
        performTokenUpdate()
        return
      end
      
      -- Compare timestamps
      if remoteTimestamp == lastTokenUpdate then
        broadcastToAll("Tokens already up to date! (Last: " .. lastTokenUpdate .. ")", {0, 1, 0})
        return
      else
        broadcastToAll("Token update available! Local: " .. lastTokenUpdate .. " | Remote: " .. remoteTimestamp, {0, 0.7, 1})
        performTokenUpdate(tokenBagUrl, remoteTimestamp)
      end
    end)
  else
    -- No timestamp info, force update
    broadcastToAll("No token timestamp info. Forcing refresh...", {1, 1, 0})
    performTokenUpdate()
  end
end

function performTokenUpdate(tokenBagUrl, newTimestamp)
  -- If we don't have the URL, fetch it from metadata
  if not tokenBagUrl then
    WebRequest.get(TTS_METADATA_URL, function(request)
      if request.is_error then
        broadcastToAll("Could not fetch token bag metadata.", {1, 0, 0})
        return
      end
      
      local success, ttsTokenBags = pcall(function() return JSON.decode(request.text) end)
      if not success or not ttsTokenBags then
        broadcastToAll("Could not parse token bag metadata.", {1, 0, 0})
        return
      end
      
      for _, bag in ipairs(ttsTokenBags) do
        if bag.team == teamSlug then
          tokenBagUrl = bag.tokens_url or ""
          newTimestamp = bag.tokens_last_modified or ""
          break
        end
      end
      
      if tokenBagUrl == "" then
        broadcastToAll("Token bag not found for " .. teamSlug, {1, 0, 0})
        return
      end
      
      -- Now we have the URL, do the actual update
      doTokenBagSpawn(tokenBagUrl, newTimestamp)
    end)
  else
    -- We already have the URL
    doTokenBagSpawn(tokenBagUrl, newTimestamp)
  end
end

function doTokenBagSpawn(tokenBagUrl, newTimestamp)
  -- Add cache busting parameter
  local timestamp = newTimestamp:gsub("[^%d]", "")  -- Strip to numbers only
  local urlWithCacheBust = tokenBagUrl .. "?v=" .. timestamp
  
  broadcastToAll("Updating token bags from GitHub...", {0, 0.7, 1})
  
  -- Save current positions of any existing token bags
  local existingBags = {}
  local allObjects = getAllObjects()
  for _, obj in ipairs(allObjects) do
    if obj.type == "Bag" and obj.getGMNotes() == teamSlug .. "-tokens" then
      table.insert(existingBags, {
        guid = obj.getGUID(),
        position = obj.getPosition(),
        rotation = obj.getRotation()
      })
    end
  end
  
  -- Fetch and spawn the new token bag
  WebRequest.get(urlWithCacheBust, function(request)
    if request.is_error then
      broadcastToAll("Failed to fetch token bag: " .. request.error, {1, 0, 0})
      return
    end
    
    local success, bagData = pcall(function() return JSON.decode(request.text) end)
    if not success or not bagData then
      broadcastToAll("Failed to parse token bag JSON", {1, 0, 0})
      return
    end
    
    -- Destroy old token bags
    for _, oldBag in ipairs(existingBags) do
      local obj = getObjectFromGUID(oldBag.guid)
      if obj then
        obj.destruct()
      end
    end
    
    -- Spawn new token bag(s) from JSON
    if bagData.ObjectStates then
      for _, objState in ipairs(bagData.ObjectStates) do
        -- Use saved position if we had one, otherwise spawn at card box position
        local spawnPos = self.getPosition() + Vector(3, 1, 0)
        if #existingBags > 0 then
          spawnPos = existingBags[1].position
        end
        
        objState.GUID = nil  -- Let TTS assign new GUID
        objState.Transform.posX = spawnPos.x
        objState.Transform.posY = spawnPos.y
        objState.Transform.posZ = spawnPos.z
        
        -- Set GM notes to identify this as our token bag
        objState.GMNotes = teamSlug .. "-tokens"
        
        spawnObjectData({
          data = objState,
          callback_function = function(spawnedObj)
            broadcastToAll("Token bag updated successfully!", {0, 1, 0})
            
            -- Update timestamp
            if newTimestamp then
              lastTokenUpdate = newTimestamp
              updateSave()
            end
          end
        })
      end
    else
      broadcastToAll("Invalid token bag format", {1, 0, 0})
    end
  end)
end
