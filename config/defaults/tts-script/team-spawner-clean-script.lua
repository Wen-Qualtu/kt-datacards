-- Kill Team Spawner (clean) — spawns bare {Team}.json directly.
--
-- Reads output/team-urls.json (small index of clean per-team URLs), shows a
-- searchable team menu, downloads the chosen team's bare object JSON, hands it straight to
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
    self.setName("Kill Team Spawner")
    self.setDescription("Loading teams from GitHub...")
    local scale = self.getScale()
    self.createButton({
        label = "Spawn Team",
        click_function = "onSpawnClick",
        function_owner = self,
        position = {0, (self.getBoundsNormalized().size.y * 0.5 + 0.05) / scale.y, -1.2},
        width = 900, height = 320, font_size = 180,
        color = {0.15, 0.45, 0.36}, font_color = {1, 1, 1}
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
    self.setDescription("KILL TEAM SPAWNER\n\n" .. #allTeams .. " teams available.\nClick Spawn Team to pick or search a team.")
end

local COLUMNS = 3
local CELL_WIDTH, CELL_HEIGHT, CELL_SPACING = 290, 36, 6
local PANEL_WIDTH = COLUMNS * CELL_WIDTH + (COLUMNS - 1) * CELL_SPACING + 28
local menuOpen = false

local function xmlEscape(value)
    return tostring(value or ""):gsub("&", "&amp;"):gsub("<", "&lt;")
        :gsub(">", "&gt;"):gsub('"', "&quot;"):gsub("'", "&apos;")
end

local function matches(team, needle)
    return needle == "" or team.name:lower():find(needle, 1, true) ~= nil or team.slug:find(needle, 1, true) ~= nil
end

local function closeMenu()
    menuOpen = false
    self.UI.setXml("")
end

local function openMenu()
    menuOpen = true
    local buttons = {}
    for index, team in ipairs(allTeams) do
        buttons[#buttons + 1] = string.format('<Button id="team_%d" onClick="spawnerChooseTeam" fontSize="17" '
            .. 'colors="#34454A|#56686D|#293336|#333333" textColor="#FFFFFF">%s</Button>', index, xmlEscape(team.name))
    end
    local rows = math.ceil(#allTeams / COLUMNS)
    local gridHeight = rows * CELL_HEIGHT + math.max(0, rows - 1) * CELL_SPACING
    local panelHeight = 28 + 48 + 8 + 40 + 8 + gridHeight
    local scale = self.getScale()
    local halfDepth = self.getBoundsNormalized().size.z * 0.5
    local scaleX, scaleY = 0.8 / scale.x, 0.8 / scale.z
    local position = halfDepth / scale.z * 100 + panelHeight * scaleY * 0.5
    self.UI.setXml(string.format([[
<Panel id="spawnerPanel" width="%d" height="%d" position="0 %.3f -80" rotation="0 0 180" scale="%.4f %.4f 1"
       color="#171D1FF2" padding="14 14 14 14">
  <VerticalLayout spacing="8" childForceExpandWidth="true" childForceExpandHeight="false">
    <Text fontSize="25" fontStyle="Bold" color="#FFFFFF" alignment="UpperCenter" preferredHeight="48">Spawn a Kill Team</Text>
    <HorizontalLayout spacing="8" preferredHeight="40" flexibleHeight="0" childForceExpandWidth="false" childForceExpandHeight="false">
      <InputField id="spawner_search" onValueChanged="spawnerSearch" onSubmit="spawnerSubmit" placeholder="Search teams..."
                  flexibleWidth="1" preferredHeight="40" fontSize="18"></InputField>
      <Button id="spawner_close" onClick="spawnerClose" preferredWidth="120" flexibleWidth="0" preferredHeight="40" fontSize="17"
              colors="#34454A|#56686D|#293336|#333333" textColor="#FFFFFF">Close</Button>
    </HorizontalLayout>
    <GridLayout cellSize="%d %d" spacing="%d %d" constraint="FixedColumnCount" constraintCount="%d"
                preferredHeight="%d" flexibleHeight="0">%s</GridLayout>
  </VerticalLayout>
</Panel>]], PANEL_WIDTH, panelHeight, position, scaleX, scaleY,
        CELL_WIDTH, CELL_HEIGHT, CELL_SPACING, CELL_SPACING, COLUMNS, gridHeight, table.concat(buttons)))
end

function onSpawnClick(_, playerColor)
    if menuOpen then closeMenu(); return end
    if #allTeams == 0 then
        Player[playerColor].broadcast("Team list not loaded yet; trying again...", {1, 0.5, 0})
        loadTeamList()
        return
    end
    openMenu()
end

function spawnerClose()
    closeMenu()
end

function spawnerSearch(_, value)
    local needle = (value or ""):lower()
    for index, team in ipairs(allTeams) do
        self.UI.setAttribute("team_" .. index, "active", tostring(matches(team, needle)))
    end
end

function spawnerSubmit(player, value)
    local needle = (value or ""):lower()
    local found = {}
    for _, team in ipairs(allTeams) do
        if matches(team, needle) then found[#found + 1] = team end
    end
    if #found == 1 then
        closeMenu()
        spawnTeam(found[1], player.color)
    else
        player.broadcast(#found == 0 and "No team matches '" .. (value or "") .. "'."
            or #found .. " teams match; type more or click one.", {1, 0.8, 0.3})
    end
end

function spawnerChooseTeam(player, _, id)
    local team = allTeams[tonumber(id:match("^team_(%d+)$"))]
    if not team then return end
    closeMenu()
    spawnTeam(team, player.color)
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
