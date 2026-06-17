-- Kill Team Display Table Manager
-- Attach this to a bag to manage the display table

-- New canonical source: keyed map { slug -> { team, modified, box={url, modified}, ... } }
-- Each box URL is a BARE Custom_Model_Bag JSON (no ObjectStates wrapper).
local TTS_METADATA_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/team-urls.json"
-- The manager bag itself is published as a bare Custom_Bag JSON (no save-file
-- wrapper) so it can be downloaded and handed straight to spawnObjectJSON.
local MANAGER_BAG_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/_generic-tts-objects/Kill%20Team%20Card%20Boxes.json"
local isUpdating = false
local cancelRequested = false
local positions = {}

-- URL-decode just enough to recover a human display name from a path segment
local function urlDecode(s)
    if not s then return "" end
    s = s:gsub("+", " ")
    s = s:gsub("%%(%x%x)", function(h) return string.char(tonumber(h, 16)) end)
    return s
end

-- Derive the display name (matches the bag's Nickname) from the box URL filename.
local function displayNameFromUrl(url)
    if not url or url == "" then return "" end
    local cleanUrl = string.match(url, "^[^?]+") or url
    local file = string.match(cleanUrl, "([^/]+)$") or cleanUrl
    file = file:gsub("%.json$", "")
    return urlDecode(file)
end

-- Extract the team bag from a downloaded box JSON. Supports both bare objects
-- (new format: { Name="Custom_Model_Bag", ContainedObjects=... }) and the
-- legacy save-file wrapper ({ ObjectStates = [ {box} ] }).
local function extractTeamBag(decoded)
    if type(decoded) ~= "table" then return nil end
    if decoded.ObjectStates and decoded.ObjectStates[1] then
        return decoded.ObjectStates[1]
    end
    if decoded.Name or decoded.GUID or decoded.ContainedObjects then
        return decoded
    end
    return nil
end

-- Returns true if the downloaded text is a bare box object (new format).
-- Detection is cheap: skip whitespace, find the first JSON key, and check it
-- against the two wrapper keys. Avoids JSON.decode on 500KB+ payloads.
local function isBareBoxText(text)
    if type(text) ~= "string" or #text == 0 then return false end
    local i = 1
    while i <= #text do
        local b = text:byte(i)
        if b ~= 32 and b ~= 9 and b ~= 10 and b ~= 13 then break end
        i = i + 1
    end
    if text:byte(i) ~= 123 then return false end -- '{'
    -- Find the first key (between quotes after the opening brace).
    local keyOpen = text:find('"', i + 1, true)
    if not keyOpen then return false end
    local keyClose = text:find('"', keyOpen + 1, true)
    if not keyClose then return false end
    local firstKey = text:sub(keyOpen + 1, keyClose - 1)
    return firstKey ~= "SaveName" and firstKey ~= "ObjectStates"
end

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

    -- Move infrequent actions to context menu to keep table UI compact.
    self.addContextMenuItem("Reload Teams", refreshFromGitHub)
    self.addContextMenuItem("Update Manager", selfUpdate)
end


function createButtons(mode)
    self.clearButtons()
    
    if mode == "updating" then
        -- Show only cancel button during update (centered in grid)
        self.createButton({
            label="Cancel Reload",
            click_function="cancelReload",
            function_owner=self,
            position={0, 0.3, -2.45},
            rotation={0, 180, 0},
            height=500, width=1400,
            font_size=180,
            color={1, 0, 0},
            font_color={1, 1, 1}
        })
    else
        -- Keep only core table actions on buttons, moved closer to bag.
        self.createButton({
            label="Place Teams",
            click_function="placeTeamsOnTable",
            function_owner=self,
            position={1.6, 0.3, -2.45},
            rotation={0, 180, 0},
            height=400, width=1200,
            font_size=150,
            color={0, 0.8, 0.2},
            font_color={1, 1, 1}
        })
        
        self.createButton({
            label="Recall Teams",
            click_function="recallTeamsToManager",
            function_owner=self,
            position={-1.6, 0.3, -2.45},
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
        
        local success, payload = pcall(function() return JSON.decode(webReturn.text) end)
        if not success or type(payload) ~= "table" then
            broadcastToAll("Error parsing JSON: " .. tostring(payload), {1, 0, 0})
            isUpdating = false
            return
        end

        -- Build lookup table of remote teams by display name.
        -- New shape (keyed map):
        --   payload[slug] = { team, modified, box = { url, modified } }
        -- Legacy shape (array): payload[i] = { name, cards_url, team, cards_last_modified, tokens_last_modified }
        local remoteTeams = {}
        if payload[1] ~= nil then
            -- Legacy array shape
            for _, box in ipairs(payload) do
                local cardsTs = box.cards_last_modified or ""
                local tokensTs = box.tokens_last_modified or ""
                local latestTs = cardsTs
                if tokensTs ~= "" and cardsTs ~= "" then
                    if tokensTs > cardsTs then latestTs = tokensTs end
                elseif tokensTs ~= "" then
                    latestTs = tokensTs
                end
                remoteTeams[box.name] = {
                    url = box.cards_url,
                    team = box.team,
                    last_modified = latestTs
                }
            end
        else
            -- New keyed-map shape
            for slug, entry in pairs(payload) do
                if type(entry) == "table" and entry.box and entry.box.url then
                    local boxUrl = entry.box.url
                    local modified = entry.box.modified or entry.modified or ""
                    local name = displayNameFromUrl(boxUrl)
                    if name ~= "" then
                        remoteTeams[name] = {
                            url = boxUrl,
                            team = slug,
                            last_modified = modified
                        }
                    end
                end
            end
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

        -- Fast path: bare boxes have asset URLs pre-cache-busted by the pipeline
        -- (Python writes ?v=mtime on every asset URL), so we can hand the raw
        -- text directly to spawnObjectJSON and skip a costly decode/encode round
        -- trip on a 500KB+ string.
        local spawnJson
        if isBareBoxText(webReturn.text) then
            spawnJson = webReturn.text
        else
            local success, decoded = pcall(function() return JSON.decode(webReturn.text) end)
            local teamBag = success and extractTeamBag(decoded) or nil
            if not teamBag then
                print("[Error] Invalid JSON for " .. teamName)
                Wait.time(function()
                    processAdds(toAdd, index + 1, remoteTeams, toUpdate, toSkip)
                end, 0.1)
                return
            end

            -- Legacy wrapper path: keep cache-busting fallback for any in-bag
            -- asset URLs that lack ?v= (older published boxes).
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
            spawnJson = JSON.encode(teamBag)
        end

        local spawnedObj = spawnObjectJSON({
            json = spawnJson,
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

                -- Fast path: bare boxes (asset URLs already cache-busted by pipeline).
                local spawnJson
                if isBareBoxText(webReturn.text) then
                    spawnJson = webReturn.text
                else
                    local success, decoded = pcall(function() return JSON.decode(webReturn.text) end)
                    local teamBag = success and extractTeamBag(decoded) or nil
                    if not teamBag then
                        print("[Error] Invalid JSON for " .. teamName)
                        Wait.time(function()
                            processUpdates(toUpdate, index + 1, remoteTeams, toSkip)
                        end, 0.1)
                        return
                    end

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
                    spawnJson = JSON.encode(teamBag)
                end

                local spawnedObj = spawnObjectJSON({
                    json = spawnJson,
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
        
        -- Take out each team bag
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
    
    if recalled > 0 then
        broadcastToAll("✓ Recalled " .. recalled .. " teams and saved positions.", {0, 1, 0})
    else
        broadcastToAll("No team bags found on table to recall.", {1, 0.5, 0})
    end
end

function selfUpdate()
    broadcastToAll("Downloading latest Manager bag...", {0.8, 0, 1})

    local url = MANAGER_BAG_URL .. "?v=" .. tostring(os.time())
    WebRequest.get(url, function(resp)
        local code = tonumber(resp.response_code) or 0
        if resp.is_error or code >= 400 then
            local msg = resp.error
            if msg == nil or msg == "" then msg = "HTTP " .. tostring(code) end
            broadcastToAll("Manager update failed: " .. msg, {1, 0, 0})
            return
        end

        -- The manager bag is a bare Custom_Bag JSON. Skip leading whitespace
        -- and hand the raw text to spawnObjectJSON (no decode of the ~30MB body).
        local body = resp.text or ""
        local startIdx = 1
        while startIdx <= #body do
            local b = body:byte(startIdx)
            if b ~= 32 and b ~= 9 and b ~= 10 and b ~= 13 then break end
            startIdx = startIdx + 1
        end
        if startIdx > #body or body:byte(startIdx) ~= 123 then
            broadcastToAll("Manager update failed: unexpected response format", {1, 0, 0})
            return
        end
        local objJson = (startIdx == 1) and body or body:sub(startIdx)

        local currentPos = self.getPosition()
        local currentRot = self.getRotation()
        local savedState = self.script_state

        broadcastToAll("Spawning new Manager bag...", {0.8, 0, 1})

        local spawned = spawnObjectJSON({
            json = objJson,
            position = currentPos + Vector(5, 0, 0),
            rotation = currentRot
        })

        if spawned == nil then
            broadcastToAll("Manager update failed: spawnObjectJSON returned nil", {1, 0, 0})
            return
        end

        Wait.condition(
            function()
                Wait.time(function()
                    if spawned == nil or spawned.isDestroyed() then
                        broadcastToAll("Manager update failed during spawn", {1, 0, 0})
                        return
                    end
                    -- Preserve saved positions so Place Teams still works.
                    spawned.script_state = savedState
                    self.destruct()
                    Wait.time(function()
                        spawned.setPositionSmooth(currentPos, false, true)
                        spawned.setRotationSmooth(currentRot, false, true)
                        broadcastToAll("Manager bag updated!", {0, 1, 0})
                    end, 0.3)
                end, 0.3)
            end,
            function() return spawned ~= nil and not spawned.spawning end,
            60
        )
    end)
end

