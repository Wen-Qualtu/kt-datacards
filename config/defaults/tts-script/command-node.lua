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

-- TTS's string.match fails on values ending in the non-ASCII inch mark (U+2033).
local function leadingNumber(value)
    local text, digits = tostring(value or ""), ""
    for index = 1, #text do
        local byte = text:byte(index)
        if byte >= 48 and byte <= 57 then
            digits = digits .. string.char(byte)
        elseif digits ~= "" then
            break
        end
    end
    return tonumber(digits)
end

function commandNodeModelData(operative, teamRules)
    local node = operative.node
    local prepared = type(operative.stats) == "table"
    if not prepared and (type(node) ~= "table" or type(node.weapon_types) ~= "table") then
        return nil, "Team data needs prepared model fields. Regenerate the team data."
    end
    local stats = operative.stats
    if not prepared then
        stats = {
            APL = tonumber(operative.apl),
            Move = leadingNumber(operative.movement),
            Save = leadingNumber(operative.save),
            Wounds = tonumber(operative.wounds),
            Base = operative.base_size,
        }
        local missing = {}
        for _, key in ipairs({"APL", "Move", "Save", "Wounds"}) do
            if not stats[key] then missing[#missing + 1] = key end
        end
        if #missing > 0 then
            return nil, "Missing " .. table.concat(missing, ", ") .. " for "
                .. cleanText(operative.name or "unnamed operative") .. ". Regenerate the team data."
        end
    end
    local data = {
        name = cleanText(operative.name or ""),
        stats = stats,
        keywords = {"Operative"}, weapons = {}, abilities = {}, actions = {},
        weapon_rules = {}, selection = operative.selection or (node and node.selection),
        upgrades = operative.upgrades,
    }
    for _, name in ipairs(not prepared and node.weapon_rule_names or {}) do
        if type(teamRules) ~= "table" or teamRules[name] == nil then
            return nil, "Missing weapon rule " .. tostring(name) .. "."
        end
        data.weapon_rules[name] = teamRules[name]
    end
    for _, keyword in ipairs(operative.keywords or {}) do
        data.keywords[#data.keywords + 1] = cleanText(keyword, true)
    end
    for index, weapon in ipairs(operative.weapons or {}) do
        local kind = weapon.type or (node and node.weapon_types and node.weapon_types[index])
        if kind ~= "melee" and kind ~= "ranged" then
            return nil, "Invalid weapon classification for " .. data.name .. "."
        end
        local name = cleanText(weapon.name or "")
        local prefix = kind == "melee" and "[F4641D]M[-] " or "[1E87FF]R[-] "
        local stats = weapon.stats or {
            ATK = weapon.attacks or "", HIT = weapon.hit or "",
            DMG = weapon.damage or "", WR = weapon.special_rules or "",
        }
        data.weapons[#data.weapons + 1] = {
            name = prefix .. name, plain_name = name,
            stats = {ATK = cleanText(stats.ATK), HIT = cleanText(stats.HIT),
                DMG = cleanText(stats.DMG), WR = cleanText(stats.WR)},
        }
        for rule, description in pairs(weapon.weapon_rules or {}) do
            data.weapon_rules[rule] = cleanText(description)
        end
    end
    for _, ability in ipairs(operative.abilities or operative.passive_abilities or {}) do
        local name = cleanText(ability.name or "", true)
        if name ~= "" then
            data.abilities[#data.abilities + 1] = {name = name, text = cleanText(ability.text or ability.description or "", true)}
        end
    end
    for _, action in ipairs(operative.actions or operative.unique_actions or {}) do
        local name = cleanText(action.name or "", true)
        if name ~= "" then
            data.actions[#data.actions + 1] = {name = name, text = cleanText(action.text or action.description or "", true)}
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
local PANEL_MAX_HEIGHT = 560
local TITLE_HEIGHT = 48

local MODEL_TYPES = {
    Custom_Model = true,
    Figurine_Custom = true,
    Custom_Assetbundle = true,
    Figurine = true,
}

local APPLY_ADAPTER = [[
KT_NODE_HELPER_READY = true

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

local function wrapWords(text, width)
    local lines, line, longest = {}, nil, 0
    for word in text:gmatch("%S+") do
        if line and #line + #word + 1 > width then
            lines[#lines + 1] = line
            line = word
        else
            line = line and line .. " " .. word or word
        end
        longest = math.max(longest, #line)
    end
    lines[#lines + 1] = line
    return lines, longest
end

local function slotLabel(index, name)
    local lines, longest = wrapWords(index .. ". " .. name, 16)
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
    local declaration = script:find("function diffAndApply", 1, true)
    local opening = declaration and script:find("(", declaration, true)
    local closing = opening and script:find(")", opening + 1, true)
    local signature = closing and script:sub(opening, closing)
    return signature and signature:find("replaceScript", 1, true) ~= nil
        and signature:find("modelScript", 1, true) ~= nil
end

local function isBareObjectText(text)
    local index = 1
    while index <= #text do
        local byte = text:byte(index)
        if byte ~= 32 and byte ~= 9 and byte ~= 10 and byte ~= 13 then break end
        index = index + 1
    end
    if text:byte(index) ~= 123 then return false end
    local opening = text:find('"', index + 1, true)
    local closing = opening and text:find('"', opening + 1, true)
    if not closing then return false end
    local firstKey = text:sub(opening + 1, closing - 1)
    return firstKey ~= "SaveName" and firstKey ~= "ObjectStates"
end

local function panel(title, rows, footer, rowHeight, rowGroups, controls, controlsHeight)
    rowHeight = rowHeight or 34
    local spacing = 6
    local fixedHeight = 28 + TITLE_HEIGHT + 42 + spacing + (controls and (controlsHeight or 34) + spacing or 0)
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
            <Button id="page_prev" onClick="commandNodePage" preferredWidth="36" flexibleWidth="0" minHeight="28" preferredHeight="28" flexibleHeight="0" fontSize="16" colors="#34454A|#56686D|#293336|#333333" textColor="#FFFFFF" interactable="%s">&lt;</Button>
            <Text preferredWidth="80" flexibleWidth="0" preferredHeight="28" flexibleHeight="0" fontSize="14" color="#FFFFFF">%d / %d</Text>
            <Button id="page_next" onClick="commandNodePage" preferredWidth="36" flexibleWidth="0" minHeight="28" preferredHeight="28" flexibleHeight="0" fontSize="16" colors="#34454A|#56686D|#293336|#333333" textColor="#FFFFFF" interactable="%s">&gt;</Button>
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
    <Text fontSize="25" fontStyle="Bold" color="#FFFFFF" alignment="UpperCenter" preferredHeight="%d">%s</Text>
    %s
    %s
    %s
        <HorizontalLayout spacing="6" preferredHeight="42" flexibleHeight="0" childForceExpandHeight="false">%s</HorizontalLayout>
  </VerticalLayout>
</Panel>]], panelHeight, panelPosition, panelScale, panelScale,
        TITLE_HEIGHT, xmlEscape(title), table.concat(visibleRows), navigation, controls or "", footer)
    self.UI.setXml(xml)
end

local function button(id, action, label, tint)
    return string.format('<Button id="%s" onClick="%s" minHeight="34" preferredHeight="34" flexibleHeight="0" fontSize="17" '
        .. 'colors="%s|#56686D|#293336|#333333" textColor="#FFFFFF">%s</Button>',
        id, action, tint or "#34454A", xmlEscape(label))
end

local function listRow(index, content)
    return string.format('<HorizontalLayout preferredHeight="42" flexibleHeight="0" spacing="4" padding="10 4 3 3" '
        .. 'childForceExpandWidth="false" childForceExpandHeight="false" childAlignment="MiddleLeft" color="%s">%s</HorizontalLayout>',
        index % 2 == 0 and "#FFFFFF14" or "#00000000", content)
end

local function showTeams()
    panelRender = showTeams
    local rows = {}
    for index = 1, #teams, 2 do
        local right = teams[index + 1]
            and button("team_" .. (index + 1), "commandNodeChooseTeam", teams[index + 1].name) or "<Text></Text>"
        rows[#rows + 1] = '<HorizontalLayout spacing="6" preferredHeight="34" flexibleHeight="0" childForceExpandHeight="false">'
            .. button("team_" .. index, "commandNodeChooseTeam", teams[index].name) .. right .. '</HorizontalLayout>'
    end
    panel("Choose a team", rows, button("cancel", "commandNodeCancel", "Cancel"))
end

local function showRoster()
    panelRender = showRoster
    local rows = {}
    for index, operative in ipairs(operatives) do
        rows[#rows + 1] = listRow(index, string.format(
            '<Text flexibleWidth="1" fontSize="16" color="#FFFFFF" alignment="MiddleLeft" horizontalOverflow="Truncate">%s</Text>'
            .. '<Button id="minus_%d" onClick="commandNodeChangeCount" preferredWidth="58" flexibleWidth="0" preferredHeight="36" fontSize="20">-</Button>'
            .. '<Text preferredWidth="48" flexibleWidth="0" fontSize="16" color="#FFFFFF">%d</Text>'
            .. '<Button id="plus_%d" onClick="commandNodeChangeCount" preferredWidth="58" flexibleWidth="0" preferredHeight="36" fontSize="20">+</Button>',
            xmlEscape(operative.name), index, counts[index] or 0, index))
    end
    local controlsHeight = currentTeam.counterRule and 74 or 34
    local controls = '<VerticalLayout preferredHeight="' .. controlsHeight .. '" flexibleHeight="0" spacing="6" childForceExpandHeight="false">'
        .. button("setup_cardbox", "commandNodeToggleCardbox",
            currentTeam.useCardbox and "Cardbox added (tokens + dice)" or "Add cardbox (tokens + dice)",
            currentTeam.useCardbox and "#237A60" or nil)
    if currentTeam.counterRule then
        local name = currentTeam.counterRule.name
        controls = controls .. '<HorizontalLayout preferredHeight="34" flexibleHeight="0" spacing="6" childForceExpandHeight="false">'
            .. button("setup_rules", "commandNodeToggleRules",
                currentTeam.useSpecialRules and name .. " added" or "Add " .. name,
                currentTeam.useSpecialRules and "#237A60" or nil)
        if currentTeam.counterRule.options and currentTeam.useSpecialRules then
            controls = controls .. button("choose_rules", "commandNodeChooseRules", "Select " .. name)
        end
        controls = controls .. '</HorizontalLayout>'
    end
    controls = controls .. '</VerticalLayout>'
    panel(currentTeam.name, rows,
        button("back", "commandNodeBackToTeams", "Teams")
        .. button("next", "commandNodeNext", "Next", "#237A60")
        .. button("cancel", "commandNodeCancel", "Cancel"), 42, nil, controls, controlsHeight)
end

local function isSessionPlayer(player)
    return player and player.color == sessionColor
end

local function ruleChoiceCount(rule)
    local count = rule.select or 1
    for _, override in pairs(rule.operative_select_count or {}) do count = math.max(count, override) end
    return count
end

local function showRuleChoices()
    panelRender = showRuleChoices
    local rule = currentTeam.counterRule
    local rows, groups = {}, {}
    for choice = 1, ruleChoiceCount(rule) do
        groups[#rows + 1] = #rule.options + 1
        local label = ruleChoiceCount(rule) == 1 and "Choose one" or (choice == 1 and "Primary" or "Secondary")
        rows[#rows + 1] = '<Text preferredHeight="26" fontSize="16" color="#A8BEB7">' .. label .. '</Text>'
        for index, option in ipairs(rule.options) do
            rows[#rows + 1] = button("rule_" .. choice .. "_" .. index, "commandNodeRuleOption",
                (currentTeam.ruleChoices[choice] == index and "[x] " or "[ ] ") .. option.name)
        end
    end
    panel(rule.name, rows, button("rules_done", "commandNodeRulesDone", "Done", "#237A60"), nil, groups)
end

function commandNodeChooseRules(player)
    if not isSessionPlayer(player) or panelRender ~= showRoster or not currentTeam.useSpecialRules then return end
    if not currentTeam.counterRule or not currentTeam.counterRule.options then return end
    panelPage = 1
    showRuleChoices()
end

function commandNodeRuleOption(player, _, id)
    if not isSessionPlayer(player) or panelRender ~= showRuleChoices then return end
    local choice, option = id:match("^rule_(%d+)_(%d+)$")
    choice, option = tonumber(choice), tonumber(option)
    local rule = currentTeam.counterRule
    if not choice or not option or choice > ruleChoiceCount(rule) or not rule.options[option] then return end
    local previous = currentTeam.ruleChoices[choice]
    for index, selected in ipairs(currentTeam.ruleChoices) do
        if index ~= choice and selected == option then currentTeam.ruleChoices[index] = previous end
    end
    currentTeam.ruleChoices[choice] = option
    showRuleChoices()
end

function commandNodeRulesDone(player)
    if not isSessionPlayer(player) or panelRender ~= showRuleChoices then return end
    panelPage = 1
    showRoster()
end

function commandNodeToggleRules(player)
    if not isSessionPlayer(player) or panelRender ~= showRoster or building then return end
    currentTeam.useSpecialRules = not currentTeam.useSpecialRules
    showRoster()
end

function commandNodeToggleCardbox(player)
    if not isSessionPlayer(player) or panelRender ~= showRoster or building then return end
    currentTeam.useCardbox = not currentTeam.useCardbox
    showRoster()
end

function commandNodeNext(player)
    if not isSessionPlayer(player) or applying or building or panelRender ~= showRoster then return end
    if commandNodeCreateSlots(player) then commandNodeSpawnSupplies(player) end
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
            currentTeam.useCardbox = false
            currentTeam.useSpecialRules = true
            currentTeam.cardboxPath = type(metadata.box) == "table" and type(metadata.box.url) == "string"
                and metadata.box.url:match("/output/([^?]+)") or nil
            counts = {}
            panelPage = 1
            local function ready(script, loaderError)
                if version ~= sessionVersion then return end
                local metadata
                if type(script) == "string" then
                    local marker = "NODE_COUNTER_SETUP = [====["
                    local opening = script:find(marker, 1, true)
                    if opening then
                        local start = opening + #marker
                        local closing = script:find("]====]", start, true)
                        if closing then metadata = script:sub(start, closing - 1) end
                    end
                end
                local ok, rules = pcall(function() return metadata and JSON.decode(metadata) end)
                if not compatibleLoader(script) or not ok or type(rules) ~= "table" then
                    notify(sessionColor, loaderError or "Published loader needs the special-rule setup update.", {1, 0.3, 0.3})
                    showTeams()
                    return
                end
                loaderScript = script
                currentTeam.counterRule = rules[currentTeam.slug]
                currentTeam.ruleChoices = {}
                local rule = currentTeam.counterRule
                if rule and rule.options then
                    local texts = {}
                    for _, factionRule in ipairs(payload.faction_rules or {}) do
                        for _, option in ipairs(factionRule.options or {}) do
                            texts[cleanText(option.name, true):lower()] = option.text
                        end
                    end
                    for _, option in ipairs(rule.options) do
                        option.text = option.text or texts[cleanText(option.name, true):lower()] or ""
                    end
                    for choice = 1, ruleChoiceCount(rule) do currentTeam.ruleChoices[choice] = choice end
                end
                showRoster()
            end
            requestText(NODE_LOADER_URL .. "?v=" .. tostring(os.time()), ready)
        end)
    end)
end

function commandNodeSpawnSupplies(player)
    if not isSessionPlayer(player) or not currentTeam or applying then return end
    local team = currentTeam
    if not team.useCardbox or team.suppliesBusy or team.suppliesSpawned then return end
    local path = team.cardboxPath
    local prefix = team.slug .. "/tts_objects/"
    if not path or path:sub(1, #prefix) ~= prefix or path:sub(-5) ~= ".json"
        or path:find("..", 1, true) then
        notify(sessionColor, "No published cardbox is available for this team.", {1, 0.3, 0.3})
        return
    end
    local version = sessionVersion
    local color = sessionColor
    local function refreshRoster()
        if panelRender == showRoster and not building then showRoster() end
    end
    team.suppliesBusy = true
    refreshRoster()
    local finished = false
    local function finish(errorMessage)
        if finished then return end
        finished = true
        team.suppliesBusy = false
        if version ~= sessionVersion then return end
        if errorMessage then
            notify(color, errorMessage, {1, 0.3, 0.3})
        else
            team.suppliesSpawned = true
            notify(color, "Team cardbox spawned.", {0.3, 1, 0.5})
        end
        refreshRoster()
    end
    requestText(REPO_BASE_URL .. "/output/" .. path .. "?v=" .. tostring(os.time()), function(text, errorMessage)
        if finished then return end
        if version ~= sessionVersion then finish(); return end
        if not text then finish(errorMessage); return end
        local spawnJson = text
        if not isBareObjectText(text) then
            local ok, payload = pcall(function() return JSON.decode(text) end)
            local root = ok and type(payload) == "table" and (payload.ObjectStates and payload.ObjectStates[1] or payload)
            if type(root) ~= "table" or type(root.Name) ~= "string" then
                finish("Invalid team cardbox object: " .. path)
                return
            end
            spawnJson = JSON.encode(root)
        end
        local scale = self.getScale()
        local side = math.max(self.getBoundsNormalized().size.x * 0.5, 2.6 * scale.x) + 3
        local called, object = pcall(function()
            return spawnObjectJSON({json = spawnJson,
                position = self.positionToWorld({side / scale.x, 1 / scale.y, 3 / scale.z}),
                rotation = self.getRotation()})
        end)
        finish((not called or not object) and "Could not spawn the team cardbox; try again." or nil)
    end)
    Wait.time(function() finish("Team cardbox timed out; please try again.") end, 30)
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

local function hasLoadout(slot)
    local selection = operatives[slot.operative].data.selection
    return selection and selection.groups and #selection.groups > 0
end

local function loadoutButtonLabel(slot)
    return slot.loadoutChosen and "Change loadout" or "Choose loadout"
end

local function activeGroups(slot, selection)
    local active = {}
    if selection.exclusive_sets and #selection.exclusive_sets > 0 then
        for _, group in ipairs(selection.exclusive_sets[slot.selectedSet] or {}) do active[group + 1] = true end
    else
        for group in ipairs(selection.groups) do active[group] = true end
    end
    return active
end

local function loadoutSummary(slot)
    local selection = operatives[slot.operative].data.selection
    local active = activeGroups(slot, selection)
    local lines, longest = {}, 1
    for groupIndex, group in ipairs(selection.groups) do
        local option = active[groupIndex] and group[slot.choices[groupIndex] or 1]
        if option then
            local wrapped, width = wrapWords(cleanText(option.label or "Option", true), 22)
            for _, line in ipairs(wrapped) do lines[#lines + 1] = line end
            longest = math.max(longest, width)
        end
    end
    return table.concat(lines, "\n"), math.min(50, math.floor(1000 / longest))
end

local function refreshSlotTile(slot)
    local marker = getObjectFromGUID(slot.guid)
    if not marker then return end
    local summary, fontSize = "All weapons", 50
    if slot.loadoutChosen then summary, fontSize = loadoutSummary(slot) end
    marker.editButton({index = 1, label = loadoutButtonLabel(slot)})
    marker.editButton({index = 2, label = summary, font_size = fontSize})
end

local function showSlots()
    panelRender = showSlots
    local rows = {}
    for index, slot in ipairs(slots) do
        local operative = operatives[slot.operative]
        local loadout = ""
        if hasLoadout(slot) then
            loadout = button("slot_" .. index, "commandNodeSelectSlot", loadoutButtonLabel(slot))
                :gsub('preferredHeight=', 'preferredWidth="170" flexibleWidth="0" preferredHeight=', 1)
        end
        rows[#rows + 1] = listRow(index, string.format(
            '<Text flexibleWidth="1" fontSize="16" color="#FFFFFF" alignment="MiddleLeft" horizontalOverflow="Truncate">%s</Text>%s',
            xmlEscape(index .. ". " .. operative.name), loadout))
    end
    panel("Place models on tiles: " .. currentTeam.name, rows,
        button("slots_back", "commandNodeSlotsBack", "Back")
        .. button("confirm", "commandNodeConfirm", "Confirm", "#237A60")
        .. button("cancel", "commandNodeCancel", "Cancel"), 42)
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
        rows[#rows + 1] = '<Text preferredHeight="32" fontSize="20" color="#FFFFFF">'
            .. (slot.loadoutChosen and "Loadout" or "Loadout: all weapons until you choose") .. '</Text>'
        if selection.exclusive_sets and #selection.exclusive_sets > 0 then
            for index in ipairs(selection.exclusive_sets) do
                rows[#rows + 1] = button("set_" .. index, "commandNodeSelectSet",
                    (slot.loadoutChosen and index == slot.selectedSet and "[x] " or "[ ] ") .. "Alternative " .. index)
            end
        end
        local active = activeGroups(slot, selection)
        for groupIndex, group in ipairs(selection.groups) do
            if active[groupIndex] then
                rowGroups[#rows + 1] = #group + 1
                rows[#rows + 1] = '<Text preferredHeight="26" fontSize="16" color="#A8BEB7">Choose one</Text>'
                for optionIndex, option in ipairs(group) do
                    local selected = slot.loadoutChosen and (slot.choices[groupIndex] or 1) == optionIndex
                    rows[#rows + 1] = button("option_" .. groupIndex .. "_" .. optionIndex,
                        "commandNodeSelectOption", (selected and "[x] " or "[ ] ") .. (option.label or "Option"))
                end
            end
        end
    end
    panel(selectedSlot .. ". " .. operatives[slot.operative].name, rows,
        button("loadout_all", "commandNodeLoadoutAll", "All weapons", not slot.loadoutChosen and "#237A60" or nil)
        .. button("loadout_done", "commandNodeLoadoutDone", "Done", "#237A60"), nil, rowGroups)
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
            local rowCount = math.min(6, total - row * 6)
            local tileWidth, tileDepth, baseWidth, baseDepth = slotDimensions(operative)
            local nodeScale = self.getScale()
            local halfDepth = self.getBoundsNormalized().size.z * 0.5
            local position = self.positionToWorld({
                ((rowCount - 1) / 2 - column) * columnSpacing / nodeScale.x,
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
                    marker.tooltip = false
                    marker.setName(index .. ". " .. operative.name)
                    marker.setColorTint({0, 0, 0})
                    marker.addTag("KTCommandNodeSlot-" .. self.getGUID())
                    local label, fontSize = slotLabel(index, operative.name)
                    local loadout = selection and selection.groups and #selection.groups > 0
                    local buttonScale = {1 / markerScale.x, 12.5, 1 / markerScale.z}
                    marker.createButton({label = label,
                        click_function = "commandNodeSlotLabel", function_owner = self,
                        position = {0, 0.7, (loadout and -0.4 or 0) / markerScale.z}, width = 0, height = 0,
                        font_size = fontSize, font_color = {1, 1, 1}, scale = buttonScale})
                    if loadout then
                        marker.createButton({label = loadoutButtonLabel(slot),
                            click_function = "commandNodeSlotLoadout", function_owner = self,
                            position = {0, 0.8, 0.8 / markerScale.z}, width = 1000, height = 280, font_size = 110,
                            font_color = {1, 1, 1}, color = {0.14, 0.48, 0.38}, scale = buttonScale})
                        marker.createButton({label = "All weapons",
                            click_function = "commandNodeSlotLabel", function_owner = self,
                            position = {0, 0.7, 0.25 / markerScale.z}, width = 0, height = 0, font_size = 50,
                            font_color = {0.66, 0.75, 0.72}, scale = buttonScale})
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
    return true
end

function commandNodeSlotLabel() end

function commandNodeSelectSlot(player, _, id)
    if not isSessionPlayer(player) or applying or building then return end
    local index = tonumber(id:match("^slot_(%d+)$"))
    local slot = index and slots[index]
    if slot and hasLoadout(slot) then
        selectedSlot = index
        panelPage = 1
        showSlotLoadout()
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

function commandNodeLoadoutAll(player)
    if not isSessionPlayer(player) or panelRender ~= showSlotLoadout then return end
    local slot = slots[selectedSlot]
    slot.loadoutChosen = false
    slot.selectedSet = 1
    for group in pairs(slot.choices) do slot.choices[group] = 1 end
    refreshSlotTile(slot)
    panelPage = 1
    showSlots()
end

function commandNodeSlotsBack(player)
    if not isSessionPlayer(player) or applying or building or panelRender ~= showSlots then return end
    clearSlots()
    panelPage = 1
    showRoster()
end

function commandNodeSelectSet(player, _, id)
    if not isSessionPlayer(player) then return end
    local index = tonumber(id:match("^set_(%d+)$"))
    local slot = slots[selectedSlot]
    local selection = operatives[slot.operative].data.selection
    if index and selection.exclusive_sets[index] then
        slot.selectedSet = index
        slot.loadoutChosen = true
        refreshSlotTile(slot)
        showSlotLoadout()
    end
end

function commandNodeSelectOption(player, _, id)
    if not isSessionPlayer(player) then return end
    local group, option = id:match("^option_(%d+)_(%d+)$")
    group, option = tonumber(group), tonumber(option)
    local slot = slots[selectedSlot]
    local selection = operatives[slot.operative].data.selection
    if group and option and selection.groups[group] and selection.groups[group][option] then
        slot.choices[group] = option
        slot.loadoutChosen = true
        refreshSlotTile(slot)
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

local function prepareSlotData(index, slot)
    local ok, data = pcall(function() return JSON.decode(JSON.encode(operatives[slot.operative].data)) end)
    if not ok or not data then return nil, "Slot " .. index .. ": could not prepare operative data." end
    if slot.loadoutChosen then
        local weapons, selectionError = selectedLoadoutWeapons(data, slot.choices, slot.selectedSet)
        if not weapons then return nil, "Slot " .. index .. ": " .. selectionError end
        data.weapons = weapons
    end
    local rule = currentTeam.counterRule
    if currentTeam.useSpecialRules and rule and rule.options then
        local applies = not rule.applies_to
        for _, keyword in ipairs(rule.applies_to or {}) do
            for _, operativeKeyword in ipairs(data.keywords or {}) do
                if keyword:upper() == operativeKeyword:upper() then applies = true end
            end
        end
        if applies then
            local selectCount = rule.select or 1
            local overrideCount = 0
            for _, keyword in ipairs(data.keywords or {}) do
                local override = (rule.operative_select_count or {})[keyword:upper()]
                if override then overrideCount = math.max(overrideCount, override) end
            end
            if overrideCount > 0 then selectCount = overrideCount end
            for choice, selected in ipairs(currentTeam.ruleChoices) do
                if choice > selectCount then break end
                local option = rule.options[selected]
                if not option then return nil, "Invalid special-rule choice." end
                local suffix = selectCount == 1 and "" or (choice == 1 and " (Primary)" or " (Secondary)")
                data.abilities[#data.abilities + 1] = {name = option.name .. suffix, text = option.text}
            end
        end
    end
    return data
end

local function applyAll(models)
    local pending = {}
    for index, slot in ipairs(slots) do
        if not slot.done then
            local data, errorMessage = prepareSlotData(index, slot)
            if not data then finishApply(errorMessage); return end
            pending[#pending + 1] = {index = index, slot = slot, guid = models[index].getGUID(), data = data}
        end
    end
    if #pending == 0 then finishApply(); return end

    local firstError
    local function fail(item, message)
        item.failed = true
        firstError = firstError or ("Slot " .. item.index .. ": " .. message)
    end
    local function refreshAll()
        for _, item in ipairs(pending) do
            if not item.failed then
                local refreshed = getObjectFromGUID(item.guid)
                local refreshedOk = refreshed ~= nil and pcall(function()
                    refreshed.call("loadState")
                    refreshed.call("refreshUI")
                    refreshed.call("refreshVectors", true)
                end)
                if refreshedOk then
                    item.slot.done = true
                    item.slot.modelGuid = item.guid
                else
                    fail(item, "could not refresh model UI; check the TTS log.")
                end
            end
        end
        finishApply(firstError)
    end
    local function run()
        local helper = getObjectFromGUID(activeHelper)
        local heading = self.getRotation().y
        for _, item in ipairs(pending) do
            local target = getObjectFromGUID(item.guid)
            if not target then
                fail(item, "model is no longer available.")
            else
                local called, result = pcall(function()
                    return helper.call("ktCommandNodeApply", {
                        model = target, data = item.data, playerColor = sessionColor, heading = heading,
                    })
                end)
                if not called or type(result) ~= "table" or not result.applied then
                    fail(item, "failed to apply stats; check the TTS log.")
                end
            end
        end
        if currentTeam.useSpecialRules ~= false and currentTeam.counterRule and not currentTeam.counterRule.options then
            Wait.frames(function()
                for _, item in ipairs(pending) do
                    if not item.failed then
                        local refreshed = getObjectFromGUID(item.guid)
                        local counterOk, added = pcall(function()
                            if not refreshed then return false end
                            return helper.call("ktCommandNodeAddCounters", {
                                model = refreshed, team = currentTeam.slug, playerColor = sessionColor,
                            })
                        end)
                        if not counterOk or not added then fail(item, "could not add special-rule counters.") end
                    end
                end
                Wait.frames(refreshAll, 30)
            end, 10)
        else
            Wait.frames(refreshAll, 10)
        end
    end

    local position = self.getPosition() + Vector(0, 20, 0)
    local helper = spawnObject({type = "BlockSquare", position = position, scale = {0.1, 0.1, 0.1},
        sound = false, callback_function = function(ready)
        ready.setLock(true)
        ready.setInvisibleTo({"White", "Brown", "Red", "Orange", "Yellow", "Green", "Teal", "Blue", "Purple", "Pink", "Grey", "Black"})
        ready.setGMNotes(JSON.encode(pending[1].data))
        ready.setLuaScript(loaderScript .. "\n" .. APPLY_ADAPTER)
        activeHelper = ready.getGUID()
        ready.reload()
        Wait.condition(run, function()
            local loaded = getObjectFromGUID(activeHelper)
            return loaded ~= nil and loaded.getVar("KT_NODE_HELPER_READY") == true
        end, 15, function() finishApply("The stats helper did not load; please try again.") end)
    end})
    if not helper then finishApply("Could not create the stats helper.") end
end

function commandNodeConfirm(player)
    if not isSessionPlayer(player) or applying then return end
    local models, used = {}, {}
    for index, slot in ipairs(slots) do
        if slot.done then
            used[slot.modelGuid] = true
        else
            local weapons, selectionError = true, nil
            if slot.loadoutChosen then
                weapons, selectionError = selectedLoadoutWeapons(
                    operatives[slot.operative].data, slot.choices, slot.selectedSet)
            end
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
    if not compatibleLoader(loaderScript) then
        finishApply("The node loader is missing; choose the team again.")
        return
    end
    applyAll(models)
end