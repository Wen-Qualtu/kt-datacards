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
        value = value:match("^%s*(.-)%s*$")
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
local ROWS_PER_PAGE = 10

local MODEL_TYPES = {
    Custom_Model = true,
    Figurine_Custom = true,
    Custom_Assetbundle = true,
    Figurine = true,
}

local APPLY_ADAPTER = [[
function ktCommandNodeApply(params)
    if not params or not params.model or not params.data then return nil end
    params.data.description = rebuildDescription(params.data)
    local changes = diffAndApply(params.model, params.data, params.playerColor)
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

local function panel(title, rows, footer)
    local pageCount = math.max(1, math.ceil(#rows / ROWS_PER_PAGE))
    panelPage = math.max(1, math.min(panelPage, pageCount))
    local visibleRows = {}
    local first = (panelPage - 1) * ROWS_PER_PAGE + 1
    for index = first, math.min(first + ROWS_PER_PAGE - 1, #rows) do
        visibleRows[#visibleRows + 1] = rows[index]
    end
    local navigation = ""
    if pageCount > 1 then
        navigation = string.format([[
    <HorizontalLayout spacing="6" preferredHeight="36">
      <Button id="page_prev" onClick="commandNodePage" fontSize="16">Previous</Button>
      <Text fontSize="16" color="#FFFFFF">%d / %d</Text>
      <Button id="page_next" onClick="commandNodePage" fontSize="16">Next</Button>
    </HorizontalLayout>]], panelPage, pageCount)
    end
    self.UI.setXml(string.format([[
<Panel id="nodePanel" width="650" height="650" position="0 0 -80" rotation="0 0 180"
       color="#171D1FF2" padding="14 14 14 14">
  <VerticalLayout spacing="6" childForceExpandWidth="true" childForceExpandHeight="false">
    <Text fontSize="25" fontStyle="Bold" color="#FFFFFF" preferredHeight="40">%s</Text>
    %s
    %s
    <HorizontalLayout spacing="6" preferredHeight="42">%s</HorizontalLayout>
  </VerticalLayout>
</Panel>]], xmlEscape(title), table.concat(visibleRows), navigation, footer))
end

local function button(id, action, label, tint)
    return string.format('<Button id="%s" onClick="%s" preferredHeight="34" fontSize="17" '
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
        rows[#rows + 1] = string.format('<HorizontalLayout preferredHeight="36" spacing="5">'
            .. '<Text fontSize="17" color="#FFFFFF" alignment="MiddleLeft">%s</Text>'
            .. '<Button id="minus_%d" onClick="commandNodeChangeCount" preferredWidth="40" fontSize="22">-</Button>'
            .. '<Text preferredWidth="38" fontSize="18" color="#FFFFFF">%d</Text>'
            .. '<Button id="plus_%d" onClick="commandNodeChangeCount" preferredWidth="40" fontSize="22">+</Button>'
            .. '</HorizontalLayout>', xmlEscape(operative.name), index, counts[index] or 0, index)
    end
    panel(currentTeam.name, rows,
        button("back", "commandNodeBackToTeams", "Teams")
        .. button("next", "commandNodeCreateSlots", "Create slots", "#237A60")
        .. button("cancel", "commandNodeCancel", "Cancel"))
end

local function isSessionPlayer(player)
    return player and player.color == sessionColor
end

function commandNodePage(player, _, id)
    if not isSessionPlayer(player) or not panelRender then return end
    if id == "page_prev" then panelPage = panelPage - 1 end
    if id == "page_next" then panelPage = panelPage + 1 end
    panelRender()
end

local function setStartVisible(visible)
    self.editButton({index = 0, label = visible and "Start" or "",
        width = visible and 900 or 0, height = visible and 320 or 0})
end

function onLoad()
    self.setName("Kill Team Command Node")
    for _, object in ipairs(getObjectsWithTag("KTCommandNodeSlot-" .. self.getGUID())) do
        object.destruct()
    end
    self.createButton({label = "Start", click_function = "commandNodeStart", function_owner = self,
        position = {0, 0.65, -1.2}, width = 900, height = 320, font_size = 180,
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
            counts = {}
            panelPage = 1
            showRoster()
        end)
    end)
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

local function drawBase(object, raw)
    local width, depth = baseDimensions(raw)
    local points = {}
    for step = 0, 40 do
        local angle = step * 2 * math.pi / 40
        points[#points + 1] = {width * 0.5 * math.cos(angle), 0.6, depth * 0.5 * math.sin(angle)}
    end
    object.setVectorLines({{points = points, color = {0.3, 0.95, 0.7}, thickness = 0.04}})
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

    local slot = slots[selectedSlot]
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
                rows[#rows + 1] = '<Text preferredHeight="26" fontSize="16" color="#A8BEB7">Choose one</Text>'
                for optionIndex, option in ipairs(group) do
                    local selected = (slot.choices[groupIndex] or 1) == optionIndex
                    rows[#rows + 1] = button("option_" .. groupIndex .. "_" .. optionIndex,
                        "commandNodeSelectOption", (selected and "[x] " or "[ ] ") .. (option.label or "Option"))
                end
            end
        end
    end
    panel("Place models: " .. currentTeam.name, rows,
        button("confirm", "commandNodeConfirm", "Confirm", "#237A60")
        .. button("cancel", "commandNodeCancel", "Cancel"))
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
            local position = self.positionToWorld({(column - 2.5) * 3.5, 0.4, -4 - row * 3.5})
            local slot = {operative = operativeIndex, choices = {}, selectedSet = 1}
            slots[index] = slot
            local object = spawnObject({type = "BlockSquare", position = position, scale = {1, 0.08, 1},
                rotation = self.getRotation(), sound = false, callback_function = function(marker)
                    if version ~= sessionVersion then marker.destruct(); return end
                    marker.setLock(true)
                    marker.setName(index .. ". " .. operative.name)
                    marker.setColorTint({0.18, 0.38, 0.32})
                    marker.addTag("KTCommandNodeSlot-" .. self.getGUID())
                    marker.createButton({label = index .. ". " .. operative.name,
                        click_function = "commandNodeSlotLabel", function_owner = self,
                        position = {0, 0.7, 0}, width = 0, height = 0, font_size = 95,
                        font_color = {1, 1, 1}, scale = {1, 12.5, 1}})
                    drawBase(marker, operative.data.stats.Base)
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
    if not isSessionPlayer(player) then return end
    local index = tonumber(id:match("^slot_(%d+)$"))
    if index and slots[index] then
        selectedSlot = index
        panelPage = math.ceil((#slots + 1) / ROWS_PER_PAGE)
        showSlots()
    end
end

function commandNodeSelectSet(player, _, id)
    if not isSessionPlayer(player) then return end
    local index = tonumber(id:match("^set_(%d+)$"))
    local slot = slots[selectedSlot]
    local selection = operatives[slot.operative].data.selection
    if index and selection.exclusive_sets[index] then slot.selectedSet = index; showSlots() end
end

function commandNodeSelectOption(player, _, id)
    if not isSessionPlayer(player) then return end
    local group, option = id:match("^option_(%d+)_(%d+)$")
    group, option = tonumber(group), tonumber(option)
    local slot = slots[selectedSlot]
    local selection = operatives[slot.operative].data.selection
    if group and option and selection.groups[group] and selection.groups[group][option] then
        slot.choices[group] = option
        showSlots()
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
    local width, depth = baseDimensions(operatives[slot.operative].data.stats.Base)
    local center = marker.getPosition()
    local hits = Physics.cast({origin = center + Vector(0, 1, 0), direction = {0, 1, 0}, type = 3,
        size = {math.max(width + 0.4, 1.2), 3, math.max(depth + 0.4, 1.2)},
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
                return loaded.call("ktCommandNodeApply", {model = target, data = data, playerColor = sessionColor})
            end)
            loaded.destruct()
            activeHelper = nil
            if not called or type(result) ~= "table" or not result.applied then
                finishApply("Slot " .. index .. ": failed to apply stats; check the TTS log.")
                return
            end
            slot.done = true
            slot.modelGuid = targetGuid
            applyNext(index + 1, models)
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
        if not script then finishApply(errorMessage); return end
        if not script:find("function diffAndApply", 1, true)
            or not script:find("function rebuildDescription", 1, true)
            or not script:find("KTUI_MODELSCRIPT", 1, true) then
            finishApply("Invalid node loader script.")
            return
        end
        loaderScript = script
        applyNext(1, models)
    end)
end