-- Kill Team Display Table Manager
-- Attach this to a bag to manage the display table

local TTS_METADATA_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/tts-metadata.json"
local MANAGER_METADATA_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/tts-manager.json"
local isUpdating = false
local cancelRequested = false
local positions = {}

-- Default grid layout: 10 columns x 8 rows = 80 spots
local GRID_COLUMNS = 10
local GRID_ROWS = 10
local GRID_SPACING_X = 7.5  -- Horizontal spacing between bags
local GRID_SPACING_Z = 9.0  -- Vertical spacing between bags
local GRID_START_Z = -8.0   -- First row starts below the manager bag

function onLoad(script_state)
    print("[KT Display Manager] Ready. Buttons: Reload, Place, Recall, Update Manager")
    self.setName("Kill Team Card Boxes")
    self.setDescription("Take out individual team card boxes (rightclick and search) or use 'Place team' for the full display. Click 'Reload Teams' to update with the latest teams.")
    
    -- Load stored positions (keyed by team name, not GUID)
    if script_state ~= "" and script_state ~= nil then
        local success, decoded = pcall(function() return JSON.decode(script_state) end)
        if success and decoded then
            positions = decoded
            print("[KT Display Manager] Loaded " .. getTableSize(positions) .. " saved positions")
        end
    end
    
    -- Create buttons
    createButtons()
end


function createButtons(mode)
    self.clearButtons()
    
    -- Description box always visible (non-clickable button for visual consistency)
    self.createButton({
        label="Kill Team Card Boxes\nTake out individual team card boxes (rightclick and search) or use 'Place on Table' for\nthe full display. Click 'Reload All Teams' to update with the latest teams.",
        click_function="doNothing",
        function_owner=self,
        position={0, 0.3, -1.8},
        rotation={0, 180, 0},
        height=600, width=4800,
        font_size=120,
        color={0, 0, 0},
        font_color={1, 1, 1}
    })
    
    if mode == "updating" then
        -- Show only cancel button during update (centered in grid)
        self.createButton({
            label="Cancel Reload",
            click_function="cancelReload",
            function_owner=self,
            position={0, 0.3, -3.5625},
            rotation={0, 180, 0},
            height=500, width=1400,
            font_size=180,
            color={1, 0, 0},
            font_color={1, 1, 1}
        })
    else
        -- Normal 2x2 button grid with proper spacing
        -- Top-left: Update Manager (swapped X for correct display)
        self.createButton({
            label="Update Manager",
            click_function="selfUpdate",
            function_owner=self,
            position={1.6, 0.3, -3.0},
            rotation={0, 180, 0},
            height=400, width=1200,
            font_size=150,
            color={0.8, 0, 1},
            font_color={1, 1, 1}
        })
        
        -- Top-right: Reload Teams (swapped X for correct display)
        self.createButton({
            label="Reload Teams",
            click_function="refreshFromGitHub",
            function_owner=self,
            position={-1.6, 0.3, -3.0},
            rotation={0, 180, 0},
            height=400, width=1200,
            font_size=150,
            color={0.2, 0.6, 1},
            font_color={1, 1, 1}
        })
        
        -- Bottom-left: Place Teams (swapped X for correct display)
        self.createButton({
            label="Place Teams",
            click_function="placeTeamsOnTable",
            function_owner=self,
            position={1.6, 0.3, -4.125},
            rotation={0, 180, 0},
            height=400, width=1200,
            font_size=150,
            color={0, 0.8, 0.2},
            font_color={1, 1, 1}
        })
        
        -- Bottom-right: Recall Teams (swapped X for correct display)
        self.createButton({
            label="Recall Teams",
            click_function="recallTeamsToManager",
            function_owner=self,
            position={-1.6, 0.3, -4.125},
            rotation={0, 180, 0},
            height=400, width=1200,
            font_size=150,
            color={1, 0.5, 0},
            font_color={1, 1, 1}
        })
    end
end

function onSave()
    return JSON.encode(positions)
end

function getTableSize(t)
    local count = 0
    for _ in pairs(t) do count = count + 1 end
    return count
end

function calculateGridPosition(index)
    -- Calculate grid position for a given index (1-based)
    -- Returns relative position from manager bag
    local row = math.floor((index - 1) / GRID_COLUMNS)
    local col = (index - 1) % GRID_COLUMNS
    
    -- Center the grid horizontally around the bag
    local offsetX = (col - (GRID_COLUMNS - 1) / 2.0) * GRID_SPACING_X
    local offsetZ = GRID_START_Z - (row * GRID_SPACING_Z)
    
    return {
        x = offsetX,
        y = 1.0,
        z = offsetZ
    }
end

function cancelReload()
    cancelRequested = true
    broadcastToAll("Cancelling reload... finishing current team.", {1, 0.5, 0})
end

function doNothing()
    -- Dummy function for non-clickable buttons (description box)
end

function refreshFromGitHub()
    if isUpdating then
        broadcastToAll("Refresh already in progress...", {1, 0.5, 0})
        return
    end
    
    isUpdating = true
    cancelRequested = false
    createButtons("updating")  -- Show cancel button
    broadcastToAll("Checking for team updates...", {0.2, 0.8, 1})
    
    -- Fetch the metadata with timestamps
    WebRequest.get(TTS_METADATA_URL, function(webReturn)
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
        
        -- Build lookup table of remote teams by name
        local remoteTeams = {}
        for _, box in ipairs(teamBoxes) do
            -- Use the latest timestamp (max of cards and tokens)
            local cardsTs = box.cards_last_modified or ""
            local tokensTs = box.tokens_last_modified or ""
            local latestTs = cardsTs
            -- Only compare if both have values
            if tokensTs ~= "" and cardsTs ~= "" then
                if tokensTs > cardsTs then
                    latestTs = tokensTs
                end
            elseif tokensTs ~= "" then
                -- Only tokens timestamp exists
                latestTs = tokensTs
            end
            
            remoteTeams[box.name] = {
                url = box.cards_url,
                team = box.team,
                last_modified = latestTs
            }
        end
        
        -- Check existing teams in bag
        local contents = self.getObjects()
        
        -- Build sorted list of all remote teams (alphabetical)
        local allRemoteTeams = {}
        for teamName, teamData in pairs(remoteTeams) do
            table.insert(allRemoteTeams, {name = teamName, data = teamData})
        end
        table.sort(allRemoteTeams, function(a, b) return a.name < b.name end)
        
        broadcastToAll("Analyzing " .. #allRemoteTeams .. " remote teams vs " .. #contents .. " local teams...", {0.5, 0.5, 1})
        
        -- Quick pass: categorize all teams
        analyzeTeams(remoteTeams, allRemoteTeams, contents, 1, {}, {}, {})
    end)
end

function analyzeTeams(remoteTeams, allRemoteTeams, contents, index, toAdd, toUpdate, toSkip)
    -- Check if user cancelled
    if cancelRequested then
        broadcastToAll("✓ Reload cancelled.", {1, 0.8, 0})
        isUpdating = false
        cancelRequested = false
        createButtons()
        return
    end
    
    -- Done analyzing, report summary and start processing
    if index > #allRemoteTeams then
        local total = #allRemoteTeams
        broadcastToAll("━━━━━━━━━━━━━━━━━━━━━━━━━━━━", {0.7, 0.7, 0.7})
        broadcastToAll("Total: " .. total .. " | Add: " .. #toAdd .. " | Update: " .. #toUpdate .. " | Skip: " .. #toSkip, {0.2, 0.8, 1})
        broadcastToAll("━━━━━━━━━━━━━━━━━━━━━━━━━━━━", {0.7, 0.7, 0.7})
        
        -- Process in order: add new teams, then update existing teams
        if #toAdd > 0 then
            processAdds(toAdd, 1, remoteTeams, toUpdate, toSkip)
        elseif #toUpdate > 0 then
            processUpdates(toUpdate, 1, remoteTeams, toSkip)
        else
            broadcastToAll("✓ All teams are up to date!", {0, 1, 0})
            isUpdating = false
            cancelRequested = false
            createButtons()
        end
        return
    end
    
    local remoteTeam = allRemoteTeams[index]
    local teamName = remoteTeam.name
    local teamData = remoteTeam.data
    
    -- Find this team in local contents
    local localItem = nil
    for _, item in ipairs(contents) do
        if item.name == teamName then
            localItem = item
            break
        end
    end
    
    if not localItem then
        -- Team is missing, needs to be added
        table.insert(toAdd, {name = teamName, data = teamData})
        Wait.time(function()
            analyzeTeams(remoteTeams, allRemoteTeams, contents, index + 1, toAdd, toUpdate, toSkip)
        end, 0.05)
    else
        -- Team exists, check if it needs updating
        local takenObj = self.takeObject({
            guid = localItem.guid,
            position = self.getPosition() + Vector(0, 3, 0),
            smooth = false
        })
        
        Wait.condition(
            function()
                local scriptState = takenObj.script_state
                local localTimestamp = ""
                
                if scriptState and scriptState ~= "" then
                    local success, decoded = pcall(function() return JSON.decode(scriptState) end)
                    if success and decoded then
                        -- Use the latest of card or token timestamps
                        local cardTs = decoded.lastCardUpdate or ""
                        local tokenTs = decoded.lastTokenUpdate or ""
                        localTimestamp = cardTs
                        -- Only compare if both have values
                        if tokenTs ~= "" and cardTs ~= "" then
                            if tokenTs > cardTs then
                                localTimestamp = tokenTs
                            end
                        elseif tokenTs ~= "" then
                            -- Only tokens timestamp exists
                            localTimestamp = tokenTs
                        end
                    end
                end
                
                local remoteTimestamp = teamData.last_modified
                local localTrunc = localTimestamp:sub(1, 16)
                local remoteTrunc = remoteTimestamp:sub(1, 16)
                
                -- Put it back
                self.putObject(takenObj)
                
                if localTrunc == remoteTrunc and localTimestamp ~= "" then
                    -- Up to date, skip
                    table.insert(toSkip, {name = teamName, guid = localItem.guid})
                else
                    -- Needs update
                    table.insert(toUpdate, {name = teamName, guid = localItem.guid, data = teamData, localTs = localTimestamp, remoteTs = remoteTimestamp})
                end
                
                Wait.time(function()
                    analyzeTeams(remoteTeams, allRemoteTeams, contents, index + 1, toAdd, toUpdate, toSkip)
                end, 0.05)
            end,
            function() return takenObj ~= nil and not takenObj.spawning end,
            5
        )
    end
end

function processAdds(toAdd, index, remoteTeams, toUpdate, toSkip)
    -- Check if user cancelled
    if cancelRequested then
        broadcastToAll("✓ Reload cancelled.", {1, 0.8, 0})
        isUpdating = false
        cancelRequested = false
        createButtons()
        return
    end
    
    if index > #toAdd then
        -- Done adding, move to updates
        if #toUpdate > 0 then
            processUpdates(toUpdate, 1, remoteTeams, toSkip)
        else
            broadcastToAll("✓ Done! Added: " .. #toAdd .. " | Skip: " .. #toSkip, {0, 1, 0})
            isUpdating = false
            cancelRequested = false
            createButtons()
        end
        return
    end
    
    local team = toAdd[index]
    local teamName = team.name
    local teamData = team.data
    
    local cacheBust = (teamData.last_modified or ""):gsub("[^%d]", "")
    local url = teamData.url .. "?v=" .. cacheBust
    
    broadcastToAll("+ Adding " .. teamName .. "... (" .. index .. "/" .. #toAdd .. ")", {0.5, 1, 0.5})
    
    WebRequest.get(url, function(webReturn)
        if webReturn.is_error then
            print("[Error] Failed to fetch " .. teamName .. ": " .. webReturn.error)
            Wait.time(function()
                processAdds(toAdd, index + 1, remoteTeams, toUpdate, toSkip)
            end, 0.1)
            return
        end
        
        local success, decoded = pcall(function() return JSON.decode(webReturn.text) end)
        if not success or not decoded.ObjectStates or #decoded.ObjectStates == 0 then
            print("[Error] Invalid JSON for " .. teamName)
            Wait.time(function()
                processAdds(toAdd, index + 1, remoteTeams, toUpdate, toSkip)
            end, 0.1)
            return
        end
        
        local teamBag = decoded.ObjectStates[1]
        
        -- Apply cache busting to all token URLs inside the bag
        if teamBag.ContainedObjects then
            for _, obj in ipairs(teamBag.ContainedObjects) do
                if obj.CustomImage then
                    if obj.CustomImage.ImageURL and not obj.CustomImage.ImageURL:find("?v=") then
                        obj.CustomImage.ImageURL = obj.CustomImage.ImageURL .. "?v=" .. cacheBust
                    end
                    if obj.CustomImage.ImageSecondaryURL and not obj.CustomImage.ImageSecondaryURL:find("?v=") then
                        obj.CustomImage.ImageSecondaryURL = obj.CustomImage.ImageSecondaryURL .. "?v=" .. cacheBust
                    end
                end
                if obj.CustomTile and obj.CustomTile.CustomImage then
                    if obj.CustomTile.CustomImage.ImageURL and not obj.CustomTile.CustomImage.ImageURL:find("?v=") then
                        obj.CustomTile.CustomImage.ImageURL = obj.CustomTile.CustomImage.ImageURL .. "?v=" .. cacheBust
                    end
                end
            end
        end
        
        local spawnedObj = spawnObjectJSON({
            json = JSON.encode(teamBag),
            position = self.getPosition() + Vector(0, 5, 0)
        })
        
        Wait.condition(
            function()
                -- Wait a moment for the object's script state to fully initialize
                Wait.time(function()
                    self.putObject(spawnedObj)
                    Wait.time(function()
                        processAdds(toAdd, index + 1, remoteTeams, toUpdate, toSkip)
                    end, 0.2)
                end, 0.3)
            end,
            function() return spawnedObj ~= nil and not spawnedObj.spawning end,
            5
        )
    end)
end

function processUpdates(toUpdate, index, remoteTeams, toSkip)
    -- Check if user cancelled
    if cancelRequested then
        broadcastToAll("✓ Reload cancelled.", {1, 0.8, 0})
        isUpdating = false
        cancelRequested = false
        createButtons()
        return
    end
    
    if index > #toUpdate then
        -- Done updating, process skips
        processSkips(toSkip, 1)
        return
    end
    
    local team = toUpdate[index]
    local teamName = team.name
    local teamData = team.data
    
    broadcastToAll("↻ Updating " .. teamName .. "... (" .. index .. "/" .. #toUpdate .. ")", {1, 0.8, 0})
    
    -- Take out old version and destroy it
    local takenObj = self.takeObject({
        guid = team.guid,
        position = self.getPosition() + Vector(0, 3, 0),
        smooth = false
    })
    
    Wait.condition(
        function()
            takenObj.destruct()
            
            -- Download and spawn new version
            local cacheBust = teamData.last_modified:gsub("[^%d]", "")
            local url = teamData.url .. "?v=" .. cacheBust
            
            WebRequest.get(url, function(webReturn)
                if webReturn.is_error then
                    print("[Error] Failed to fetch " .. teamName .. ": " .. webReturn.error)
                    Wait.time(function()
                        processUpdates(toUpdate, index + 1, remoteTeams, toSkip)
                    end, 0.1)
                    return
                end
                
                local success, decoded = pcall(function() return JSON.decode(webReturn.text) end)
                if not success or not decoded.ObjectStates or #decoded.ObjectStates == 0 then
                    print("[Error] Invalid JSON for " .. teamName)
                    Wait.time(function()
                        processUpdates(toUpdate, index + 1, remoteTeams, toSkip)
                    end, 0.1)
                    return
                end
                
                local teamBag = decoded.ObjectStates[1]
                
                -- Apply cache busting to all token URLs inside the bag
                if teamBag.ContainedObjects then
                    for _, obj in ipairs(teamBag.ContainedObjects) do
                        if obj.CustomImage then
                            if obj.CustomImage.ImageURL and not obj.CustomImage.ImageURL:find("?v=") then
                                obj.CustomImage.ImageURL = obj.CustomImage.ImageURL .. "?v=" .. cacheBust
                            end
                            if obj.CustomImage.ImageSecondaryURL and not obj.CustomImage.ImageSecondaryURL:find("?v=") then
                                obj.CustomImage.ImageSecondaryURL = obj.CustomImage.ImageSecondaryURL .. "?v=" .. cacheBust
                            end
                        end
                        if obj.CustomTile and obj.CustomTile.CustomImage then
                            if obj.CustomTile.CustomImage.ImageURL and not obj.CustomTile.CustomImage.ImageURL:find("?v=") then
                                obj.CustomTile.CustomImage.ImageURL = obj.CustomTile.CustomImage.ImageURL .. "?v=" .. cacheBust
                            end
                        end
                    end
                end
                
                local spawnedObj = spawnObjectJSON({
                    json = JSON.encode(teamBag),
                    position = self.getPosition() + Vector(0, 5, 0)
                })
                
                Wait.condition(
                    function()
                        -- Wait a moment for the object's script state to fully initialize
                        Wait.time(function()
                            self.putObject(spawnedObj)
                            Wait.time(function()
                                processUpdates(toUpdate, index + 1, remoteTeams, toSkip)
                            end, 0.2)
                        end, 0.3)
                    end,
                    function() return spawnedObj ~= nil and not spawnedObj.spawning end,
                    5
                )
            end)
        end,
        function() return takenObj ~= nil and not takenObj.spawning end,
        5
    )
end

function processSkips(toSkip, index)
    -- Check if user cancelled
    if cancelRequested then
        broadcastToAll("✓ Reload cancelled.", {1, 0.8, 0})
        isUpdating = false
        cancelRequested = false
        createButtons()
        return
    end
    
    if index > #toSkip then
        broadcastToAll("✓ All done!", {0, 1, 0})
        isUpdating = false
        cancelRequested = false
        createButtons()
        return
    end
    
    local team = toSkip[index]
    broadcastToAll("⊙ Skipping " .. team.name .. " (current) (" .. index .. "/" .. #toSkip .. ")", {0.5, 0.5, 0.5})
    
    Wait.time(function()
        processSkips(toSkip, index + 1)
    end, 0.1)
end

function placeTeamsOnTable()
    local contents = self.getObjects()
    
    if #contents == 0 then
        broadcastToAll("Manager bag is empty! Click 'Reload Teams' first.", {1, 0.5, 0})
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
        
        -- Build list of teams with their data
        local teamList = {}
        for i, item in ipairs(contents) do
            table.insert(teamList, {
                guid = item.guid,
                name = item.name
            })
        end
        
        -- Sort teams alphabetically for default grid placement
        table.sort(teamList, function(a, b)
            return a.name < b.name
        end)
        
        -- Take out each team bag and spawn label
        local placed = 0
        for i, team in ipairs(teamList) do
            Wait.time(function()
                local guid = team.guid
                local teamName = team.name
                local posData = positions[teamName]  -- Check for saved custom position
                
                local relativePos
                if posData then
                    -- Use saved custom position
                    relativePos = {
                        x = bagPos.x + posData.pos.x,
                        y = bagPos.y + posData.pos.y,
                        z = bagPos.z + posData.pos.z
                    }
                else
                    -- Use default grid position (alphabetical order)
                    local gridPos = calculateGridPosition(i)
                    relativePos = {
                        x = bagPos.x + gridPos.x,
                        y = bagPos.y + gridPos.y,
                        z = bagPos.z + gridPos.z
                    }
                end
                
                local bagObj = self.takeObject({
                    guid = guid,
                    position = Vector(relativePos.x, relativePos.y, relativePos.z),
                    rotation = posData and Vector(posData.rot.x, posData.rot.y, posData.rot.z) or Vector(0, 270, 0),
                    smooth = false
                })
                
                -- Spawn text label for this team
                Wait.time(function()
                    if bagObj and teamName and teamName ~= "" then
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
                end, 0.2)
                
                placed = placed + 1
                if placed == #teamList then
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
    
    -- Save positions before recalling (keyed by team name)
    for _, obj in ipairs(getAllObjects()) do
        if obj.type == "Bag" and obj ~= self and obj.getName() ~= "" then
            local name = obj.getName()
            if name ~= "KT Display Manager" and obj.getGUID() ~= self.getGUID() then
                -- Store position relative to manager bag
                local bagPos = self.getPosition()
                local objPos = obj.getPosition()
                local objRot = obj.getRotation()
                
                positions[name] = {
                    pos = {
                        x = objPos.x - bagPos.x,
                        y = objPos.y - bagPos.y,
                        z = objPos.z - bagPos.z
                    },
                    rot = {x = objRot.x, y = objRot.y, z = objRot.z}
                }
                
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
        broadcastToAll("✓ Recalled " .. recalled .. " teams and saved positions.", {0, 1, 0})
    else
        broadcastToAll("No team bags found on table to recall.", {1, 0.5, 0})
    end
end

function selfUpdate()
    broadcastToAll("Checking for Manager updates...", {0.8, 0, 1})
    
    -- Fetch manager metadata to get latest version URL
    WebRequest.get(MANAGER_METADATA_URL, function(request)
        if request.is_error then
            broadcastToAll("Could not check for Manager updates: " .. request.error, {1, 0, 0})
            return
        end
        
        local success, metadata = pcall(function() return JSON.decode(request.text) end)
        if not success or not metadata or not metadata.url then
            broadcastToAll("Could not parse Manager metadata", {1, 0, 0})
            return
        end
        
        local managerUrl = metadata.url
        local timestamp = (metadata.last_modified or ""):gsub("[^%d]", "")
        local urlWithCacheBust = managerUrl .. "?v=" .. timestamp
        
        broadcastToAll("Downloading latest Manager bag...", {0.8, 0, 1})
        
        -- Fetch the new manager bag JSON
        WebRequest.get(urlWithCacheBust, function(webReturn)
            if webReturn.is_error then
                broadcastToAll("Failed to download Manager: " .. webReturn.error, {1, 0, 0})
                return
            end
            
            local success2, newBagData = pcall(function() return JSON.decode(webReturn.text) end)
            if not success2 or not newBagData or not newBagData.ObjectStates or #newBagData.ObjectStates == 0 then
                broadcastToAll("Invalid Manager bag format", {1, 0, 0})
                return
            end
            
            broadcastToAll("Spawning new Manager bag...", {0.8, 0, 1})
            
            -- Get current state
            local currentPos = self.getPosition()
            local currentRot = self.getRotation()
            local savedState = self.script_state
            local contents = self.getObjects()
            
            -- Spawn new manager bag NEXT TO the old one (not on top)
            local newBagState = newBagData.ObjectStates[1]
            newBagState.Transform.posX = currentPos.x + 5.0  -- Offset 5 units to the side
            newBagState.Transform.posY = currentPos.y
            newBagState.Transform.posZ = currentPos.z
            newBagState.Transform.rotX = currentRot.x
            newBagState.Transform.rotY = currentRot.y
            newBagState.Transform.rotZ = currentRot.z
            newBagState.LuaScriptState = ""  -- Start with empty state, will update after transfer
            newBagState.ContainedObjects = {}  -- Spawn empty bag
            
            spawnObjectData({
                data = newBagState,
                callback_function = function(newBag)
                    if #contents == 0 then
                        -- No contents to transfer, restore state and destroy old bag
                        newBag.script_state = savedState
                        broadcastToAll("✓ Manager updated! Old Manager destroyed.", {0, 1, 0})
                        
                        -- Move new bag to old position
                        Wait.time(function()
                            newBag.setPositionSmooth(currentPos, false, false)
                            Wait.time(function()
                                self.destruct()
                            end, 0.5)
                        end, 0.3)
                    else
                        -- Transfer contents one at a time
                        broadcastToAll("Transferring " .. #contents .. " team boxes...", {0.8, 0, 1})
                        transferNextBox(newBag, contents, 1, #contents, currentPos, savedState)
                    end
                end
            })
        end)
    end)
end

function transferNextBox(newBag, contents, index, total, originalPos, savedState)
    if index > total then
        -- All transferred, NOW restore the state, then move and destroy
        broadcastToAll("✓ Manager updated! All " .. total .. " teams transferred. Restoring state...", {0, 1, 0})
        newBag.script_state = savedState  -- Restore saved positions AFTER transfer
        
        Wait.time(function()
            newBag.setPositionSmooth(originalPos, false, false)
            Wait.time(function()
                self.destruct()
            end, 1.0)
        end, 0.3)
        return
    end
    
    local item = contents[index]
    broadcastToAll("Transferring " .. (item.name or "team") .. " (" .. index .. "/" .. total .. ")", {0.6, 0.6, 1})
    
    -- Take object from old bag and place it to the side (not above)
    local takenObj = self.takeObject({
        guid = item.guid,
        position = self.getPosition() + Vector(0, 1, 5),  -- To the side, not above
        smooth = false
    })
    
    -- Wait for it to spawn, then put in new bag
    Wait.condition(
        function()
            newBag.putObject(takenObj)
            
            -- Wait a moment for putObject to complete, then transfer next
            Wait.time(function()
                transferNextBox(newBag, contents, index + 1, total, originalPos, savedState)
            end, 0.1)
        end,
        function() return takenObj ~= nil and not takenObj.spawning end,
        5,
        function()
            -- Timeout - skip this one and move to next
            print("[Warning] Timeout transferring " .. (item.name or item.guid))
            transferNextBox(newBag, contents, index + 1, total, originalPos, savedState)
        end
    )
end

