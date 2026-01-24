-- Kill Team Spawner Token
-- Click button to spawn any Kill Team card box

local TTS_BOXES_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/tts-card-boxes.json"
local allTeams = {}
local teamsByNumber = {}
local teamsByName = {}

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
    
    -- Load team list from GitHub
    loadTeamList()
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
    
    -- Build title with team list in 3 columns
    local title = "SPAWN KILL TEAM - Select by number or name\n\n"
    
    -- Split teams into 3 columns of ~15 teams each
    local col1, col2, col3 = "", "", ""
    for i, team in ipairs(allTeams) do
        local line = string.format("%2d.%-24s", i, team.name)
        if i <= 15 then
            col1 = col1 .. line .. "\n"
        elseif i <= 30 then
            col2 = col2 .. line .. "\n"
        else
            col3 = col3 .. line .. "\n"
        end
    end
    
    -- Combine columns side by side
    local col1Lines = {}
    local col2Lines = {}
    local col3Lines = {}
    
    for line in col1:gmatch("[^\n]+") do table.insert(col1Lines, line) end
    for line in col2:gmatch("[^\n]+") do table.insert(col2Lines, line) end
    for line in col3:gmatch("[^\n]+") do table.insert(col3Lines, line) end
    
    for i = 1, math.max(#col1Lines, #col2Lines, #col3Lines) do
        local c1 = col1Lines[i] or string.rep(" ", 27)
        local c2 = col2Lines[i] or string.rep(" ", 27)
        local c3 = col3Lines[i] or ""
        title = title .. c1 .. "  " .. c2 .. "  " .. c3 .. "\n"
    end
    
    title = title .. "\nType number (1-44) or team name. Chat: /spawn <team>"
    
    Player[playerColor].showInputDialog(title, "", function(input, color)
        spawnTeam(input, color)
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
