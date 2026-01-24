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
    if #allTeams == 0 then
        Player[playerColor].broadcast("Team list not loaded yet, please wait...", {1, 0.5, 0})
        return
    end
    
    -- Group teams by faction using metadata
    local factionGroups = {chaos = {}, imperium = {}, xenos = {}}
    local factionNames = {"Chaos", "Imperium", "Xenos"}
    
    for i, team in ipairs(allTeams) do
        local faction = "xenos" -- default
        
        -- Safely access metadata
        if teamMetadata and team.team and teamMetadata[team.team] then
            if teamMetadata[team.team].faction then
                faction = teamMetadata[team.team].faction:lower()
            end
        end
        
        if factionGroups[faction] then
            table.insert(factionGroups[faction], team)
        end
    end
    
    -- Show faction selection
    Player[playerColor].showOptionsDialog("Select Faction", factionNames, 1, function(factionChoice, playerColorCallback)
        if not factionChoice then return end
        
        local factionKey = factionNames[factionChoice]:lower()
        local factionTeams = factionGroups[factionKey]
        
        if not factionTeams or #factionTeams == 0 then
            Player[playerColorCallback].broadcast("No teams found for " .. factionNames[factionChoice], {1, 0.5, 0})
            return
        end
        
        -- Build team names for this faction
        local teamNames = {}
        for _, team in ipairs(factionTeams) do
            table.insert(teamNames, team.name)
        end
        
        -- Show team selection for chosen faction
        Player[playerColorCallback].showOptionsDialog("Select " .. factionNames[factionChoice] .. " Team", teamNames, 1, function(teamChoice, playerColorCallback2)
            if teamChoice and factionTeams[teamChoice] then
                spawnTeamByObject(factionTeams[teamChoice], playerColorCallback2)
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
