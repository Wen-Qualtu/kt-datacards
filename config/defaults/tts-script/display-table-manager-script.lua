-- Kill Team Display Table Manager
-- Attach this to a bag to manage the display table

local TTS_BOXES_JSON_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/tts-card-boxes.json"
local isUpdating = false
local positions = {}

function onLoad(script_state)
    print("[KT Display Manager] Ready. Buttons: Refresh from GitHub | Place/Recall Teams")
    self.setName("KT Display Manager")
    self.setDescription("Manages Kill Team display table. Refresh from GitHub or Place/Recall all teams.")
    
    -- Load stored positions
    if script_state ~= "" then
        positions = JSON.decode(script_state)
    end
end

function refreshFromGitHub()
    if isUpdating then
        broadcastToAll("Refresh already in progress...", {1, 0.5, 0})
        return
    end
    
    isUpdating = true
    broadcastToAll("Fetching latest team list from GitHub...", {0.2, 0.8, 1})
    
    -- Fetch the minimal JSON with just TTS card box URLs
    WebRequest.get(TTS_BOXES_JSON_URL, function(webReturn)
        if webReturn.is_error then
            broadcastToAll("Error fetching team list: " .. webReturn.error, {1, 0, 0})
            isUpdating = false
            return
        end
        
        local success, teamBoxes = pcall(function() return JSON.decode(webReturn.text) end)
        if not success then
            broadcastToAll("Error parsing JSON: " .. tostring(teamBoxes), {1, 0, 0})
            isUpdating = false
            return
        end
        
        broadcastToAll("Found " .. #teamBoxes .. " teams. Clearing current contents...", {0.2, 0.8, 1})
        
        -- Clear current contents
        for _, obj in ipairs(self.getObjects()) do
            self.takeObject({guid = obj.guid}).destruct()
        end
        
        Wait.time(function()
            broadcastToAll("Fetching team bags...", {0.2, 0.8, 1})
            loadNext(teamBoxes, 1, 0)
        end, 1.0)
    end)
end

function loadNext(teamBoxes, index, added)
    if index > #teamBoxes then
        broadcastToAll("✓ Manager bag updated with " .. added .. " teams!", {0, 1, 0})
        isUpdating = false
        return
    end
    
    local box = teamBoxes[index]
    local cacheBust = math.random(1, 999999)
    local url = box.url .. "?v=" .. cacheBust
    
    WebRequest.get(url, function(webReturn)
        if webReturn.is_error then
            print("[Warning] Failed to fetch " .. box.name .. ": " .. webReturn.error)
            Wait.time(function() loadNext(teamBoxes, index + 1, added) end, 0.1)
            return
        end
        
        local success, decoded = pcall(function() return JSON.decode(webReturn.text) end)
        if not success or not decoded.ObjectStates or #decoded.ObjectStates == 0 then
            print("[Warning] Invalid JSON for " .. box.name)
            Wait.time(function() loadNext(teamBoxes, index + 1, added) end, 0.1)
            return
        end
        
        -- Get the team card box (first object)
        local teamBag = decoded.ObjectStates[1]
        local spawnedObj = spawnObjectJSON({
            json = JSON.encode(teamBag),
            position = self.getPosition() + Vector(0, 5, 0)
        })
        
        Wait.condition(
            function()
                self.putObject(spawnedObj)
                added = added + 1
                broadcastToAll("Added " .. box.name .. " (" .. added .. "/" .. #teamBoxes .. ")", {0.5, 0.5, 1})
                
                Wait.time(function()
                    loadNext(teamBoxes, index + 1, added)
                end, 0.1)
            end,
            function() return spawnedObj ~= nil and not spawnedObj.spawning end,
            5
        )
    end)
end

function placeTeamsOnTable()
    local contents = self.getObjects()
    
    if #contents == 0 then
        broadcastToAll("Manager bag is empty! Click 'Reload All Teams' first.", {1, 0.5, 0})
        return
    end
    
    broadcastToAll("Recalling any existing teams first...", {0.8, 0.8, 0.2})
    
    -- First, recall any existing team bags and clean up labels
    local recalled = 0
    for _, obj in ipairs(getAllObjects()) do
        if obj.type == "Bag" and obj ~= self and obj.getName() ~= "" then
            local name = obj.getName()
            if name ~= "KT Display Manager" and obj.getGUID() ~= self.getGUID() then
                self.putObject(obj)
                recalled = recalled + 1
            end
        end
    end
    
    -- Clean up old text labels
    for _, obj in ipairs(getAllObjects()) do
        if obj.getGMNotes() == "_team_label" then
            obj.destruct()
        end
    end
    
    if recalled > 0 then
        broadcastToAll("Recalled " .. recalled .. " existing teams.", {0.5, 0.5, 0.5})
    end
    
    -- Wait a moment before placing to ensure recall is complete
    Wait.time(function()
        broadcastToAll("Placing " .. #contents .. " teams on display table...", {0.2, 0.8, 1})
        
        -- Get manager bag position as reference point
        local bagPos = self.getPosition()
        
        -- Take out each team bag and spawn label
        local placed = 0
        for i, item in ipairs(contents) do
            Wait.time(function()
                local guid = item.guid
                local posData = positions[guid]
                
                if posData then
                    -- Calculate position relative to manager bag
                    local relativePos = {
                        x = bagPos.x + posData.pos.x,
                        y = bagPos.y + posData.pos.y,
                        z = bagPos.z + posData.pos.z - 30.0  -- Offset since bag is at Z=30
                    }
                    
                    local bagObj = self.takeObject({
                        guid = guid,
                        position = Vector(relativePos.x, relativePos.y, relativePos.z),
                        rotation = Vector(posData.rot.x, posData.rot.y, posData.rot.z),
                        smooth = false
                    })
                    
                    -- Spawn text label for this team
                    Wait.time(function()
                        if bagObj then
                            local teamName = bagObj.getName()
                            if teamName and teamName ~= "" then
                                spawnObject({
                                    type = "3DText",
                                    position = Vector(relativePos.x, relativePos.y - 2.2, relativePos.z + 3.0),
                                    rotation = Vector(90, 0, 0),
                                    scale = Vector(0.015, 0.015, 0.015),
                                    callback_function = function(obj)
                                        obj.TextTool.setValue(teamName)
                                        obj.TextTool.setFontSize(50)
                                        obj.setColorTint({r=1, g=1, b=1})
                                        obj.setLock(true)
                                        obj.setGMNotes("_team_label")
                                    end
                                })
                            end
                        end
                    end, 0.2)
                else
                    self.takeObject({
                        guid = guid,
                        smooth = false
                    })
                end
                
                placed = placed + 1
                if placed == #contents then
                    Wait.time(function()
                        broadcastToAll("✓ All teams placed on table!", {0, 1, 0})
                    end, 0.5)
                end
            end, i * 0.15)
        end
    end, 0.5)
end

function recallTeamsToManager()
    local recalled = 0
    
    -- Recall team bags
    for _, obj in ipairs(getAllObjects()) do
        if obj.type == "Bag" and obj ~= self and obj.getName() ~= "" then
            -- Check if it's a team bag (has specific tag pattern or name)
            local name = obj.getName()
            if name ~= "KT Display Manager" and obj.getGUID() ~= self.getGUID() then
                self.putObject(obj)
                recalled = recalled + 1
            end
        end
    end
    
    -- Clean up text labels
    for _, obj in ipairs(getAllObjects()) do
        if obj.getGMNotes() == "_team_label" then
            obj.destruct()
        end
    end
    
    if recalled > 0 then
        broadcastToAll("✓ Recalled " .. recalled .. " teams to manager bag.", {0, 1, 0})
    else
        broadcastToAll("No team bags found on table to recall.", {1, 0.5, 0})
    end
end
