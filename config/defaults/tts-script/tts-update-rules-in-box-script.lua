-- constants
local TTS_METADATA_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/tts-metadata.json"

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
    -- Will be initialized from metadata on first setup
    lastCardUpdate = ""
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

function click_place()
  local bagObjList = self.getObjects()
  local currentRotation = readRotation()

  local newMemoryList = {}
  for guid, entry in pairs(memoryList) do
    local obj = getObjectFromGUID(guid)
    local selfPos = self.getPosition()
    local rot = { x=entry.rot.x, y=entry.rot.y, z=entry.rot.z }
    local rotationAdjustment = currentRotation - relativeRotation

    rot.y = rot.y + rotationAdjustment
    if (rot.y > 360) then
      rot.y = rot.y - 360
    elseif (rot.y < 0) then
      rot.y = rot.y + 360
    end

    if obj ~= nil then
      local deltaPos = compare_coords(selfPos, entry.pos, rotationAdjustment)
      obj.setPosition(deltaPos)
      obj.setRotation(rot)
      obj.setLock(entry.lock)
      newMemoryList[obj.guid] = memoryList[obj.guid]
    else
      for _, bagObj in ipairs(bagObjList) do
        if bagObj.guid == guid then
          local deltaPos = compare_coords(selfPos, entry.pos, rotationAdjustment)
          local item = self.takeObject({
            guid=guid,
            position=deltaPos,
            rotation=rot,
            smooth=false
          })

          newItem = item.clone({
            position=deltaPos,
            rotation=rot,
            smooth=false
          })
          item.destruct()

          newItem.setLock(entry.lock)
          newItem.setPosition(deltaPos)
          newMemoryList[newItem.guid] = memoryList[guid]
          break
        end
      end
    end
  end

  memoryList = {}
  for k,v in pairs(newMemoryList) do
   memoryList[k] = v
  end
  broadcastToAll("Objects Placed", {1,1,1})
  updateSave()
end

function click_recall()
  for guid, entry in pairs(memoryList) do
    local obj = getObjectFromGUID(guid)
    if obj ~= nil then
      self.putObject(obj)
    end
  end
  broadcastToAll("Objects Recalled", {1,1,1})
end

function click_update_rules()
  local bagObjList = self.getObjects()
  
  if #bagObjList == 0 then
    broadcastToAll("Bag is empty. Click Recall first, then Update.", {1, 0.5, 0})
    return
  end
  
  -- Check if we need to update by comparing timestamps
  if teamSlug ~= "" and lastCardUpdate ~= "" then
    broadcastToAll("Checking for updates...", {1, 1, 0})
    
    -- Fetch tts-metadata.json to check if update is needed
    WebRequest.get(TTS_METADATA_URL, function(request)
      if request.is_error then
        broadcastToAll("Could not check for updates. Forcing refresh...", {1, 0.5, 0})
        performUpdate()
        return
      end
      
      -- Parse JSON to find this team's last_modified timestamp
      local success, ttsBoxes = pcall(function() return JSON.decode(request.text) end)
      if not success or not ttsBoxes then
        broadcastToAll("Could not parse update info. Forcing refresh...", {1, 0.5, 0})
        performUpdate()
        return
      end
      
      -- Find our team in the list
      local remoteTimestamp = ""
      for _, box in ipairs(ttsBoxes) do
        if box.team == teamSlug then
          remoteTimestamp = box.cards_last_modified or ""
          break
        end
      end
      
      if remoteTimestamp == "" then
        broadcastToAll("Could not find team in update list. Forcing refresh...", {1, 0.5, 0})
        performUpdate()
        return
      end
      
      -- Compare timestamps
      if remoteTimestamp == lastCardUpdate then
        broadcastToAll("Cards already up to date! (Last: " .. lastCardUpdate .. ")", {0, 1, 0})
        return
      else
        broadcastToAll("Card update available! Local: " .. lastCardUpdate .. " | Remote: " .. remoteTimestamp, {0, 0.7, 1})
        performUpdate(remoteTimestamp)
      end
    end)
  else
    -- No timestamp info, force update
    broadcastToAll("No card timestamp info. Forcing refresh...", {1, 1, 0})
    performUpdate()
  end
end

function performUpdate(newTimestamp)
  local bagObjList = self.getObjects()
  broadcastToAll("Updating rules and box texture... Please wait and do NOT click other buttons.", {1, 1, 0})
  
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
  
  -- Process objects one at a time sequentially
  local function processNextObject(index)
    if index > #objectsToUpdate then
      -- All done - now update the bag texture and mesh last
      Wait.time(function()
        local bagCustom = self.getCustomObject()
        if bagCustom then
          if bagCustom.diffuse then
            bagCustom.diffuse = bagCustom.diffuse .. "?v=" .. cacheBust
          end
          if bagCustom.mesh then
            bagCustom.mesh = bagCustom.mesh .. "?v=" .. cacheBust
          end
          self.setCustomObject(bagCustom)
          self.reload()
        end
        
        -- Update timestamp if we got a new one
        if newTimestamp then
          lastCardUpdate = newTimestamp
          updateSave()
        end
        
        broadcastToAll("✓ Cards updated! (" .. processedCount .. " cards, box texture, mesh). Now updating tokens...", {0, 1, 0})
        
        -- Wait for reload to complete before updating tokens
        Wait.condition(
          function()
            click_update_tokens()
          end,
          function()
            return not self.spawning
          end,
          5
        )
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
              deck.FaceURL = deck.FaceURL .. "?v=" .. cacheBust
              deck.BackURL = deck.BackURL .. "?v=" .. cacheBust
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
        else
          local customObj = obj.getCustomObject()
          if customObj and (customObj.face or customObj.back) then
            if customObj.face then
              customObj.face = customObj.face .. "?v=" .. cacheBust
            end
            if customObj.back then
              customObj.back = customObj.back .. "?v=" .. cacheBust
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
