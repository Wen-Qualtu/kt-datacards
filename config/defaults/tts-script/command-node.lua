function selectedLoadoutWeapons(data, choices, selectedSet)
    local selection = data.selection
    if not selection or not selection.groups or #selection.groups == 0 then
        return data.weapons or {}
    end

    local activeGroups = {}
    if selection.exclusive_sets and #selection.exclusive_sets > 0 then
        local set = selection.exclusive_sets[selectedSet or 1]
        if not set then return nil, "Invalid loadout alternative." end
        for _, groupIndex in ipairs(set) do
            if type(groupIndex) ~= "number" or not selection.groups[groupIndex + 1] then
                return nil, "Invalid loadout group."
            end
            activeGroups[groupIndex + 1] = true
        end
    else
        for groupIndex in ipairs(selection.groups) do
            activeGroups[groupIndex] = true
        end
    end

    local selected = {}
    for _, weaponIndex in ipairs(selection.fixed or {}) do
        if type(weaponIndex) ~= "number" or not data.weapons or not data.weapons[weaponIndex + 1] then
            return nil, "Invalid fixed weapon."
        end
        selected[weaponIndex + 1] = true
    end
    for groupIndex, group in ipairs(selection.groups) do
        if activeGroups[groupIndex] then
            local option = group[choices[groupIndex] or 1]
            if not option then return nil, "Invalid loadout choice." end
            for _, weaponIndex in ipairs(option.weapons or {}) do
                if type(weaponIndex) ~= "number" or not data.weapons or not data.weapons[weaponIndex + 1] then
                    return nil, "Invalid loadout weapon."
                end
                selected[weaponIndex + 1] = true
            end
        end
    end

    local weapons = {}
    for weaponIndex, weapon in ipairs(data.weapons or {}) do
        if selected[weaponIndex] then weapons[#weapons + 1] = weapon end
    end
    return weapons
end

local NORMALIZED_CHARACTERS = {
    ["\226\128\153"] = "'", ["\226\128\152"] = "'",
    ["\226\128\156"] = '"', ["\226\128\157"] = '"',
    ["\226\128\144"] = "-", ["\226\128\145"] = "-", ["\226\128\146"] = "-",
    ["\226\128\147"] = "-", ["\226\128\148"] = "-",
    ["\226\128\179"] = '"', ["\226\128\178"] = "'",
    ["\195\162"] = "a", ["\195\180"] = "o",
}

local function cleanText(value, normalize)
    if type(value) ~= "string" then return value end
    if normalize then
        value = value:gsub("[\007\008]", "")
        for character, replacement in pairs(NORMALIZED_CHARACTERS) do
            value = value:gsub(character, replacement)
        end
        value = value:gsub("^%s+", ""):gsub("%s+$", "")
    end
    local parts = {}
    for index = 1, #value do
        local character = value:sub(index, index)
        if character == "&" and value:sub(index - 1, index - 1) ~= "&"
            and value:sub(index + 1, index + 1) ~= "&" then
            character = "and"
        end
        parts[#parts + 1] = character
    end
    return table.concat(parts)
end

function commandNodeModelData(operative, teamRules)
    local node = operative.node
    if type(node) ~= "table" or type(node.weapon_types) ~= "table" then
        return nil, "Team data needs node fields. Regenerate the team data."
    end
    local data = {
        name = cleanText(operative.name or ""),
        stats = {
            APL = operative.apl or 2,
            Move = tonumber(tostring(operative.movement or "6"):match("%d+")) or 6,
            Save = tonumber(tostring(operative.save or "5+"):match("%d+")) or 5,
            Wounds = operative.wounds or 1,
            Base = operative.base_size,
        },
        keywords = {"Operative"}, weapons = {}, abilities = {}, actions = {},
        weapon_rules = {}, selection = node.selection,
    }
    for _, name in ipairs(node.weapon_rule_names or {}) do
        if type(teamRules) ~= "table" or teamRules[name] == nil then
            return nil, "Missing weapon rule " .. tostring(name) .. "."
        end
        data.weapon_rules[name] = teamRules[name]
    end
    for _, keyword in ipairs(operative.keywords or {}) do
        data.keywords[#data.keywords + 1] = cleanText(keyword, true)
    end
    for index, weapon in ipairs(operative.weapons or {}) do
        local kind = node.weapon_types[index]
        if kind ~= "melee" and kind ~= "ranged" then
            return nil, "Invalid weapon classification for " .. data.name .. "."
        end
        local name = cleanText(weapon.name or "")
        local prefix = kind == "melee" and "[F4641D]M[-] " or "[1E87FF]R[-] "
        data.weapons[#data.weapons + 1] = {
            name = prefix .. name, plain_name = name,
            stats = {ATK = cleanText(weapon.attacks or ""), HIT = cleanText(weapon.hit or ""),
                DMG = cleanText(weapon.damage or ""), WR = cleanText(weapon.special_rules or "")},
        }
    end
    for _, ability in ipairs(operative.passive_abilities or {}) do
        local name = cleanText(ability.name or "", true)
        if name ~= "" then
            data.abilities[#data.abilities + 1] = {name = name, text = cleanText(ability.description or "", true)}
        end
    end
    for _, action in ipairs(operative.unique_actions or {}) do
        local name = cleanText(action.name or "", true)
        if name ~= "" then
            data.actions[#data.actions + 1] = {name = name, text = cleanText(action.description or "", true)}
        end
    end
    return data
end

local REPO_BASE_URL = NODE_REPO_BASE_URL or "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"
local TEAM_INDEX_URL = REPO_BASE_URL .. "/output/team-urls.json"
local NODE_LOADER_URL = REPO_BASE_URL .. "/output/_generic-tts-objects/command-node-loader.lua"
local teams = {}
local operatives = {}
local counts = {}
local slots = {}
local sessionColor = nil
local sessionVersion = 0
local currentTeam = nil
local applying = false
local building = false
local selectedSlot = 1
local activeHelper = nil
local loaderScript = nil
local panelPage = 1
local panelRender = nil
local showSetup
local PANEL_MAX_HEIGHT = 550

local MODEL_TYPES = {
    Custom_Model = true,
    Figurine_Custom = true,
    Custom_Assetbundle = true,
    Figurine = true,
}

local APPLY_ADAPTER = [[
function ktCommandNodeApply(params)
    if not params or not params.model or not params.data then return nil end
    local mounted = false
    for _, keyword in ipairs(params.data.keywords or {}) do
        if tostring(keyword):upper() == "MOUNTED" then mounted = true end
    end
    local movement = mounted and SPRINT_TOOL_CODE or MOVE_TOOL_CODE
    if type(movement) ~= "string" or movement == "" then
        error("Movement tool missing from the command-node loader.")
    end
    local tag = mounted and "KT_SPRINT_TOOL_V1" or "KT_MOVE_TOOL_V1"
    local modelScript = KTUI_MODELSCRIPT .. "\n\n-- START " .. tag .. " --\n"
        .. movement .. "\n-- END " .. tag .. " --\n"
    params.data.description = rebuildDescription(params.data)
    local state = {}
    local raw = params.model.script_state
    if raw and raw ~= "" then
        local ok, decoded = pcall(function() return JSON.decode(raw) end)
        if ok and type(decoded) == "table" then state = decoded end
    end
    local rotation = params.model.getRotation()
    local front = (params.heading - rotation.y) % 360
    state.kt_front = front
    state.uiAngle = (-front) % 360
    state.uiPositionIndex = 1
    state.kt_node_ui = true
    params.model.script_state = JSON.encode(state)
    params.model.clearButtons()
    params.model.clearInputs()
    params.model.UI.setXml("")
    local changes = diffAndApply(params.model, params.data, params.playerColor, true, modelScript)
    return {applied = true, changes = #changes}
end
]]

local function xmlEscape(value)
    return tostring(value or ""):gsub("&", "&amp;"):gsub("<", "&lt;")
        :gsub(">", "&gt;"):gsub('"', "&quot;"):gsub("'", "&apos;")
end

local function displayName(slug)
    return (slug:gsub("-", " "):gsub("%f[%a]%l", string.upper))
end

local function slotLabel(index, name)
    local lines = {}
    local line = index .. "."
    local longest = #line
    for word in name:gmatch("%S+") do
        if #line + #word + 1 > 16 then
            lines[#lines + 1] = line
            line = word
        else
            line = line .. " " .. word
        end
        longest = math.max(longest, #line)
    end
    lines[#lines + 1] = line
    return table.concat(lines, "\n"), math.min(80, math.floor(1000 / longest))
end

local function notify(color, message, tint)
    broadcastToColor(message, color, tint or {1, 0.8, 0.3})
end

local function requestText(url, callback)
    WebRequest.get(url, function(response)
        local status = tonumber(response.response_code) or 0
        if response.is_error or status >= 400 then
            local reason = response.error
            if not reason or reason == "" then reason = "HTTP " .. tostring(status) end
            callback(nil, "Download failed: " .. tostring(reason))
        elseif type(response.text) ~= "string" or response.text == "" then
            callback(nil, "The downloaded response is empty.")
        else
            callback(response.text)
        end
    end)
end

local function requestJson(url, callback)
    requestText(url, function(text, errorMessage)
        if not text then callback(nil, errorMessage); return end
        local ok, data = pcall(function() return JSON.decode(text) end)
        if not ok or type(data) ~= "table" then
            callback(nil, "The downloaded response is not valid JSON.")
            return
        end
        callback(data)
    end)
end

local function compatibleLoader(script)
    if type(script) ~= "string" or not script:find("function rebuildDescription", 1, true)
        or not script:find("KTUI_MODELSCRIPT", 1, true) then return false end
    local signature = script:match("function%s+diffAndApply%s*(%b())")
    return signature and signature:find("replaceScript", 1, true) ~= nil
        and signature:find("modelScript", 1, true) ~= nil
end

local function panel(title, rows, footer, rowHeight, rowGroups)
    rowHeight = rowHeight or 34
    local spacing = 6
    local fixedHeight = 28 + 40 + 42 + spacing
    local navigationHeight = 28 + spacing
    local rowsPerPage = math.max(1, #rows)
    if fixedHeight + #rows * (rowHeight + spacing) > PANEL_MAX_HEIGHT then
        rowsPerPage = math.max(1, math.floor(
            (PANEL_MAX_HEIGHT - fixedHeight - navigationHeight) / (rowHeight + spacing)))
    end
    local pages = {{}}
    local rowIndex = 1
    while rowIndex <= #rows do
        local count = rowGroups and rowGroups[rowIndex] or 1
        local page = pages[#pages]
        if count <= rowsPerPage and #page > 0 and #page + count > rowsPerPage then
            page = {}
            pages[#pages + 1] = page
        end
        for offset = 0, count - 1 do
            if #page == rowsPerPage then
                page = {}
                pages[#pages + 1] = page
            end
            page[#page + 1] = rows[rowIndex + offset]
        end
        rowIndex = rowIndex + count
    end
    local pageCount = #pages
    panelPage = math.max(1, math.min(panelPage, pageCount))
    local visibleRows = pages[panelPage]
    local navigation = ""
    if pageCount > 1 then
        navigation = string.format([[
        <HorizontalLayout spacing="6" minHeight="28" preferredHeight="28" flexibleHeight="0" childForceExpandHeight="false" childForceExpandWidth="false" childAlignment="MiddleCenter">
            <Button id="page_prev" onClick="commandNodePage" tooltip="Previous page" preferredWidth="36" flexibleWidth="0" minHeight="28" preferredHeight="28" flexibleHeight="0" fontSize="16" colors="#34454A|#56686D|#293336|#333333" textColor="#FFFFFF" interactable="%s">&lt;</Button>
            <Text preferredWidth="80" flexibleWidth="0" preferredHeight="28" flexibleHeight="0" fontSize="14" color="#FFFFFF">%d / %d</Text>
            <Button id="page_next" onClick="commandNodePage" tooltip="Next page" preferredWidth="36" flexibleWidth="0" minHeight="28" preferredHeight="28" flexibleHeight="0" fontSize="16" colors="#34454A|#56686D|#293336|#333333" textColor="#FFFFFF" interactable="%s">&gt;</Button>
        </HorizontalLayout>]], tostring(panelPage > 1), panelPage, pageCount, tostring(panelPage < pageCount))
    end
    local nodeScale = self.getScale()
    local halfDepth = self.getBoundsNormalized().size.z * 0.5
    local panelHeight = fixedHeight + #visibleRows * (rowHeight + spacing)
        + (pageCount > 1 and navigationHeight or 0)
    local panelScale = 0.8
    local panelPosition = halfDepth / nodeScale.z * 100 + panelHeight * panelScale * 0.5
    local xml = string.format([[
<Panel id="nodePanel" width="650" height="%d" position="0 %.3f -80" rotation="0 0 180" scale="%.2f %.2f 1"
       color="#171D1FF2" padding="14 14 14 14">
  <VerticalLayout spacing="6" childForceExpandWidth="true" childForceExpandHeight="false">
    <Text fontSize="25" fontStyle="Bold" color="#FFFFFF" preferredHeight="40">%s</Text>
    %s
    %s
        <HorizontalLayout spacing="6" preferredHeight="42" flexibleHeight="0" childForceExpandHeight="false">%s</HorizontalLayout>
  </VerticalLayout>
</Panel>]], panelHeight, panelPosition, panelScale, panelScale,
        xmlEscape(title), table.concat(visibleRows), navigation, footer)
    self.UI.setXml(xml)
end

local function button(id, action, label, tint)
    return string.format('<Button id="%s" onClick="%s" minHeight="34" preferredHeight="34" flexibleHeight="0" fontSize="17" '
        .. 'colors="%s|#56686D|#293336|#333333" textColor="#FFFFFF">%s</Button>',
        id, action, tint or "#34454A", xmlEscape(label))
end

local function showTeams()
    panelRender = showTeams
    local rows = {}
    for index, team in ipairs(teams) do
        rows[#rows + 1] = button("team_" .. index, "commandNodeChooseTeam", team.name)
    end
    panel("Choose a team", rows, button("cancel", "commandNodeCancel", "Cancel"))
end

local function showRoster()
    panelRender = showRoster
    local rows = {}
    for index, operative in ipairs(operatives) do
        rows[#rows + 1] = string.format(
            '<HorizontalLayout preferredHeight="42" flexibleHeight="0" spacing="4" childForceExpandWidth="false" childForceExpandHeight="false">'
            .. '<Text preferredWidth="310" flexibleWidth="0" fontSize="16" color="#FFFFFF" alignment="MiddleLeft" horizontalOverflow="Truncate">%s</Text>'
            .. '<Button id="minus_%d" onClick="commandNodeChangeCount" preferredWidth="58" flexibleWidth="0" preferredHeight="36" fontSize="20">-</Button>'
            .. '<Text preferredWidth="48" flexibleWidth="0" fontSize="16" color="#FFFFFF">%d</Text>'
            .. '<Button id="plus_%d" onClick="commandNodeChangeCount" preferredWidth="58" flexibleWidth="0" preferredHeight="36" fontSize="20">+</Button>'
            .. '</HorizontalLayout>',
            xmlEscape(operative.name), index, counts[index] or 0, index)
    end
    local supplies = button("supplies", "commandNodeSpawnSupplies", "Tokens + dice")
    if currentTeam.suppliesBusy or currentTeam.suppliesSpawned then
        supplies = button("supplies", "commandNodeSpawnSupplies",
            currentTeam.suppliesBusy and "Spawning..." or "Spawned")
        supplies = supplies:gsub('onClick=', 'interactable="false" onClick=', 1)
    end
    panel(currentTeam.name, rows,
        button("back", "commandNodeBackToTeams", "Teams")
        .. (currentTeam.useTokens ~= false and supplies or "")
        .. button("next", "commandNodeSetup", "Next", "#237A60")
        .. button("cancel", "commandNodeCancel", "Cancel"), 42)
end

local function isSessionPlayer(player)
    return player and player.color == sessionColor
end

showSetup = function()
    panelRender = showSetup
    local rows = {
        '<Toggle id="setup_tokens" onValueChanged="commandNodeSetupToggle" preferredHeight="34" fontSize="17" textColor="#FFFFFF" isOn="'
            .. tostring(currentTeam.useTokens ~= false) .. '">Team tokens + dice</Toggle>',
    }
    if currentTeam.useTokens ~= false then
        local label = currentTeam.suppliesBusy and "Spawning..." or (currentTeam.suppliesSpawned and "Spawned" or "Spawn tokens + dice")
        local control = button("setup_supplies", "commandNodeSpawnSupplies", label)
        if currentTeam.suppliesBusy or currentTeam.suppliesSpawned then
            control = control:gsub('onClick=', 'interactable="false" onClick=', 1)
        end
        rows[#rows + 1] = control
    end
    if currentTeam.counterRule then
        rows[#rows + 1] = '<Toggle id="setup_rules" onValueChanged="commandNodeSetupToggle" preferredHeight="34" fontSize="17" textColor="#FFFFFF" isOn="'
            .. tostring(currentTeam.useSpecialRules ~= false) .. '">Special rules: '
            .. xmlEscape(currentTeam.counterRule.name) .. '</Toggle>'
    end
    panel(currentTeam.name .. " setup", rows,
        button("setup_back", "commandNodeSetupBack", "Back")
        .. button("setup_create", "commandNodeCreateSlots", "Create slots", "#237A60")
        .. button("cancel", "commandNodeCancel", "Cancel"))
end

function commandNodeSetupToggle(player, value, id)
    if not isSessionPlayer(player) or panelRender ~= showSetup then return end
    local enabled = value == "True" or value == "true" or value == true
    if id == "setup_tokens" then currentTeam.useTokens = enabled end
    if id == "setup_rules" then currentTeam.useSpecialRules = enabled end
    showSetup()
end

function commandNodeSetupBack(player)
    if not isSessionPlayer(player) then return end
    panelPage = 1
    showRoster()
end

function commandNodeSetup(player)
    if not isSessionPlayer(player) or applying or building or panelRender ~= showRoster then return end
    local version = sessionVersion
    local function loaded(script, errorMessage)
        if version ~= sessionVersion then return end
        local metadata = type(script) == "string" and script:match("NODE_COUNTER_SETUP%s*=%s*%[====%[(.-)%]====%]")
        local ok, rules = pcall(function() return metadata and JSON.decode(metadata) end)
        if not compatibleLoader(script) or not ok or type(rules) ~= "table" then
            notify(sessionColor, errorMessage or "Published loader needs the special-rule setup update.", {1, 0.3, 0.3})
            showRoster()
            return
        end
        loaderScript = script
        currentTeam.counterRule = rules[currentTeam.slug]
        panelPage = 1
        showSetup()
    end
    if loaderScript then loaded(loaderScript); return end
    panel("Loading team setup...", {}, button("cancel", "commandNodeCancel", "Cancel"))
    requestText(NODE_LOADER_URL .. "?v=" .. tostring(os.time()), loaded)
end

function commandNodePage(player, _, id)
    if not isSessionPlayer(player) or not panelRender then return end
    if id == "page_prev" then panelPage = panelPage - 1 end
    if id == "page_next" then panelPage = panelPage + 1 end
    panelRender()
end

local function setStartVisible(visible)
    self.editButton({index = 0, label = visible and "New team" or "",
        width = visible and 900 or 0, height = visible and 320 or 0})
end

function onLoad()
    self.setName("Kill Team Command Node")
    local scale = self.getScale()
    local arrowHeight = (self.getBoundsNormalized().size.y * 0.5 + 0.05) / scale.y
    self.setVectorLines({{
        points = {
            {0, arrowHeight, -0.35 / scale.z},
            {0, arrowHeight, 0.45 / scale.z},
            {-0.18 / scale.x, arrowHeight, 0.15 / scale.z},
            {0, arrowHeight, 0.45 / scale.z},
            {0.18 / scale.x, arrowHeight, 0.15 / scale.z},
        },
        color = {0.85, 1, 0.9}, thickness = 0.04,
    }})
    for _, object in ipairs(getObjectsWithTag("KTCommandNodeSlot-" .. self.getGUID())) do
        object.destruct()
    end
    self.createButton({label = "New team", click_function = "commandNodeStart", function_owner = self,
        position = {0, arrowHeight, -1.2}, width = 900, height = 320, font_size = 180,
        color = {0.15, 0.45, 0.36}, font_color = {1, 1, 1}})
end

function commandNodeStart(_, playerColor)
    if sessionColor then
        notify(playerColor, "A setup is already in progress.")
        return
    end
    sessionColor = playerColor
    setStartVisible(false)
    sessionVersion = sessionVersion + 1
    loaderScript = nil
    local version = sessionVersion
    panel("Loading teams...", {}, button("cancel", "commandNodeCancel", "Cancel"))
    requestJson(TEAM_INDEX_URL .. "?v=" .. tostring(os.time()), function(index, errorMessage)
        if version ~= sessionVersion then return end
        if not index then
            sessionColor = nil
            self.UI.setXml("")
            setStartVisible(true)
            notify(playerColor, errorMessage, {1, 0.3, 0.3})
            return
        end
        teams = {}
        for slug, entry in pairs(index) do
            if type(slug) == "string" and slug:match("^[a-z0-9][a-z0-9%-]*$")
                and type(entry) == "table" and type(entry.team_url) == "string" then
                teams[#teams + 1] = {name = displayName(slug), slug = slug}
            end
        end
        table.sort(teams, function(left, right) return left.name:lower() < right.name:lower() end)
        if #teams == 0 then
            sessionColor = nil
            self.UI.setXml("")
            setStartVisible(true)
            notify(playerColor, "No teams are available.", {1, 0.3, 0.3})
            return
        end
        panelPage = 1
        showTeams()
    end)
end

function commandNodeChooseTeam(player, _, id)
    if not isSessionPlayer(player) then return end
    local index = tonumber(id:match("^team_(%d+)$"))
    local team = index and teams[index]
    if not team then return end
    sessionVersion = sessionVersion + 1
    local version = sessionVersion
    panel("Loading " .. team.name .. "...", {}, button("cancel", "commandNodeCancel", "Cancel"))
    local teamBase = REPO_BASE_URL .. "/output/" .. team.slug
    local metadataUrl = teamBase .. "/" .. team.slug .. "-object-urls.json?v=" .. tostring(os.time())
    requestJson(metadataUrl, function(metadata, errorMessage)
        if version ~= sessionVersion then return end
        if not metadata then
            notify(sessionColor, errorMessage, {1, 0.3, 0.3})
            showTeams()
            return
        end
        if metadata.team ~= team.slug or type(metadata.team_data) ~= "table"
            or type(metadata.team_data.url) ~= "string" or metadata.team_data.url == "" then
            notify(sessionColor, "Team data is not published for " .. team.name .. ".", {1, 0.3, 0.3})
            showTeams()
            return
        end
        local hash = metadata.team_data.hash
        local dataVersion = type(hash) == "string" and hash:match("^[a-fA-F0-9]+$") and hash or tostring(os.time())
        local dataUrl = teamBase .. "/data/" .. team.slug .. "-team-data.json?v=" .. dataVersion
        requestJson(dataUrl, function(payload, dataError)
            if version ~= sessionVersion then return end
            if not payload then
                notify(sessionColor, dataError, {1, 0.3, 0.3})
                showTeams()
                return
            end
            if payload.team ~= team.slug or type(payload.datacards) ~= "table" or #payload.datacards == 0 then
                notify(sessionColor, "Invalid operative data for " .. team.name .. ".", {1, 0.3, 0.3})
                showTeams()
                return
            end
            local cards = {}
            for _, operative in ipairs(payload.datacards) do
                local data, conversionError = commandNodeModelData(operative, payload.node_weapon_rules)
                if not data then
                    notify(sessionColor, conversionError, {1, 0.3, 0.3})
                    showTeams()
                    return
                end
                cards[#cards + 1] = {name = data.name, data = data}
            end
            table.sort(cards, function(left, right) return left.name:lower() < right.name:lower() end)
            operatives = cards
            currentTeam = team
            currentTeam.hasTokenBag = false
            for _, object in ipairs(metadata.objects or {}) do
                if object.type == "token-bag" then currentTeam.hasTokenBag = true end
            end
            counts = {}
            panelPage = 1
            showRoster()
        end)
    end)
end

function commandNodeSpawnSupplies(player)
    if not isSessionPlayer(player) or not currentTeam or applying or building
        or (panelRender ~= showRoster and panelRender ~= showSetup) then return end
    local team = currentTeam
    if team.suppliesBusy or team.suppliesSpawned then return end
    local base = REPO_BASE_URL .. "/output/" .. team.slug .. "/tts_objects/"
    local files = {}
    if team.hasTokenBag then files[#files + 1] = {path = team.slug .. "-token-bag.json", optional = true} end
    for _, suffix in ipairs({"-dice", "-light-dice", "-dark-dice"}) do
        files[#files + 1] = {path = "dice/" .. team.slug .. suffix .. ".json"}
    end
    local version = sessionVersion
    local color = sessionColor
    local function refreshRoster()
        if panelRender == showRoster or panelRender == showSetup then panelRender() end
    end
    team.suppliesBusy = true
    showRoster()
    local spawned, finished, hasTokens = {}, false, false
    local function finish(errorMessage)
        if finished then return end
        finished = true
        team.suppliesBusy = false
        if errorMessage or version ~= sessionVersion then
            for _, object in ipairs(spawned) do object.destruct() end
        end
        if version ~= sessionVersion then return end
        if errorMessage then
            notify(color, errorMessage, {1, 0.3, 0.3})
        else
            team.suppliesSpawned = true
            notify(color, hasTokens and "Team token bag and dice spawned."
                or "Team dice spawned; no standalone token bag is published for this team.", {0.3, 1, 0.5})
        end
        refreshRoster()
    end
    local function nextFile(index)
        if finished then return end
        if version ~= sessionVersion then finish(); return end
        if index > #files then finish(); return end
        local file = files[index]
        requestText(base .. file.path .. "?v=" .. tostring(os.time()), function(text, errorMessage)
            if finished then return end
            if version ~= sessionVersion then finish(); return end
            if not text then
                if file.optional then nextFile(index + 1) else finish(errorMessage) end
                return
            end
            local ok, payload = pcall(function() return JSON.decode(text) end)
            local root = ok and type(payload) == "table" and (payload.ObjectStates and payload.ObjectStates[1] or payload)
            if type(root) ~= "table" or type(root.Name) ~= "string" then
                finish("Invalid team supply object: " .. file.path)
                return
            end
            local scale = self.getScale()
            local side = math.max(self.getBoundsNormalized().size.x * 0.5, 2.6 * scale.x) + 1.5
            local depth = hasTokens and (3 + (#spawned - 1) * 1.5) or #spawned * 1.5
            local called, object = pcall(function()
                return spawnObjectJSON({json = JSON.encode(root),
                    position = self.positionToWorld({side / scale.x, 1 / scale.y, depth / scale.z}),
                    rotation = self.getRotation()})
            end)
            if not called or not object then finish("Could not spawn team supplies; try again."); return end
            spawned[#spawned + 1] = object
            if file.optional then hasTokens = true end
            nextFile(index + 1)
        end)
    end
    Wait.time(function() finish("Team supplies timed out; please try again.") end, 30)
    nextFile(1)
end

function commandNodeChangeCount(player, _, id)
    if not isSessionPlayer(player) then return end
    local action, index = id:match("^(%a+)_(%d+)$")
    index = tonumber(index)
    if not index or not operatives[index] then return end
    local change = action == "plus" and 1 or -1
    counts[index] = math.max(0, math.min(20, (counts[index] or 0) + change))
    showRoster()
end

function commandNodeBackToTeams(player)
    if isSessionPlayer(player) then panelPage = 1; showTeams() end
end

local function clearSlots()
    for _, slot in ipairs(slots) do
        local object = slot.guid and getObjectFromGUID(slot.guid)
        if object then object.destruct() end
    end
    slots = {}
end

local function baseDimensions(raw)
    local width, depth = tostring(raw or ""):match("(%d+%.?%d*)%s*[xX]%s*(%d+%.?%d*)")
    if not width then width = tostring(raw or ""):match("(%d+%.?%d*)") end
    width = tonumber(width) or 32
    depth = tonumber(depth) or width
    return width / 25.4, depth / 25.4
end

local function slotDimensions(operative)
    local mounted = false
    for _, keyword in ipairs(operative.data.keywords or {}) do
        if tostring(keyword):upper() == "MOUNTED" then mounted = true end
    end
    local width, depth = baseDimensions(operative.data.stats.Base)
    if mounted then width, depth = math.min(width, depth), math.max(width, depth) end
    return 60 / 25.4, (mounted and 70 or 60) / 25.4, width, depth
end

local function showSlots()
    panelRender = showSlots
    local rows = {}
    for index, slot in ipairs(slots) do
        local prefix = index == selectedSlot and "> " or ""
        rows[#rows + 1] = button("slot_" .. index, "commandNodeSelectSlot",
            prefix .. index .. ". " .. operatives[slot.operative].name,
            index == selectedSlot and "#237A60" or nil)
    end
    panel("Place models on tiles: " .. currentTeam.name, rows,
        button("confirm", "commandNodeConfirm", "Confirm", "#237A60")
        .. button("cancel", "commandNodeCancel", "Cancel"))
end

local function showSlotLoadout()
    panelRender = showSlotLoadout
    local slot = slots[selectedSlot]
    local marker = getObjectFromGUID(slot.guid)
    if not marker then return end
    local rows = {}
    local rowGroups = {}
    local selection = operatives[slot.operative].data.selection
    if selection and selection.groups and #selection.groups > 0 then
        rows[#rows + 1] = '<Text preferredHeight="32" fontSize="20" color="#FFFFFF">Loadout</Text>'
        if selection.exclusive_sets and #selection.exclusive_sets > 0 then
            for index in ipairs(selection.exclusive_sets) do
                rows[#rows + 1] = button("set_" .. index, "commandNodeSelectSet",
                    (index == slot.selectedSet and "[x] " or "[ ] ") .. "Alternative " .. index)
            end
        end
        local active = {}
        if selection.exclusive_sets and #selection.exclusive_sets > 0 then
            for _, group in ipairs(selection.exclusive_sets[slot.selectedSet]) do active[group + 1] = true end
        else
            for group in ipairs(selection.groups) do active[group] = true end
        end
        for groupIndex, group in ipairs(selection.groups) do
            if active[groupIndex] then
                rowGroups[#rows + 1] = #group + 1
                rows[#rows + 1] = '<Text preferredHeight="26" fontSize="16" color="#A8BEB7">Choose one</Text>'
                for optionIndex, option in ipairs(group) do
                    local selected = (slot.choices[groupIndex] or 1) == optionIndex
                    rows[#rows + 1] = button("option_" .. groupIndex .. "_" .. optionIndex,
                        "commandNodeSelectOption", (selected and "[x] " or "[ ] ") .. (option.label or "Option"))
                end
            end
        end
    end
    panel(selectedSlot .. ". " .. operatives[slot.operative].name, rows,
        button("loadout_done", "commandNodeLoadoutDone", "Done", "#237A60"), nil, rowGroups)
end

function commandNodeCreateSlots(player)
    if not isSessionPlayer(player) or building then return end
    local total = 0
    for _, count in pairs(counts) do total = total + count end
    if total == 0 then
        notify(sessionColor, "Select at least one operative.")
        return
    end
    if total > 24 then
        notify(sessionColor, "A setup can contain at most 24 models.")
        return
    end
    local columnSpacing, rowSpacing = 0, 0
    for index, operative in ipairs(operatives) do
        if (counts[index] or 0) > 0 then
            local tileWidth, tileDepth, width, depth = slotDimensions(operative)
            columnSpacing = math.max(columnSpacing, tileWidth, width)
            rowSpacing = math.max(rowSpacing, tileDepth, depth)
        end
    end
    columnSpacing, rowSpacing = columnSpacing + 10 / 25.4, rowSpacing + 10 / 25.4
    clearSlots()
    building = true
    self.UI.setXml("")
    local remaining = total
    local version = sessionVersion
    for operativeIndex, operative in ipairs(operatives) do
        for _ = 1, counts[operativeIndex] or 0 do
            local index = #slots + 1
            local column = (index - 1) % 6
            local row = math.floor((index - 1) / 6)
            local tileWidth, tileDepth, baseWidth, baseDepth = slotDimensions(operative)
            local nodeScale = self.getScale()
            local halfDepth = self.getBoundsNormalized().size.z * 0.5
            local position = self.positionToWorld({
                (column - 2.5) * columnSpacing / nodeScale.x,
                0.4 / nodeScale.y,
                -(halfDepth + (row + 0.5) * rowSpacing) / nodeScale.z,
            })
            local choices = {}
            local selection = operative.data.selection
            for groupIndex in ipairs((selection and selection.groups) or {}) do
                choices[groupIndex] = 1
            end
            local slot = {
                operative = operativeIndex,
                choices = choices,
                selectedSet = 1,
                width = math.max(tileWidth, baseWidth),
                depth = math.max(tileDepth, baseDepth),
            }
            slots[index] = slot
            local object = spawnObject({type = "BlockSquare", position = position, scale = {1, 0.08, 1},
                rotation = self.getRotation(), sound = false, callback_function = function(marker)
                    if version ~= sessionVersion then marker.destruct(); return end
                    local bounds = marker.getBoundsNormalized().size
                    local markerScale = marker.getScale()
                    marker.setScale({markerScale.x * tileWidth / bounds.x, markerScale.y,
                        markerScale.z * tileDepth / bounds.z})
                    markerScale = marker.getScale()
                    marker.setLock(true)
                    marker.setName(index .. ". " .. operative.name)
                    marker.setColorTint({0, 0, 0})
                    marker.addTag("KTCommandNodeSlot-" .. self.getGUID())
                    local label, fontSize = slotLabel(index, operative.name)
                    marker.createButton({label = label,
                        click_function = "commandNodeSlotLabel", function_owner = self,
                        position = {0, 0.7, 0}, width = 0, height = 0, font_size = fontSize,
                        font_color = {1, 1, 1}, scale = {1 / markerScale.x, 12.5, 1 / markerScale.z}})
                    if selection and selection.groups and #selection.groups > 0 then
                        marker.createButton({label = "Loadout",
                            click_function = "commandNodeSlotLoadout", function_owner = self,
                            position = {0, 0.8, 0.8 / markerScale.z}, width = 850, height = 280, font_size = 150,
                            font_color = {1, 1, 1}, color = {0.14, 0.48, 0.38},
                            scale = {1 / markerScale.x, 12.5, 1 / markerScale.z}})
                    end
                    slot.guid = marker.getGUID()
                    remaining = remaining - 1
                    if remaining == 0 then
                        building = false
                        selectedSlot = 1
                        panelPage = 1
                        showSlots()
                    end
                end})
            if not object then
                sessionVersion = sessionVersion + 1
                building = false
                clearSlots()
                notify(sessionColor, "Could not create placement slots.", {1, 0.3, 0.3})
                showRoster()
                return
            end
        end
    end
end

function commandNodeSlotLabel() end

function commandNodeSelectSlot(player, _, id)
    if not isSessionPlayer(player) or applying or building then return end
    local index = tonumber(id:match("^slot_(%d+)$"))
    if index and slots[index] then
        selectedSlot = index
        panelPage = 1
        showSlots()
        local selection = operatives[slots[index].operative].data.selection
        if selection and selection.groups and #selection.groups > 0 then showSlotLoadout() end
    end
end

function commandNodeSlotLoadout(marker, color)
    for index, slot in ipairs(slots) do
        if slot.guid == marker.getGUID() then
            commandNodeSelectSlot({color = color}, nil, "slot_" .. index)
            return
        end
    end
end

function commandNodeLoadoutDone(player)
    if not isSessionPlayer(player) then return end
    panelPage = 1
    showSlots()
end

function commandNodeSelectSet(player, _, id)
    if not isSessionPlayer(player) then return end
    local index = tonumber(id:match("^set_(%d+)$"))
    local slot = slots[selectedSlot]
    local selection = operatives[slot.operative].data.selection
    if index and selection.exclusive_sets[index] then slot.selectedSet = index; showSlotLoadout() end
end

function commandNodeSelectOption(player, _, id)
    if not isSessionPlayer(player) then return end
    local group, option = id:match("^option_(%d+)_(%d+)$")
    group, option = tonumber(group), tonumber(option)
    local slot = slots[selectedSlot]
    local selection = operatives[slot.operative].data.selection
    if group and option and selection.groups[group] and selection.groups[group][option] then
        slot.choices[group] = option
        showSlotLoadout()
    end
end

function commandNodeCancel(player)
    if applying or building then
        if player and player.color then notify(player.color, "Please wait for setup to finish.") end
        return
    end
    if player and not isSessionPlayer(player) then return end
    sessionVersion = sessionVersion + 1
    clearSlots()
    sessionColor = nil
    self.UI.setXml("")
    setStartVisible(true)
end

function onDestroy()
    clearSlots()
    if activeHelper then
        local helper = getObjectFromGUID(activeHelper)
        if helper then helper.destruct() end
    end
end

local function findSlotModels(slot)
    local marker = getObjectFromGUID(slot.guid)
    if not marker then return nil, "Placement slot is missing." end
    local center = marker.getPosition()
    local hits = Physics.cast({origin = center + Vector(0, 1, 0), direction = {0, 1, 0}, type = 3,
        size = {slot.width, 3, slot.depth},
        orientation = marker.getRotation(), max_distance = 0})
    local models, seen = {}, {}
    for _, hit in ipairs(hits) do
        local object = hit.hit_object
        if object and MODEL_TYPES[object.type] then
            local guid = object.getGUID()
            if not seen[guid] then
                seen[guid] = true
                models[#models + 1] = object
            end
        end
    end
    return models
end

local function finishApply(errorMessage)
    applying = false
    if activeHelper then
        local helper = getObjectFromGUID(activeHelper)
        if helper then helper.destruct() end
        activeHelper = nil
    end
    if errorMessage then
        notify(sessionColor, errorMessage, {1, 0.3, 0.3})
        showSlots()
        return
    end
    local color = sessionColor
    clearSlots()
    sessionColor = nil
    self.UI.setXml("")
    setStartVisible(true)
    notify(color, "Operative stats and loadouts applied.", {0.3, 1, 0.5})
end

local function applyNext(index, models)
    if index > #slots then finishApply(); return end
    local slot = slots[index]
    if slot.done then applyNext(index + 1, models); return end
    local model = models[index]
    local targetGuid = model.getGUID()
    local operative = operatives[slot.operative]
    local ok, data = pcall(function() return JSON.decode(JSON.encode(operative.data)) end)
    if not ok or not data then
        finishApply("Slot " .. index .. ": could not prepare operative data.")
        return
    end
    local weapons, selectionError = selectedLoadoutWeapons(data, slot.choices, slot.selectedSet)
    if not weapons then
        finishApply("Slot " .. index .. ": " .. selectionError)
        return
    end
    data.weapons = weapons

    local position = self.getPosition() + Vector(0, 20, 0)
    local helper = spawnObject({type = "BlockSquare", position = position, scale = {0.1, 0.1, 0.1},
        sound = false, callback_function = function(ready)
        ready.setLock(true)
        ready.setInvisibleTo({"White", "Brown", "Red", "Orange", "Yellow", "Green", "Teal", "Blue", "Purple", "Pink", "Grey", "Black"})
        ready.setGMNotes(JSON.encode(data))
        ready.setLuaScript(loaderScript .. "\n" .. APPLY_ADAPTER)
        activeHelper = ready.getGUID()
        ready.reload()
        Wait.frames(function()
            local loaded = getObjectFromGUID(activeHelper)
            local target = getObjectFromGUID(targetGuid)
            if not loaded or not target then
                if loaded then loaded.destruct() end
                activeHelper = nil
                finishApply("Slot " .. index .. ": helper or model is no longer available.")
                return
            end
            local called, result = pcall(function()
                return loaded.call("ktCommandNodeApply", {
                    model = target, data = data, playerColor = sessionColor,
                    heading = self.getRotation().y,
                })
            end)
            if not called or type(result) ~= "table" or not result.applied then
                finishApply("Slot " .. index .. ": failed to apply stats; check the TTS log.")
                return
            end
            local function finishModel()
                local refreshed = getObjectFromGUID(targetGuid)
                if not refreshed then
                    finishApply("Slot " .. index .. ": model is no longer available after reload.")
                    return
                end
                local refreshedOk = pcall(function()
                    refreshed.call("loadState")
                    refreshed.call("refreshUI")
                    refreshed.call("refreshVectors", true)
                end)
                if not refreshedOk then
                    finishApply("Slot " .. index .. ": could not refresh model UI; check the TTS log.")
                    return
                end
                loaded.destruct()
                activeHelper = nil
                slot.done = true
                slot.modelGuid = targetGuid
                applyNext(index + 1, models)
            end
            if currentTeam.useSpecialRules ~= false and currentTeam.counterRule then
                Wait.frames(function()
                    local refreshed = getObjectFromGUID(targetGuid)
                    local counterOk, added = pcall(function()
                        if not refreshed then return false end
                        return loaded.call("ktCommandNodeAddCounters", {
                            model = refreshed, team = currentTeam.slug, playerColor = sessionColor,
                        })
                    end)
                    if not counterOk or not added then
                        finishApply("Slot " .. index .. ": could not add special-rule counters.")
                        return
                    end
                    Wait.frames(finishModel, 30)
                end, 10)
            else
                Wait.frames(finishModel, 10)
            end
        end, 60)
    end})
    if not helper then finishApply("Slot " .. index .. ": could not create the stats helper."); return end
end

function commandNodeConfirm(player)
    if not isSessionPlayer(player) or applying then return end
    local models, used = {}, {}
    for index, slot in ipairs(slots) do
        if slot.done then
            used[slot.modelGuid] = true
        else
            local weapons, selectionError = selectedLoadoutWeapons(
                operatives[slot.operative].data, slot.choices, slot.selectedSet)
            if not weapons then notify(sessionColor, "Slot " .. index .. ": " .. selectionError); return end
            local matches, errorMessage = findSlotModels(slot)
            if not matches then notify(sessionColor, "Slot " .. index .. ": " .. errorMessage); return end
            if #matches ~= 1 then
                notify(sessionColor, "Slot " .. index .. " needs exactly one model; found " .. #matches .. ".")
                return
            end
            local guid = matches[1].getGUID()
            if used[guid] then notify(sessionColor, "A model is assigned to more than one slot."); return end
            used[guid] = true
            models[index] = matches[1]
        end
    end
    applying = true
    self.UI.setXml("")
    notify(sessionColor, "Applying stats and loadouts...", {0.5, 0.8, 1})
    if loaderScript then
        applyNext(1, models)
        return
    end
    local version = sessionVersion
    requestText(NODE_LOADER_URL .. "?v=" .. tostring(os.time()), function(script, errorMessage)
        if version ~= sessionVersion then return end
        if not compatibleLoader(script) then
            finishApply(errorMessage or "Downloaded node loader is outdated; publish the updated shared loader to the feature branch.")
            return
        end
        loaderScript = script
        applyNext(1, models)
    end)
end