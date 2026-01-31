-- Kill Team Spawner Token
-- Click button to spawn any Kill Team card box

local TTS_BOXES_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/tts-card-boxes.json"
local TTS_METADATA_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/tts-metadata.json"
local allTeams = {}
local teamMetadata = {}

function onLoad()
    print("[Spawner] Initializing Kill Team Spawner")
    self.setName("Kill Team Spawner")
    self.setDescription("Loading teams from GitHub...")
    
    -- Create spawn button (positioned above the team list)
    self.createButton({
        label = "Spawn Team",
        click_function = "onSpawnClick",
        function_owner = self,
        position = {0, 0.2, -1.3},
        rotation = {0, 0, 0},
        height = 220,
        width = 800,
        font_size = 120,
        color = {0, 0.7, 0.2},
        font_color = {1, 1, 1}
    })
    
    -- Load team list and metadata from GitHub
    loadTeamList()
end

function loadTeamList()
    print("[Spawner] Fetching team list from GitHub...")
    
    -- First load metadata for timestamps
    WebRequest.get(TTS_METADATA_URL, function(metaRequest)
        if not metaRequest.is_error then
            local success, metaData = pcall(function() 
                return JSON.decode(metaRequest.text) 
            end)
            
            if success and metaData then
                -- Index metadata by team slug
                for _, meta in ipairs(metaData) do
                    teamMetadata[meta.team] = meta
                end
                print("[Spawner] Loaded metadata for " .. #metaData .. " teams")
            end
        end
        
        -- Then load the team list
        WebRequest.get(TTS_BOXES_URL, function(request)
            if request.is_error then
                print("[Spawner] Error: " .. request.error)
                broadcastToAll("Failed to load team list", {1, 0, 0})
                return
            end
            
            local success, data = pcall(function() 
                return JSON.decode(request.text) 
            end)
            
            if not success or not data then
                print("[Spawner] Error: Failed to parse JSON")
                broadcastToAll("Failed to parse team list", {1, 0, 0})
                return
            end
            
            -- Sort teams alphabetically
            table.sort(data, function(a, b)
                return a.name:lower() < b.name:lower()
            end)
            
            allTeams = data
            
            print("[Spawner] Loaded " .. #allTeams .. " teams")
            updateDescription()
        end)
    end)
end

function updateDescription()
    local desc = "🎯 KILL TEAM SPAWNER 🎯\n\n"
    desc = desc .. "All " .. #allTeams .. " teams shown above\n"
    desc = desc .. "Click button and enter:\n"
    desc = desc .. "  • Team number (1-" .. #allTeams .. ")\n"
    desc = desc .. "  • Partial name ('kas', 'death')"
    
    self.setDescription(desc)
end

function onSpawnClick(obj, playerColor)
    if #allTeams == 0 then
        Player[playerColor].broadcast("Team list not loaded yet", {1, 0.5, 0})
        return
    end
    
    Player[playerColor].showInputDialog(
        "Enter team number or partial name\n━━━━━━━━━━━━━━━━━━━━━━━\nExamples: 12  OR  'kasrkin'  OR  'death'\n\nClick 'Show List' button to see all teams",
        "",
        function(input)
            if not input or input == "" then
                return
            end
            handleTeamInput(input, playerColor)
        end
    )
end

function handleTeamInput(input, playerColor)
    local team = nil
    local teamNumber = tonumber(input)
    
    -- Try number first
    if teamNumber and teamNumber >= 1 and teamNumber <= #allTeams then
        team = allTeams[teamNumber]
    else
        -- Try name matching (case-insensitive, partial)
        local inputLower = input:lower()
        local matches = {}
        
        for _, t in ipairs(allTeams) do
            if t.name:lower():find(inputLower, 1, true) then
                table.insert(matches, t)
            end
        end
        
        if #matches == 1 then
            team = matches[1]
        elseif #matches > 1 then
            -- Multiple matches - show them
            Player[playerColor].broadcast("━━━━━━━━━━━━━━━━━━━━━━━━━━━", {1, 0.8, 0.3})
            Player[playerColor].broadcast("Multiple matches for '" .. input .. "':", {1, 0.8, 0.3})
            for _, t in ipairs(matches) do
                -- Find the team number
                for j, allTeam in ipairs(allTeams) do
                    if allTeam.name == t.name then
                        Player[playerColor].broadcast("  " .. j .. ". " .. t.name, {1, 1, 1})
                        break
                    end
                end
            end
            Player[playerColor].broadcast("━━━━━━━━━━━━━━━━━━━━━━━━━━━", {1, 0.8, 0.3})
            Player[playerColor].broadcast("Please enter the team number", {1, 0.8, 0.3})
            return
        end
    end
    
    if not team then
        Player[playerColor].broadcast("❌ No match for: '" .. input .. "'", {1, 0.3, 0.3})
        Player[playerColor].broadcast("Try a team number (1-" .. #allTeams .. ") or partial name", {1, 0.5, 0.5})
        return
    end
    
    spawnTeam(team, playerColor)
end

function spawnTeam(team, playerColor)
    Player[playerColor].broadcast("Loading " .. team.name .. "...", {0.2, 0.8, 1})
    
    WebRequest.get(team.url, function(request)
        if request.is_error then
            Player[playerColor].broadcast("Failed to load " .. team.name, {1, 0, 0})
            return
        end
        
        local success, data = pcall(function() 
            return JSON.decode(request.text) 
        end)
        
        if not success or not data or not data.ObjectStates or not data.ObjectStates[1] then
            Player[playerColor].broadcast("Failed to parse " .. team.name, {1, 0, 0})
            return
        end
        
        local boxData = data.ObjectStates[1]
        
        -- Use timestamp from metadata for cache busting (efficient caching)
        -- Use the latest of cards or tokens timestamp
        local cacheBust = ""
        local meta = teamMetadata[team.team]
        if meta then
            local cardsTs = meta.cards_last_modified or ""
            local tokensTs = meta.tokens_last_modified or ""
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
            
            if latestTs ~= "" then
                -- Strip to numbers only for cleaner URLs
                cacheBust = latestTs:gsub("[^%d]", "")
            else
                -- Fallback to current time if no timestamp available
                cacheBust = tostring(os.time())
            end
        else
            -- Fallback to current time if no metadata available
            cacheBust = tostring(os.time())
        end
        
        -- Update bag mesh and texture URLs
        if boxData.CustomMesh then
            if boxData.CustomMesh.MeshURL then
                boxData.CustomMesh.MeshURL = boxData.CustomMesh.MeshURL .. "?v=" .. cacheBust
            end
            if boxData.CustomMesh.DiffuseURL then
                boxData.CustomMesh.DiffuseURL = boxData.CustomMesh.DiffuseURL .. "?v=" .. cacheBust
            end
        end
        
        -- Update all contained objects (cards, decks, tokens)
        if boxData.ContainedObjects then
            for _, obj in ipairs(boxData.ContainedObjects) do
                -- Handle decks
                if obj.CustomDeck then
                    for deckID, deck in pairs(obj.CustomDeck) do
                        if deck.FaceURL then
                            deck.FaceURL = deck.FaceURL .. "?v=" .. cacheBust
                        end
                        if deck.BackURL then
                            deck.BackURL = deck.BackURL .. "?v=" .. cacheBust
                        end
                    end
                end
                
                -- Handle individual cards/tokens
                if obj.CustomImage then
                    if obj.CustomImage.ImageURL then
                        obj.CustomImage.ImageURL = obj.CustomImage.ImageURL .. "?v=" .. cacheBust
                    end
                    if obj.CustomImage.ImageSecondaryURL then
                        obj.CustomImage.ImageSecondaryURL = obj.CustomImage.ImageSecondaryURL .. "?v=" .. cacheBust
                    end
                end
                
                -- Handle custom objects (tokens, etc.)
                if obj.CustomTile and obj.CustomTile.CustomImage then
                    if obj.CustomTile.CustomImage.ImageURL then
                        obj.CustomTile.CustomImage.ImageURL = obj.CustomTile.CustomImage.ImageURL .. "?v=" .. cacheBust
                    end
                end
            end
        end
        
        -- Spawn position: in front of spawner
        local basePos = self.getPosition() + Vector(0, 2, -5)
        local spawnPos = basePos
        local foundClear = false
        
        -- Check if there's already an object at spawn position
        local hitList = Physics.cast({
            origin = basePos,
            direction = {0, 1, 0},
            type = 3,  -- Box cast
            size = {3, 3, 3},
            max_distance = 0
        })
        
        -- If base position is clear, use it
        if #hitList == 0 then
            foundClear = true
        else
            -- Try offsets to the right until we find a clear spot
            for i = 1, 5 do
                local offset = i * 5
                spawnPos = basePos + Vector(offset, 0, 0)
                
                hitList = Physics.cast({
                    origin = spawnPos,
                    direction = {0, 1, 0},
                    type = 3,
                    size = {3, 3, 3},
                    max_distance = 0
                })
                
                if #hitList == 0 then
                    foundClear = true
                    Player[playerColor].broadcast("⚠ Spawning to the side to avoid overlap", {1, 0.8, 0.3})
                    break
                end
            end
        end
        
        -- Only spawn if we found a clear position
        if not foundClear then
            Player[playerColor].broadcast("⚠ Please move existing boxes first - spawn area is blocked", {1, 0.3, 0.3})
            return
        end
        
        local spawnedObj = spawnObjectJSON({
            json = JSON.encode(boxData),
            position = spawnPos,
            rotation = {0, 270, 0}
        })
        
        if spawnedObj then
            Player[playerColor].broadcast("✓ Spawned " .. team.name, {0, 1, 0})
        else
            Player[playerColor].broadcast("Failed to spawn " .. team.name, {1, 0, 0})
        end
    end)
end
