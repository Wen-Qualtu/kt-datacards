-- Kill Team Spawner Token
-- Click button to spawn any Kill Team card box

local TTS_BOXES_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/feature/add-team-spawner-object/output_v2/tts-card-boxes.json"
local METADATA_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/feature/add-team-spawner-object/output_v2/metadata.yaml"
local allTeams = {}
local teamsByNumber = {}
local teamsByName = {}
local teamMetadata = {}

function onLoad()
    print("[KT Spawner] Ready - Click button to spawn a team")
    self.setName("Kill Team Spawner")
    updateDescription()
    
    -- Create spawn button
    self.createButton({
        label="Spawn Team",
        click_function="showTeamSelector",
        function_owner=self,
        position={0, 0.2, 0},
        rotation={0, 0, 0},
        height=800, width=2000,
        font_size=350,
        color={0, 0.8, 0.2},
        font_color={1, 1, 1}
    })
    
    -- Load team list and metadata from GitHub
    loadMetadata()
    loadTeamList()
end

function loadMetadata()
    WebRequest.get(METADATA_URL, function(request)
        if request.is_error then
            print("[KT Spawner] Error loading metadata: " .. request.error)
            return
        end
        
        -- Parse YAML metadata (simplified parsing for faction only)
        local lines = {}
        for line in request.text:gmatch("[^\r\n]+") do
            table.insert(lines, line)
        end
        
        local currentTeam = nil
        for _, line in ipairs(lines) do
            -- Match team ID
            local teamId = line:match("^  ([%w%-]+):")
            if teamId then
                currentTeam = teamId
                teamMetadata[teamId] = {}
            end
            
            -- Match faction within a team
            if currentTeam and line:match("^    faction:") then
                local faction = line:match("faction:%s*(.+)")
                if faction then
                    teamMetadata[currentTeam].faction = faction
                end
            end
        end
        
        print("[KT Spawner] Loaded metadata for " .. getTableSize(teamMetadata) .. " teams")
    end)
end

function getTableSize(t)
    local count = 0
    for _ in pairs(t) do count = count + 1 end
    return count
end

function updateDescription()
    if #allTeams == 0 then
        self.setDescription("Click button to spawn any Kill Team card box.\nSupports team number (1-44) or name.\nChat: /spawn <team>\n\nLoading team list...")
    else
        local desc = "Click button to spawn a team. Type number or name.\nChat: /spawn <team>\n\nAVAILABLE TEAMS:\n"
        for i, team in ipairs(allTeams) do
            desc = desc .. string.format("%2d. %s\n", i, team.name)
        end
        self.setDescription(desc)
    end
end

function loadTeamList()
    WebRequest.get(TTS_BOXES_URL, function(request)
        if request.is_error then
            print("[KT Spawner] Error loading team list: " .. request.error)
            broadcastToAll("Failed to load team list from GitHub", {1, 0, 0})
            return
        end
        
        local success, decoded = pcall(function() return JSON.decode(request.text) end)
        if not success or not decoded then
            print("[KT Spawner] Error parsing team list")
            broadcastToAll("Failed to parse team list", {1, 0, 0})
            return
        end
        
        -- Sort teams alphabetically by name
        table.sort(decoded, function(a, b)
            return a.name:lower() < b.name:lower()
        end)
        
        allTeams = decoded
        
        -- Build lookup tables
        for i, team in ipairs(allTeams) do
            teamsByNumber[i] = team
            -- Store by lowercase name for case-insensitive matching
            teamsByName[team.name:lower()] = team
            -- Also store by team ID for alternative matching
            teamsByName[team.team:lower()] = team
        end
        
        print("[KT Spawner] Loaded " .. #allTeams .. " teams")
        updateDescription()
    end)
end

function showTeamSelector(obj, playerColor, altClick)
    print("[KT Spawner] === showTeamSelector called ===")
    print("[KT Spawner] playerColor type: " .. type(playerColor))
    print("[KT Spawner] playerColor value: " .. tostring(playerColor))
    print("[KT Spawner] Player global type: " .. type(Player))
    
    if playerColor then
        local playerObj = Player[playerColor]
        print("[KT Spawner] Player[playerColor] type: " .. type(playerObj))
        print("[KT Spawner] Player[playerColor] value: " .. tostring(playerObj))
        
        if playerObj then
            print("[KT Spawner] Player object exists, checking showOptionsDialog method")
            print("[KT Spawner] showOptionsDialog type: " .. type(playerObj.showOptionsDialog))
        else
            print("[KT Spawner] ERROR: Player[playerColor] is nil!")
            return
        end
    else
        print("[KT Spawner] ERROR: playerColor is nil!")
        return
    end
    
    if #allTeams == 0 then
        Player[playerColor].broadcast("Team list not loaded yet, please wait...", {1, 0.5, 0})
        return
    end
    
    -- Dynamically discover factions and group teams
    local factionGroups = {}
    local factionSet = {}
    
    for i, team in ipairs(allTeams) do
        local faction = "uncategorized" -- default
        
        -- Safely access metadata
        if teamMetadata and team.team and teamMetadata[team.team] then
            if teamMetadata[team.team].faction then
                faction = teamMetadata[team.team].faction:lower()
            end
        end
        
        -- Create faction group if it doesn't exist
        if not factionGroups[faction] then
            factionGroups[faction] = {}
            factionSet[faction] = true
        end
        
        table.insert(factionGroups[faction], team)
    end
    
    -- Build sorted list of faction names (capitalize first letter)
    local factionNames = {}
    for faction in pairs(factionSet) do
        table.insert(factionNames, faction:sub(1,1):upper() .. faction:sub(2))
    end
    table.sort(factionNames)
    
    -- Debug: Print available factions
    print("[KT Spawner] Available factions:")
    for k, v in pairs(factionGroups) do
        print("  - " .. k .. ": " .. #v .. " teams")
    end
    print("[KT Spawner] Faction names for dialog:")
    for i, name in ipairs(factionNames) do
        print("  " .. i .. ": " .. name)
    end
    
    -- Cache player reference before callbacks
    local playerObj = Player[playerColor]
    if not playerObj then
        print("[KT Spawner] ERROR: Player[" .. tostring(playerColor) .. "] is nil!")
        return
    end
    
    -- Show faction selection
    playerObj.showOptionsDialog("Select Faction", factionNames, 1, function(factionChoice)
        if not factionChoice then 
            print("[KT Spawner] No faction selected")
            return 
        end
        
        print("[KT Spawner] Faction choice index: " .. tostring(factionChoice))
        
        local factionDisplayName = factionNames[factionChoice]
        if not factionDisplayName then
            playerObj.broadcast("Invalid faction selection", {1, 0, 0})
            return
        end
        
        print("[KT Spawner] Faction display name: " .. factionDisplayName)
        
        local factionKey = factionDisplayName:lower()
        local factionTeams = factionGroups[factionKey]
        
        print("[KT Spawner] Faction key: " .. factionKey)
        print("[KT Spawner] factionTeams is nil: " .. tostring(factionTeams == nil))
        
        if not factionTeams or #factionTeams == 0 then
            playerObj.broadcast("No teams found for " .. factionDisplayName, {1, 0.5, 0})
            return
        end
        
        print("[KT Spawner] Found " .. #factionTeams .. " teams for " .. factionKey)
        
        -- Build team names for this faction
        local teamNames = {}
        for _, team in ipairs(factionTeams) do
            if team and team.name then
                table.insert(teamNames, team.name)
            end
        end
        
        -- Show team selection for chosen faction
        playerObj.showOptionsDialog("Select " .. factionDisplayName .. " Team", teamNames, 1, function(teamChoice)
            if not teamChoice then 
                print("[KT Spawner] No team selected")
                return 
            end
            
            print("[KT Spawner] Team choice: " .. tostring(teamChoice))
            
            if teamChoice and factionTeams and factionTeams[teamChoice] then
                spawnTeamByObject(factionTeams[teamChoice], playerColor)
            else
                print("[KT Spawner] ERROR: Invalid team choice or factionTeams is nil")
                if factionTeams then
                    print("[KT Spawner] factionTeams has " .. #factionTeams .. " items")
                else
                    print("[KT Spawner] factionTeams is nil!")
                end
            end
        end)
    end)
end

function spawnTeamByObject(team, playerColor)
    -- Show loading message
    Player[playerColor].broadcast("Loading " .. team.name .. "...", {0.2, 0.8, 1})
    
    -- Fetch and spawn the team box
    WebRequest.get(team.url, function(request)
        if request.is_error then
            Player[playerColor].broadcast("Failed to load " .. team.name .. ": " .. request.error, {1, 0, 0})
            return
        end
        
        local success, decoded = pcall(function() return JSON.decode(request.text) end)
        if not success or not decoded or not decoded.ObjectStates or not decoded.ObjectStates[1] then
            Player[playerColor].broadcast("Failed to parse " .. team.name, {1, 0, 0})
            return
        end
        
        local teamBox = decoded.ObjectStates[1]
        
        -- Spawn just below the spawner token
        local spawnPos = self.getPosition() + Vector(0, 2, -3)
        
        local spawnedObj = spawnObjectJSON({
            json = JSON.encode(teamBox),
            position = spawnPos,
            rotation = {0, 270, 0}  -- 90 degrees to the right
        })
        
        if spawnedObj then
            Player[playerColor].broadcast("✓ Spawned " .. team.name, {0, 1, 0})
        else
            Player[playerColor].broadcast("Failed to spawn " .. team.name, {1, 0, 0})
        end
    end)
end

function spawnTeam(input, playerColor)
    if not input or input == "" then
        Player[playerColor].broadcast("No team selected", {1, 0.5, 0})
        return
    end
    
    local team = nil
    local teamNumber = tonumber(input)
    
    -- Try to match by number first
    if teamNumber and teamsByNumber[teamNumber] then
        team = teamsByNumber[teamNumber]
    else
        -- Try to match by name (case-insensitive, partial match)
        local inputLower = input:lower()
        
        -- First try exact match
        team = teamsByName[inputLower]
        
        -- If no exact match, try partial match
        if not team then
            for _, t in ipairs(allTeams) do
                if t.name:lower():find(inputLower, 1, true) or t.team:lower():find(inputLower, 1, true) then
                    team = t
                    break
                end
            end
        end
    end
    
    if not team then
        Player[playerColor].broadcast("Team not found: " .. input, {1, 0, 0})
        return
    end
    
    -- Show loading message
    Player[playerColor].broadcast("Loading " .. team.name .. "...", {0.2, 0.8, 1})
    
    -- Fetch and spawn the team box
    WebRequest.get(team.url, function(request)
        if request.is_error then
            Player[playerColor].broadcast("Failed to load " .. team.name .. ": " .. request.error, {1, 0, 0})
            return
        end
        
        local success, decoded = pcall(function() return JSON.decode(request.text) end)
        if not success or not decoded or not decoded.ObjectStates or not decoded.ObjectStates[1] then
            Player[playerColor].broadcast("Failed to parse " .. team.name, {1, 0, 0})
            return
        end
        
        local teamBox = decoded.ObjectStates[1]
        
        -- Spawn just below the spawner token
        local spawnPos = self.getPosition() + Vector(0, 2, -3)
        
        local spawnedObj = spawnObjectJSON({
            json = JSON.encode(teamBox),
            position = spawnPos,
            rotation = {0, 270, 0}  -- 90 degrees to the right
        })
        
        if spawnedObj then
            Player[playerColor].broadcast("✓ Spawned " .. team.name, {0, 1, 0})
        else
            Player[playerColor].broadcast("Failed to spawn " .. team.name, {1, 0, 0})
        end
    end)
end

-- Chat command support: /spawn <team>
function onChat(message, player)
    if message:sub(1, 7):lower() == "/spawn " then
        local teamInput = message:sub(8)
        spawnTeam(teamInput, player.color)
        return false  -- Suppress the chat message
    end
end
