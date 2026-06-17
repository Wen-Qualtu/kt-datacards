-- Kill Team Spawner (clean) — spawns bare {Team}.json directly.
--
-- Reads output/team-urls.json (small index of clean per-team URLs), shows a
-- picker, downloads the chosen team's bare object JSON, hands it straight to
-- spawnObjectJSON. No save-file slicing, no manual URL cache-busting (the
-- generated files already carry ?v= on every asset URL).

local TEAM_URLS_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/team-urls.json"
local allTeams = {}  -- { {slug, name, url}, ... } sorted by name

local function slugToName(slug)
    local out = {}
    for word in string.gmatch(slug, "[^-]+") do
        out[#out + 1] = word:sub(1,1):upper() .. word:sub(2)
    end
    return table.concat(out, " ")
end

function onLoad()
    self.setName("Kill Team Spawner (clean)")
    self.setDescription("Loading teams from GitHub...")
    self.createButton({
        label = "Spawn Team",
        click_function = "onSpawnClick",
        function_owner = self,
        position = {0, 0.2, -1.3},
        rotation = {0, 0, 0},
        height = 220, width = 800, font_size = 120,
        color = {0, 0.7, 0.2}, font_color = {1, 1, 1}
    })
    loadTeamList()
end

function loadTeamList()
    local url = TEAM_URLS_URL .. "?v=" .. tostring(os.time())
    WebRequest.get(url, function(req)
        if req.is_error or (tonumber(req.response_code) or 0) >= 400 then
            broadcastToAll("Failed to load team list: " .. (req.error or ("HTTP " .. tostring(req.response_code))), {1, 0.3, 0.3})
            return
        end
        local ok, data = pcall(function() return JSON.decode(req.text) end)
        if not ok or type(data) ~= "table" then
            broadcastToAll("Failed to parse team list", {1, 0.3, 0.3})
            return
        end
        allTeams = {}
        for slug, entry in pairs(data) do
            if type(entry) == "table" and type(entry.box) == "table" and entry.box.url then
                allTeams[#allTeams + 1] = {
                    slug = slug,
                    name = slugToName(slug),
                    url = entry.box.url
                }
            end
        end
        table.sort(allTeams, function(a, b) return a.name:lower() < b.name:lower() end)
        updateDescription()
        print("[Spawner] Loaded " .. #allTeams .. " teams")
    end)
end

function updateDescription()
    local desc = "KILL TEAM SPAWNER (clean)\n\n"
    desc = desc .. #allTeams .. " teams available\n"
    desc = desc .. "Click button and enter:\n"
    desc = desc .. "  - Team number (1-" .. #allTeams .. ")\n"
    desc = desc .. "  - Partial name ('kas', 'death')"
    self.setDescription(desc)
end

function onSpawnClick(_, playerColor)
    if #allTeams == 0 then
        Player[playerColor].broadcast("Team list not loaded yet", {1, 0.5, 0})
        return
    end
    Player[playerColor].showInputDialog(
        "Enter team number or partial name",
        "",
        function(input)
            if not input or input == "" then return end
            handleTeamInput(input, playerColor)
        end
    )
end

function handleTeamInput(input, playerColor)
    local team
    local n = tonumber(input)
    if n and n >= 1 and n <= #allTeams then
        team = allTeams[n]
    else
        local needle = input:lower()
        local matches = {}
        for _, t in ipairs(allTeams) do
            if t.name:lower():find(needle, 1, true) or t.slug:find(needle, 1, true) then
                matches[#matches + 1] = t
            end
        end
        if #matches == 1 then
            team = matches[1]
        elseif #matches > 1 then
            Player[playerColor].broadcast("Multiple matches for '" .. input .. "':", {1, 0.8, 0.3})
            for _, t in ipairs(matches) do
                for j, all in ipairs(allTeams) do
                    if all.slug == t.slug then
                        Player[playerColor].broadcast("  " .. j .. ". " .. t.name, {1, 1, 1})
                        break
                    end
                end
            end
            return
        end
    end
    if not team then
        Player[playerColor].broadcast("No match for: '" .. input .. "'", {1, 0.3, 0.3})
        return
    end
    spawnTeam(team, playerColor)
end

local function findClearSpot(basePos)
    local hit = Physics.cast({origin = basePos, direction = {0,1,0}, type = 3, size = {3,3,3}, max_distance = 0})
    if #hit == 0 then return basePos, true end
    for i = 1, 5 do
        local p = basePos + Vector(i * 5, 0, 0)
        hit = Physics.cast({origin = p, direction = {0,1,0}, type = 3, size = {3,3,3}, max_distance = 0})
        if #hit == 0 then return p, true end
    end
    return basePos, false
end

function spawnTeam(team, playerColor)
    Player[playerColor].broadcast("Loading " .. team.name .. "...", {0.2, 0.8, 1})
    WebRequest.get(team.url, function(req)
        local code = tonumber(req.response_code) or 0
        if req.is_error or code >= 400 then
            Player[playerColor].broadcast("Failed to load " .. team.name .. ": " .. (req.error ~= "" and req.error or ("HTTP " .. code)), {1, 0.3, 0.3})
            return
        end
        local body = req.text or ""
        local i = 1
        while i <= #body and (body:byte(i) == 32 or body:byte(i) == 9 or body:byte(i) == 10 or body:byte(i) == 13) do
            i = i + 1
        end
        if i > #body or body:byte(i) ~= 123 then  -- '{'
            Player[playerColor].broadcast("Unexpected response format for " .. team.name, {1, 0.3, 0.3})
            return
        end
        local objJson = (i == 1) and body or body:sub(i)

        local basePos = self.getPosition() + Vector(0, 2, -5)
        local spawnPos, clear = findClearSpot(basePos)
        if not clear then
            Player[playerColor].broadcast("Spawn area blocked - move existing boxes first", {1, 0.3, 0.3})
            return
        end

        local spawned = spawnObjectJSON({
            json = objJson,
            position = spawnPos,
            rotation = {0, 270, 0}
        })
        if spawned then
            Player[playerColor].broadcast("Spawned " .. team.name, {0, 1, 0})
        else
            Player[playerColor].broadcast("Failed to spawn " .. team.name, {1, 0, 0})
        end
    end)
end
