local objects = {}
local spawnedSlots = {}
local messages = {}
local applied = {}
local nextGuid = 0
local hits = {}
local lastXml = ""
local callbacks = {}
local startButton
local applyAdapter
local helperScripts = {}
local extraCard
local extraCards = {}
local lastCast
local spawnedSupplies = {}
local supplyAttempts = 0
local supplyFailAt
local suppliesMissing = false
local counterSupported = false
local choicesSupported = false
local choiceOverride
local tacticNames = {"Aggressive", "Dueller", "Resolute", "Stealthy", "Mobile", "Hardy", "Sharpshooter", "Siege Specialist"}
local expectCardbox = false
local rawCardbox = false
local rawCardboxText = ' \r\n{"Name":"Custom_Model_Bag","Nickname":"Test cardbox","ContainedObjects":['
    .. '{"Name":"Custom_Model_Bag"},{"Name":"Custom_Dice"},{"Name":"Custom_Dice"},'
    .. '{"Name":"Custom_Dice"},{"Name":"Deck"}],"Description":"' .. string.rep("x", 600000) .. '"}'
local supplyTimeouts = {}
local supplyBox = {Name = "Custom_Model_Bag", Nickname = "Test cardbox", ContainedObjects = {
    {Name = "Custom_Model_Bag", Nickname = "Team tokens", Tags = {"KTCardsTokenBag"},
        LuaScript = "token-bag-script", ContainedObjects = {{Name = "Custom_Model_Infinite_Bag", Nickname = "Token dispenser"}}},
    {Name = "Custom_Dice", Nickname = "Team dice", Tags = {"KTDice_Team"}, LuaScript = "dice-script"},
    {Name = "Custom_Dice", Nickname = "Light dice", Tags = {"KTDice_Light"}},
    {Name = "Custom_Dice", Nickname = "Dark dice", Tags = {"KTDice_Dark"}},
    {Name = "Deck", Nickname = "Datacards", Tags = {"KTCardsDatacard"}},
}}

local function flushCallbacks()
    while #callbacks > 0 do
        local callback = table.remove(callbacks, 1)
        callback()
    end
end

local vectorMeta = {__add = function(left, right)
    return Vector(left.x + right.x, left.y + right.y, left.z + right.z)
end}

function Vector(x, y, z)
    return setmetatable({x = x, y = y, z = z}, vectorMeta)
end

local cardScript = [[
KTUI_MODELSCRIPT = "test"
MOVE_TOOL_CODE = "-- move-dash-regression"
SPRINT_TOOL_CODE = "-- sprint-leap-regression"
NODE_COUNTER_SETUP = [====[{"test":{"name":"Gore Tank"}}]====]
function ktCommandNodeAddCounters(params)
    assert(getObjectFromGUID(helperObject.guid) == helperObject)
    params.model.counterInstalls = (params.model.counterInstalls or 0) + 1
    params.model.script_state.operative_counter = {name = "Gore Tank", current = 0}
    Wait.frames(function()
        assert(getObjectFromGUID(helperObject.guid) == helperObject, "Counter helper destroyed before reload")
        params.model.reload()
    end, 10)
    return true
end
function rebuildDescription(data) return "Chosen loadout" end
function diffAndApply(model, data, color, replaceScript, modelScript)
    if not replaceScript then
        assert(KTUI_MODELSCRIPT_VERSION == nil, "Updates must not re-stamp the model script")
        model.updated = data
        return {"stats"}
    end
    assert(replaceScript == true)
    assert(type(modelScript) == "string")
    model.installedScript = modelScript
    assert(#model.buttons == 0 and #model.inputs == 0 and model.xml == "")
    model.scriptReplacements = (model.scriptReplacements or 0) + 1
    if model.noStatChanges then model.reload(); return {"script replaced"} end
    model.applied = data
    model.color = color
    model.loadedFront = JSON.decode(model.script_state).kt_front
    applied[#applied + 1] = model
    model.reload()
    return {"updated"}
end
]]

local cardData = {
    name = "ASSAULT INTERCESSOR GRENADIER",
    apl = 3, movement = '6"', save = "3+", wounds = 14,
    base_size = 32,
    weapons = {{name = "fixed"}, {name = "plasma"}, {name = "flamer"}},
    node = {
        weapon_types = {"melee", "ranged", "ranged"},
        weapon_rule_names = {},
        selection = {
            fixed = {0},
            groups = {{{label = "Plasma", weapons = {1}}, {label = "Flamer", weapons = {2}}}},
        },
    },
}
NODE_REPO_BASE_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/refs/heads/feature/command-node"
local index = {test = {team_url = "https://example.test/main/test-metadata"}}
index["../escape"] = {team_url = "https://example.test/main/escape"}
for teamNumber = 1, 49 do
    index["zzz-team-" .. teamNumber] = {team_url = "https://example.test/main/test-metadata"}
end

local function copy(value)
    if type(value) ~= "table" then return value end
    local result = {}
    for key, item in pairs(value) do result[key] = copy(item) end
    return result
end

JSON = {
    encode = function(value)
        assert(not (rawCardbox and type(value) == "table" and value.Nickname == "Test cardbox"),
            "Bare cardbox must not be re-encoded in Lua")
        return copy(value)
    end,
    decode = function(value)
        assert(value ~= rawCardboxText, "Bare cardbox must not be decoded in Lua")
        if value == "team-index" then return index end
        if value == "empty-index" then return {} end
        if value == '{"test":{"name":"Gore Tank"}}' then
            if choicesSupported then
                if choiceOverride then return {test = copy(choiceOverride)} end
                local options = {}
                for _, name in ipairs(tacticNames) do options[#options + 1] = {name = name} end
                return {test = {name = "Chapter Tactics", select = 2, kind = "choice", options = options}}
            end
            return counterSupported and {test = {name = "Gore Tank"}} or {}
        end
        if value == "team-metadata" then return {
            team = "test", team_data = {url = "https://example.test/main/test-data", hash = "abc123"},
            box = {url = "https://example.test/main/output/test/tts_objects/Test.json", hash = "def456"},
        } end
        if value == "cardbox" then return copy(supplyBox) end
        if value == "test-roster" then
            local cards = {copy(cardData)}
            if extraCard then cards[#cards + 1] = copy(extraCard) end
            for _, card in ipairs(extraCards) do cards[#cards + 1] = copy(card) end
            local options = {}
            for index, name in ipairs(tacticNames) do options[#options + 1] = {name = name, text = "Tactic text " .. index} end
            return {team = "test", datacards = cards, faction_rules = {{options = options}}}
        end
        return value
    end,
}
local requests = {}
local indexMissing = false
local indexEmpty = false
local metadataMissing = false
local loaderMissing = false
local loaderOutdated = false
local helperNeverReady = false
local loaderMetadataTruncated = false
local loaderPadding = string.rep("-- loader padding\n", 12000)
local deferRequest = false
WebRequest = {get = function(url, callback)
    assert(expectCardbox or not url:find("/tts_objects/Test.json", 1, true), "Unselected cardbox must not be downloaded")
    requests[#requests + 1] = url
    local text
    if url:find("team%-urls%.json") and not indexMissing then
        text = indexEmpty and "empty-index" or "team-index"
    elseif url:find("/output/test/test-object-urls.json", 1, true) and not metadataMissing then text = "team-metadata"
    elseif url:find("/output/test/data/test-team-data.json", 1, true) then text = "test-roster"
    elseif url:find("/output/test/tts_objects/Test.json", 1, true) and not suppliesMissing then
        text = rawCardbox and rawCardboxText or "cardbox"
    elseif url:find("command%-node%-loader%.lua") and not loaderMissing then
        text = loaderOutdated and cardScript:gsub("color, replaceScript, modelScript%)", "color)") or cardScript
        if loaderMetadataTruncated then text = text:gsub("%]====%]", "") end
        text = loaderPadding .. text
    end
    local response = {response_code = text and 200 or 404, is_error = not text, text = text, error = ""}
    if deferRequest then
        callbacks[#callbacks + 1] = function() callback(response) end
    else
        callback(response)
    end
end}
Physics = {cast = function(parameters)
    lastCast = parameters
    assert(parameters.size[1] >= 60 / 25.4 and parameters.size[3] >= 60 / 25.4)
    return hits[string.format("%.1f,%.1f", parameters.origin.x, parameters.origin.z)] or {}
end}
Wait = {
    frames = function(callback) callbacks[#callbacks + 1] = callback end,
    condition = function(callback, check, timeout, onTimeout)
        assert(timeout and onTimeout)
        callbacks[#callbacks + 1] = function()
            if check() then callback() else onTimeout() end
        end
    end,
    time = function(callback, seconds)
        assert(seconds == 30)
        supplyTimeouts[#supplyTimeouts + 1] = callback
    end,
}
function broadcastToColor(message) messages[#messages + 1] = message end
function getObjectsWithTag() return {} end
function getObjectFromGUID(guid) return objects[guid] end

local function installModelRefresh(object)
    object.refreshCalls = {}
    object.call = function(name, parameters)
        assert(objects[object.guid] == object, "Refresh used a stale model instance")
        object.refreshCalls[#object.refreshCalls + 1] = name
        if name == "loadState" then
            object.loadedFront = JSON.decode(object.script_state).kt_front
        elseif name == "refreshUI" then
            assert(object.refreshCalls[#object.refreshCalls - 1] == "loadState")
            object.uiVisible = true
        elseif name == "refreshVectors" then
            assert(parameters == true, "Base refresh must not rotate the model")
        else
            error("Unexpected model call: " .. name)
        end
    end
end

local function newObject(kind, position)
    nextGuid = nextGuid + 1
    local guid = tostring(nextGuid)
    local object = {type = kind, position = position, guid = guid}
    installModelRefresh(object)
    object.buttons = {}
    object.inputs = {}
    object.clearButtons = function() object.buttons = {}; object.buttonsCleared = true end
    object.clearInputs = function() object.inputs = {}; object.inputsCleared = true end
    object.UI = {setXml = function(xml) object.xml = xml end}
    objects[guid] = object
    object.getGUID = function()
        assert(not object.spawning, "GUID requested before spawn completed")
        return guid
    end
    object.getPosition = function() return position end
    object.scale = {x = 1, y = 1, z = 1}
    object.getScale = function() return object.scale end
    object.setScale = function(scale)
        object.scale = {x = scale[1], y = scale[2], z = scale[3]}
    end
    object.getBoundsNormalized = function()
        return {size = {x = object.scale.x, y = object.scale.y, z = 2 * object.scale.z}}
    end
    object.rotation = {x = 0, y = 0, z = 0}
    object.getRotation = function() return object.rotation end
    object.setRotation = function(rotation)
        object.rotationCalls = (object.rotationCalls or 0) + 1
        object.rotation = {x = rotation[1], y = rotation[2], z = rotation[3]}
    end
    object.setLock = function() end
    object.setName = function() end
    object.setColorTint = function(tint) object.tint = tint end
    object.addTag = function() end
    object.createButton = function(parameters) object.buttons[#object.buttons + 1] = parameters end
    object.editButton = function(parameters)
        for key, value in pairs(parameters) do object.buttons[parameters.index + 1][key] = value end
    end
    object.setVectorLines = function(lines) object.lines = lines end
    object.setInvisibleTo = function() end
    object.setGMNotes = function() end
    object.setLuaScript = function(script)
        object.script = script
        helperScripts[#helperScripts + 1] = script
    end
    object.reload = function()
        if not object.script then
            object.frontReloads = (object.frontReloads or 0) + 1
            object.loadedFront = JSON.decode(object.script_state).kt_front
            if object.recreateOnReload then
                local replacement = copy(object)
                replacement.uiVisible = false
                installModelRefresh(replacement)
                objects[guid] = replacement
                return replacement
            end
            return object
        end
        local environment = setmetatable({applied = applied, helperObject = object}, {__index = _G})
        assert(load(object.script, "helper", "t", environment))()
        applyAdapter = environment.ktCommandNodeApply
        object.call = function(name, parameters) return environment[name](parameters) end
        object.getVar = function(name) if not helperNeverReady then return environment[name] end end
    end
    object.destruct = function() objects[guid] = nil end
    return object
end

function spawnObjectJSON(parameters)
    supplyAttempts = supplyAttempts + 1
    if supplyAttempts == supplyFailAt then return nil end
    local data = parameters.json
    if type(data) == "string" then
        assert(data == rawCardboxText, "Raw downloaded JSON must reach TTS unchanged")
        data = supplyBox
    end
    local object = newObject(data.Name, parameters.position)
    object.spawnJson = parameters.json
    local rotation = parameters.rotation
    object.rotation = {x = rotation.x or rotation[1], y = rotation.y or rotation[2], z = rotation.z or rotation[3]}
    object.data = copy(data)
    spawnedSupplies[#spawnedSupplies + 1] = object
    return object
end

function spawnObject(parameters)
    local object = newObject(parameters.type, parameters.position)
    object.setScale(parameters.scale)
    object.rotation = parameters.rotation or {x = 0, y = 0, z = 0}
    object.spawning = true
    if parameters.scale[2] == 0.08 then spawnedSlots[#spawnedSlots + 1] = object end
    callbacks[#callbacks + 1] = function()
        object.spawning = false
        if parameters.callback_function then parameters.callback_function(object) end
    end
    return object
end

local nodeScale = {x = 2, y = 0.2, z = 2}
local nodeYaw = 0
local nodeLines
local nodeTag
self = {
    UI = {setXml = function(xml) lastXml = xml end},
    getGUID = function() return "node" end,
    addTag = function(tag) nodeTag = tag end,
    setName = function() end,
    createButton = function(parameters) startButton = parameters end,
    editButton = function(parameters)
        for key, value in pairs(parameters) do startButton[key] = value end
    end,
    positionToWorld = function(position)
        return Vector(position[1] * nodeScale.x, 1 + position[2] * nodeScale.y, position[3] * nodeScale.z)
    end,
    getPosition = function() return Vector(0, 1, 0) end,
    getRotation = function() return {x = 0, y = nodeYaw, z = 0} end,
    setVectorLines = function(lines) nodeLines = lines end,
    getScale = function() return nodeScale end,
    getBoundsNormalized = function()
        return {size = {x = 2 * nodeScale.x, y = 2 * nodeScale.y, z = 2 * nodeScale.z}}
    end,
}

local function assertPanelAboveNode()
    local center = assert(tonumber(lastXml:match('position="0 ([%d.]+) %-80"')))
    local height = assert(tonumber(lastXml:match('height="(%d+)"')))
    local scale = assert(tonumber(lastXml:match('scale="([%d.]+)')))
    local nearEdge = (center - height * scale * 0.5) / 100 * nodeScale.z
    assert(math.abs(nearEdge - self.getBoundsNormalized().size.z * 0.5) < 0.001)
    assert(scale < 1)
    assert(height >= 124 and height <= 560)
    return height
end

local originalMatch = string.match
string.match = function(text, pattern, ...)
    assert(#text < 100000, "Do not pattern-match the entire loader: TTS reports pattern too complex")
    return originalMatch(text, pattern, ...)
end

dofile("config/defaults/tts-script/command-node.lua")
local converted = assert(commandNodeModelData({
    name = "GUNNER", apl = 2, movement = '12\226\128\179', save = "4+", wounds = 8, base_size = 32,
    keywords = {"TEST"}, weapons = {{name = "Gun & blade", attacks = "4", hit = "3+", damage = "3/4"}},
    passive_abilities = {{name = " Steady ", description = " Ready "}},
    node = {weapon_types = {"ranged"}, weapon_rules = {}, selection = {groups = {}}},
}))
assert(converted.stats.Move == 12 and converted.stats.Save == 4 and converted.stats.Base == 32)
assert(converted.weapons[1].name == "[1E87FF]R[-] Gun and blade")
assert(converted.abilities[1].name == "Steady" and converted.abilities[1].text == "Ready")
assert(commandNodeModelData({name = "Missing"}) == nil)
local missingStats, missingReason = commandNodeModelData({
    name = "NO MOVE", apl = 2, save = "4+", wounds = 8,
    weapons = {}, node = {weapon_types = {}, weapon_rule_names = {}},
})
assert(missingStats == nil and missingReason:find("Missing Move for NO MOVE", 1, true))
local longAbility = string.rep("Grit. ", 1200)
local trimmedAbility = string.rep("Grit. ", 1199) .. "Grit."
local unicodeData = assert(commandNodeModelData({
    name = "HEARTHKYN D\195\148ZR",
    apl = 2, movement = '5"', save = "4+", wounds = 8,
    weapons = {},
    passive_abilities = {{name = "\226\128\152Ancient Oath\226\128\153", description = "  " .. longAbility .. "  "}},
    node = {weapon_types = {}, weapon_rule_names = {}},
}))
assert(unicodeData.name == "HEARTHKYN D\195\148ZR")
assert(unicodeData.abilities[1].name:find("Ancient Oath", 1, true))
assert(#unicodeData.abilities[1].name == 14)
assert(unicodeData.abilities[1].text == trimmedAbility)
local alternatives = {
    weapons = {"fixed", "pistol", "blade", "plasma"},
    selection = {
        fixed = {0},
        groups = {{{weapons = {1}}}, {{weapons = {2}}}, {{weapons = {3}}}},
        exclusive_sets = {{0, 1}, {2}},
    },
}
assert(table.concat(selectedLoadoutWeapons(alternatives, {}, 1), ",") == "fixed,pistol,blade")
assert(table.concat(selectedLoadoutWeapons(alternatives, {}, 2), ",") == "fixed,plasma")
assert(selectedLoadoutWeapons(alternatives, {}, 3) == nil)
assert(selectedLoadoutWeapons({weapons = {"one"}, selection = {
    groups = {{{weapons = {8}}}},
}}, {}, 1) == nil)
onLoad()
assert(nodeTag == "KTCommandNode")
assert(nodeLines[1].points[2][3] > nodeLines[1].points[1][3])
assert(nodeLines[1].points[3][1] < 0 and nodeLines[1].points[5][1] > 0)
assert(startButton.label == "New team")
assert(startButton.position[3] < -1)
assert(math.abs(startButton.position[2] - nodeLines[1].points[1][2]) < 0.001)
commandNodeStart(nil, "White")
assert(startButton.label == "" and startButton.width == 0 and startButton.height == 0)
assert(not lastXml:find("<VerticalScrollView", 1, true))
assert(not lastXml:find('allowDragging="true"', 1, true))
local teamPanelHeight = assertPanelAboveNode()
assert(teamPanelHeight == 558)
assert(lastXml:find('alignment="UpperCenter" preferredHeight="48">Choose a team</Text>', 1, true))
assert(lastXml:find('minHeight="28" preferredHeight="28" flexibleHeight="0" childForceExpandHeight="false"', 1, true))
assert(lastXml:find('preferredWidth="36" flexibleWidth="0" minHeight="28" preferredHeight="28" flexibleHeight="0"', 1, true))
assert(lastXml:find('interactable="false">&lt;</Button>', 1, true))
assert(not lastXml:find('tooltip=', 1, true))
assert(lastXml:find('id="team_1"', 1, true))
assert(lastXml:find('id="team_20"', 1, true))
assert(not lastXml:find('id="team_21"', 1, true))
local _, teamRows = lastXml:gsub('<HorizontalLayout spacing="6" preferredHeight="34"', "")
assert(teamRows == 10)
for _ = 1, 2 do commandNodePage({color = "White"}, nil, "page_next") end
assert(lastXml:find('id="team_50"', 1, true))
assert(not lastXml:find('id="team_51"', 1, true))
for _ = 1, 2 do commandNodePage({color = "White"}, nil, "page_prev") end
commandNodeChooseTeam({color = "White"}, nil, "team_1")
assert(requests[2]:find(NODE_REPO_BASE_URL .. "/output/test/test-object-urls.json", 1, true) == 1)
assert(requests[3] == NODE_REPO_BASE_URL .. "/output/test/data/test-team-data.json?v=abc123")
assert(#requests == 4)
assert(not lastXml:find('id="supplies"', 1, true))
assert(not lastXml:find('id="setup_tokens"', 1, true) and not lastXml:find('id="setup_dice"', 1, true))
assert(lastXml:find('id="setup_cardbox" onClick="commandNodeToggleCardbox"', 1, true))
assert(lastXml:find('colors="#34454A|#56686D|#293336|#333333" textColor="#FFFFFF">Add cardbox (tokens + dice)</Button>', 1, true))
assert(lastXml:find('<VerticalLayout preferredHeight="34" flexibleHeight="0" spacing="6"', 1, true))
assert(not lastXml:find('id="setup_rules"', 1, true))
commandNodeSpawnSupplies({color = "Red"})
assert(#requests == 4 and #spawnedSupplies == 0)
commandNodeSpawnSupplies({color = "White"})
assert(#requests == 4 and #spawnedSupplies == 0)
commandNodeToggleCardbox({color = "Red"})
assert(lastXml:find('>Add cardbox (tokens + dice)</Button>', 1, true))
commandNodeToggleCardbox({color = "White"})
assert(lastXml:find('colors="#237A60|#56686D|#293336|#333333" textColor="#FFFFFF">Cardbox added (tokens + dice)</Button>', 1, true))
expectCardbox = true
commandNodeSpawnSupplies({color = "White"})
assert(requests[5]:find(NODE_REPO_BASE_URL .. "/output/test/tts_objects/Test.json?v=", 1, true) == 1)
assert(#spawnedSupplies == 1)
assert(spawnedSupplies[1].data.Nickname == "Test cardbox" and #spawnedSupplies[1].data.ContainedObjects == 5)
assert(spawnedSupplies[1].position.x > 8 and spawnedSupplies[1].position.x < 9)
assert(spawnedSupplies[1].position.z == 3 and spawnedSupplies[1].rotation.y == 0)
assert(messages[#messages] == "Team cardbox spawned.")
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == 1)
expectCardbox = false
assert(assertPanelAboveNode() < teamPanelHeight)
assert(not lastXml:find('id="page_next"', 1, true))
assert(lastXml:find('<HorizontalLayout preferredHeight="42" flexibleHeight="0" spacing="4" padding="10 4 3 3" childForceExpandWidth="false"', 1, true))
assert(lastXml:find('<Text flexibleWidth="1" fontSize="16" color="#FFFFFF" alignment="MiddleLeft" horizontalOverflow="Truncate">ASSAULT INTERCESSOR GRENADIER</Text><Button id="minus_1"', 1, true))
assert(lastXml:find('preferredWidth="48" flexibleWidth="0"', 1, true))
assert(lastXml:find('childAlignment="MiddleLeft" color="#00000000">', 1, true))
assert(lastXml:find('preferredHeight="42" flexibleHeight="0" childForceExpandHeight="false">', 1, true))
assert(not lastXml:find('Loadout', 1, true))
assert(not lastXml:find('id="option_', 1, true))
commandNodeChangeCount({color = "White"}, nil, "plus_1")
commandNodeChangeCount({color = "White"}, nil, "plus_1")
commandNodeCreateSlots({color = "White"})
assert(#spawnedSlots == 2)
flushCallbacks()
assert(spawnedSlots[1].buttons[1].label == "1. ASSAULT\nINTERCESSOR\nGRENADIER")
assert(spawnedSlots[1].buttons[1].font_size == 80)
assert(spawnedSlots[1].tooltip == false)
for _, marker in ipairs(spawnedSlots) do
    local bounds = marker.getBoundsNormalized().size
    assert(math.abs(bounds.x * 25.4 - 60) < 0.001 and math.abs(bounds.z * 25.4 - 60) < 0.001)
    local scale = marker.getScale()
    assert(math.abs(marker.buttons[1].scale[1] * scale.x - 1) < 0.001)
    assert(math.abs(marker.buttons[2].scale[3] * scale.z - 1) < 0.001)
    assert(marker.lines == nil)
    assert(marker.tint[1] == 0 and marker.tint[2] == 0 and marker.tint[3] == 0)
end
assert(lastXml:find("Place models on tiles:", 1, true))
assert(lastXml:find('horizontalOverflow="Truncate">1. ASSAULT INTERCESSOR GRENADIER</Text><Button id="slot_1" onClick="commandNodeSelectSlot"', 1, true))
assert(lastXml:find('id="slot_2" onClick="commandNodeSelectSlot" minHeight="34" preferredWidth="170" flexibleWidth="0"', 1, true))
assert(lastXml:find('>Choose loadout</Button>', 1, true))
assert(lastXml:find('id="slots_back" onClick="commandNodeSlotsBack"', 1, true))
assert(spawnedSlots[1].buttons[2].label == "Choose loadout" and spawnedSlots[1].buttons[3].label == "All weapons")
assert(spawnedSlots[1].buttons[1].position[3] < 0 and spawnedSlots[1].buttons[3].position[3] > 0)
assert(lastXml:find('childAlignment="MiddleLeft" color="#FFFFFF14">', 1, true))
for line in spawnedSlots[1].buttons[1].label:gmatch("[^\n]+") do assert(#line <= 16) end
assert(math.abs((spawnedSlots[1].position.x - spawnedSlots[2].position.x) - (70 / 25.4)) < 0.001)
assert(math.abs(spawnedSlots[1].position.x + spawnedSlots[2].position.x) < 0.001)
assert(spawnedSlots[1].position.z + 30 / 25.4 < -self.getBoundsNormalized().size.z * 0.5)
assertPanelAboveNode()
assert(not lastXml:find('id="option_', 1, true))
assert(spawnedSlots[1].buttons[2].click_function == "commandNodeSlotLoadout")
assert(spawnedSlots[1].buttons[2].width > 0 and spawnedSlots[1].buttons[2].height > 0)
commandNodeSlotLoadout(spawnedSlots[1], "Red")
assert(not lastXml:find('id="option_', 1, true))
commandNodeSlotLoadout(spawnedSlots[1], "White")
assertPanelAboveNode()
assert(assertPanelAboveNode() < teamPanelHeight)
assert(not lastXml:find('id="page_next"', 1, true))
assert(lastXml:find('onClick="commandNodeSelectOption"', 1, true))
assert(lastXml:find(">Loadout: all weapons until you choose</Text>", 1, true) and not lastXml:find("[x]", 1, true))
assert(lastXml:find('id="loadout_all" onClick="commandNodeLoadoutAll"', 1, true))
commandNodeSelectOption({color = "White"}, nil, "option_1_2")
assert(lastXml:find('[x] Flamer', 1, true))
assert(spawnedSlots[1].buttons[2].label == "Change loadout" and spawnedSlots[1].buttons[3].label == "Flamer")
commandNodeLoadoutDone({color = "White"})
assert(lastXml:find('id="confirm"', 1, true))
assert(lastXml:find('id="slot_1" onClick="commandNodeSelectSlot" minHeight="34" preferredWidth="170" flexibleWidth="0" preferredHeight="34" flexibleHeight="0" fontSize="17" colors="#34454A|#56686D|#293336|#333333" textColor="#FFFFFF">Change loadout</Button>', 1, true))
assert(lastXml:find('>Choose loadout</Button>', 1, true))
commandNodeSlotLoadout(spawnedSlots[2], "White")
assert(lastXml:find('[ ] Plasma', 1, true) and not lastXml:find('[x]', 1, true))
commandNodeSelectOption({color = "White"}, nil, "option_1_1")
assert(lastXml:find('[x] Plasma', 1, true))
commandNodeLoadoutDone({color = "White"})
assert(spawnedSlots[2].buttons[2].label == "Change loadout" and spawnedSlots[2].buttons[3].label == "Plasma")
assert(not lastXml:find('>Choose loadout</Button>', 1, true))
commandNodeSlotLoadout(spawnedSlots[1], "White")
assert(lastXml:find('[x] Flamer', 1, true))
commandNodeLoadoutDone({color = "White"})

commandNodeConfirm({color = "White"})
assert(#applied == 0 and messages[#messages]:find("exactly one model", 1, true))

local modelOne = newObject("Custom_Model", Vector(0, 1, 0))
local modelTwo = newObject("Figurine", Vector(0, 1, 0))
modelOne.rotation = {x = 10, y = 27, z = 20}
modelTwo.rotation = {x = 0, y = 47, z = 0}
modelTwo.script_state = {kt_front = 180, base = {x = 32, z = 32}, owner = "absent-steam"}
modelOne.script_state = {owner = "white-steam"}
modelTwo.buttons = {{label = "Old wounds UI"}}
modelTwo.inputs = {{value = "Old input"}}
modelTwo.xml = '<Panel id="old_layout" />'
modelTwo.recreateOnReload = true
nodeYaw = 90
local first = spawnedSlots[1].getPosition()
local second = spawnedSlots[2].getPosition()
local firstKey = string.format("%.1f,%.1f", first.x, first.z)
local secondKey = string.format("%.1f,%.1f", second.x, second.z)
hits[firstKey] = {{hit_object = modelOne}}
hits[secondKey] = {{hit_object = modelOne}}
commandNodeConfirm({color = "White"})
assert(#applied == 0 and messages[#messages]:find("more than one slot", 1, true))

hits[secondKey] = {{hit_object = modelTwo}}
local requestsBeforeConfirm = #requests
helperNeverReady = true
commandNodeConfirm({color = "White"})
flushCallbacks()
assert(#applied == 0 and messages[#messages]:find("helper did not load", 1, true))
assert(modelOne.rotation.y == 27 and modelTwo.rotation.y == 47)
assert(#modelTwo.buttons == 1 and #modelTwo.inputs == 1 and not modelTwo.buttonsCleared)
assert(lastXml:find("Place models on tiles:", 1, true))
helperNeverReady = false
local helpersBeforeConfirm = #helperScripts
commandNodeConfirm({color = "White"})
flushCallbacks()
assert(#helperScripts == helpersBeforeConfirm + 1, "All models must share one stats helper")
assert(#requests == requestsBeforeConfirm, "Confirm must reuse the loader downloaded with the team")
assert(#applied == 2, "Applied " .. #applied .. ": " .. tostring(messages[#messages]))
assert(modelOne.applied.weapons[1].plain_name == "fixed" and modelOne.applied.weapons[2].plain_name == "flamer")
assert(modelTwo.applied.weapons[1].plain_name == "fixed" and modelTwo.applied.weapons[2].plain_name == "plasma")
assert(modelOne.color == "White" and modelTwo.color == "White")
assert(modelOne.rotation.y == 27 and modelOne.rotation.x == 10 and modelOne.rotation.z == 20)
assert(modelTwo.rotation.y == 47 and modelTwo.rotation.x == 0 and modelTwo.rotation.z == 0)
assert(not modelOne.rotationCalls and not modelTwo.rotationCalls)
assert(modelOne.script_state.kt_front == 63 and modelOne.loadedFront == 63)
assert(modelTwo.script_state.kt_front == 43 and modelTwo.loadedFront == 43)
assert(modelOne.script_state.uiAngle == 297 and modelTwo.script_state.uiAngle == 317)
assert(modelOne.script_state.kt_node_ui and modelTwo.script_state.kt_node_ui)
assert(modelOne.scriptReplacements == 1 and modelTwo.scriptReplacements == 1)
assert(modelOne.installedScript:find("-- START KT_MOVE_TOOL_V1 --", 1, true))
assert(modelOne.installedScript:find("move-dash-regression", 1, true))
assert(not modelOne.installedScript:find("sprint-leap-regression", 1, true))
assert(modelTwo.script_state.base.x == 32 and modelTwo.script_state.base.z == 32)
assert(modelTwo.script_state.owner == nil and modelOne.script_state.owner == nil)
assert(modelTwo.buttonsCleared and modelTwo.inputsCleared and modelTwo.xml == "")
assert((modelOne.rotation.y + modelOne.script_state.kt_front) % 360 == nodeYaw)
assert((modelTwo.rotation.y + modelTwo.script_state.kt_front) % 360 == nodeYaw)
local refreshedModelTwo = objects[modelTwo.guid]
assert(refreshedModelTwo ~= modelTwo and refreshedModelTwo.uiVisible)
assert(refreshedModelTwo.loadedFront == 43 and not refreshedModelTwo.rotationCalls)
assert(table.concat(refreshedModelTwo.refreshCalls, ",") == "loadState,refreshUI,refreshVectors")
assert(modelOne.uiVisible and table.concat(modelOne.refreshCalls, ",") == "loadState,refreshUI,refreshVectors")
assert(not objects[spawnedSlots[1].guid] and not objects[spawnedSlots[2].guid])
assert(startButton.label == "New team" and startButton.width == 900)

assert(modelOne.installedScript:find('node.call("commandNodeUpdateModel"', 1, true))
assert(modelOne.installedScript:find("function updateStats", 1, true) < modelOne.installedScript:find("-- START KT_MOVE_TOOL_V1 --", 1, true))
local hookStart = modelOne.installedScript:find("local extenderUpdateStats", 1, true)
local hookCode = modelOne.installedScript:sub(hookStart, modelOne.installedScript:find("\n-- START KT_MOVE_TOOL_V1", 1, true))
local hookCalls, hookMenu, hookOwner, nodeCalls = {}, {}, nil, {}
local hookEnvironment = setmetatable({
    updateStats = function(color) hookCalls[#hookCalls + 1] = "extender:" .. color end,
    onLoad = function() hookMenu[#hookMenu + 1] = "Update stats" end,
    getOwningPlayer = function() return hookOwner and {color = "White"} or nil end,
    setOwningPlayer = function(owner) hookOwner = owner end,
    saveState = function() hookCalls[#hookCalls + 1] = "save" end,
    refreshVectors = function(norotate) assert(norotate == true) end,
    Player = {White = {steam_id = "white-steam"}, Red = {steam_id = ""}},
    getObjectsWithTag = function(tag)
        assert(tag == "KTCommandNode")
        return {{call = function(name, parameters) nodeCalls[#nodeCalls + 1] = {name, parameters} end}}
    end,
    self = {
        getGUID = function() return "model-guid" end,
        addContextMenuItem = function(label) hookMenu[#hookMenu + 1] = label end,
    },
}, {__index = _G})
assert(load(hookCode, "hook", "t", hookEnvironment))()
hookEnvironment.onLoad()
assert(table.concat(hookMenu, ",") == "Update stats,Reload from description")
hookEnvironment.reloadFromDescription("Red")
assert(hookOwner == nil and hookCalls[1] == "extender:Red")
hookEnvironment.reloadFromDescription("White")
assert(hookOwner == "white-steam" and table.concat(hookCalls, ",") == "extender:Red,save,extender:White")
hookEnvironment.updateStats("White")
assert(#hookCalls == 3 and nodeCalls[1][1] == "commandNodeUpdateModel")
assert(nodeCalls[1][2].guid == "model-guid" and nodeCalls[1][2].color == "White")
local sourceOne = modelOne.script_state.kt_source
assert(sourceOne.team == "test" and sourceOne.operative == "ASSAULT INTERCESSOR GRENADIER")
assert(sourceOne.loadout.choices[1] == 2 and sourceOne.loadout.set == 1)
assert(refreshedModelTwo.script_state.kt_source.loadout.choices[1] == 1)
cardData.wounds = 15
local requestsBeforeUpdate = #requests
local replacementsBeforeUpdate = modelOne.scriptReplacements
commandNodeUpdateModel({guid = modelOne.guid, color = "White"})
assert(messages[#messages]:find("Updating ASSAULT INTERCESSOR GRENADIER", 1, true))
flushCallbacks()
assert(#requests == requestsBeforeUpdate + 3)
assert(modelOne.updated.stats.Wounds == 15)
assert(#modelOne.updated.weapons == 2 and modelOne.updated.weapons[2].plain_name == "flamer")
assert(modelOne.updated.description == "Chosen loadout")
assert(modelOne.scriptReplacements == replacementsBeforeUpdate)
assert(messages[#messages] == "ASSAULT INTERCESSOR GRENADIER updated with the latest data.")
cardData.wounds = 14
local unlinkedModel = newObject("Figurine", Vector(0, 1, 0))
unlinkedModel.script_state = {wounds = 3}
commandNodeUpdateModel({guid = unlinkedModel.guid, color = "White"})
assert(messages[#messages]:find("Set this model up once more", 1, true) and not unlinkedModel.updated)
modelOne.script_state.kt_source.operative = "RETIRED OPERATIVE"
commandNodeUpdateModel({guid = modelOne.guid, color = "White"})
flushCallbacks()
assert(messages[#messages] == "RETIRED OPERATIVE is no longer in the Test data.")
modelOne.script_state.kt_source.operative = "ASSAULT INTERCESSOR GRENADIER"
deferRequest = true
commandNodeUpdateModel({guid = modelOne.guid, color = "White"})
commandNodeUpdateModel({guid = modelOne.guid, color = "White"})
assert(messages[#messages]:find("busy", 1, true))
deferRequest = false
flushCallbacks()
assert(messages[#messages]:find("updated with the latest data", 1, true))

local frontOnlyModel = newObject("Figurine", Vector(0, 1, 0))
frontOnlyModel.rotation = {x = 0, y = 350, z = 0}
frontOnlyModel.script_state = {kt_front = 180, wounds = 4}
frontOnlyModel.noStatChanges = true
local frontOnlyParams = {model = frontOnlyModel, data = {}, playerColor = "White", heading = 15}
assert(applyAdapter(frontOnlyParams).applied)
assert(frontOnlyModel.script_state.kt_front == 25 and frontOnlyModel.loadedFront == 25)
assert(frontOnlyModel.script_state.wounds == 4 and frontOnlyModel.frontReloads == 1)
assert(frontOnlyModel.rotation.y == 350 and not frontOnlyModel.rotationCalls)
assert(applyAdapter(frontOnlyParams).applied)
assert(frontOnlyModel.frontReloads == 2 and frontOnlyModel.scriptReplacements == 2)
frontOnlyParams.data.keywords = {"mOuNtEd"}
assert(applyAdapter(frontOnlyParams).applied)
assert(frontOnlyModel.installedScript:find("-- START KT_SPRINT_TOOL_V1 --", 1, true))
assert(frontOnlyModel.installedScript:find("sprint-leap-regression", 1, true))
assert(not frontOnlyModel.installedScript:find("move-dash-regression", 1, true))
frontOnlyParams.data.keywords = {}
assert(applyAdapter(frontOnlyParams).applied)
assert(frontOnlyModel.installedScript:find("move-dash-regression", 1, true))
assert(not frontOnlyModel.installedScript:find("sprint-leap-regression", 1, true))
local _, movementBlocks = frontOnlyModel.installedScript:gsub("%-%- START KT_MOVE_TOOL_V1 %-%-", "")
assert(movementBlocks == 1 and frontOnlyModel.frontReloads == 4)

local uiEnvironment = setmetatable({
    state = {kt_node_ui = true, uiAngle = 270},
    self = {getScale = function() return {x = 2, y = 1, z = 3} end},
    getUIPosition = function() return "0 30 -200" end,
}, {__index = _G})
assert(loadfile("config/defaults/tts-script/ktui-extension.lua", "t", uiEnvironment))()
local horizontal, vertical, depth = uiEnvironment.getUIPosition():match("(%S+) (%S+) (%S+)")
assert(math.abs(tonumber(horizontal) - 45) < 0.001 and math.abs(tonumber(vertical)) < 0.001)
assert(depth == "-200")
for _, front in ipairs({0, 43, 63, 90, 180, 270}) do
    uiEnvironment.state.uiAngle = (-front) % 360
    local offsetX, offsetZ = uiEnvironment.getUIPosition():match("(%S+) (%S+)")
    local modelHeading = (90 - front) % 360
    local yaw = math.rad(modelHeading)
    local worldX = tonumber(offsetX) * 2 * math.cos(yaw) + tonumber(offsetZ) * 3 * math.sin(yaw)
    local worldZ = -tonumber(offsetX) * 2 * math.sin(yaw) + tonumber(offsetZ) * 3 * math.cos(yaw)
    assert(math.abs(worldX - 90) < 0.001 and math.abs(worldZ) < 0.001)
    assert((modelHeading - uiEnvironment.state.uiAngle) % 360 == 90)
end
uiEnvironment.state.kt_node_ui = nil
assert(uiEnvironment.getUIPosition() == "0 30 -200")

local loaderEnvironment = setmetatable({
    KTUI_MODELSCRIPT = "latest composed extender",
    KTUI_MODELSCRIPT_VERSION = "latest",
    Player = {White = {steam_id = "white-steam"}, Red = {steam_id = ""}},
}, {__index = _G})
assert(loadfile("config/defaults/tts-script/datacard-load-stats.lua", "t", loaderEnvironment))()
for _, kind in ipairs({"plain", "managed", "extender"}) do
    local model = {
        script_state = {owner = "existing-owner", kt_front = 25, uiAngle = 335, wounds = 4},
        tags = {KTUIMini = kind ~= "plain", KTUIMiniDatacard = kind == "managed"},
        reloads = 0,
    }
    model.hasTag = function(tag) return model.tags[tag] end
    model.addTag = function(tag) model.tags[tag] = true end
    model.getVar = function() return "latest" end
    model.setLuaScript = function(script) model.script = script end
    model.reload = function() model.reloads = model.reloads + 1 end
    if kind ~= "plain" then
        loaderEnvironment.diffAndApply(model, {stats = {}}, "Red")
        assert(not model.script and model.reloads == 0 and model.script_state.owner == "existing-owner")
    end
    loaderEnvironment.diffAndApply(model, {stats = {}}, "White", true)
    assert(model.script == "latest composed extender" and model.reloads == 1)
    assert(model.tags.KTUIMini and model.tags.KTUIMiniDatacard)
    assert(model.script_state.owner == "white-steam" and model.script_state.wounds == 4)
    assert(model.script_state.kt_front == 25 and model.script_state.uiAngle == 335)
    loaderEnvironment.diffAndApply(model, {stats = {}}, "White", true, "composed extender with movement")
    assert(model.reloads == 2 and model.script == "composed extender with movement")
end

spawnedSlots = {}
nodeScale = {x = 3, y = 0.2, z = 1.5}
commandNodeStart(nil, "White")
commandNodeChooseTeam({color = "White"}, nil, "team_1")
for _ = 1, 11 do commandNodeChangeCount({color = "White"}, nil, "plus_1") end
commandNodeCreateSlots({color = "White"})
flushCallbacks()
assertPanelAboveNode()
for _, marker in ipairs(spawnedSlots) do
    local bounds = marker.getBoundsNormalized().size
    assert(math.abs(bounds.x * 25.4 - 60) < 0.001 and math.abs(bounds.z * 25.4 - 60) < 0.001)
    assert(marker.position.z + 30 / 25.4 < -self.getBoundsNormalized().size.z * 0.5)
end
assert(math.abs((spawnedSlots[1].position.z - spawnedSlots[7].position.z) - 70 / 25.4) < 0.001)
assert(math.abs((spawnedSlots[1].position.x - spawnedSlots[2].position.x) - 70 / 25.4) < 0.001)
assert(math.abs((spawnedSlots[1].position.x - spawnedSlots[7].position.x) - 35 / 25.4) < 0.001)
assert(math.abs(spawnedSlots[7].position.x + spawnedSlots[11].position.x) < 0.001)
assert(lastXml:find('id="slot_1"', 1, true))
assert(not lastXml:find('id="slot_11"', 1, true))
commandNodeSelectSlot({color = "White"}, nil, "slot_1")
assert(lastXml:find('id="option_1_2"', 1, true))
assertPanelAboveNode()
commandNodeSelectOption({color = "White"}, nil, "option_1_2")
assert(spawnedSlots[1].buttons[3].label == "Flamer")
commandNodeLoadoutAll({color = "White"})
assert(spawnedSlots[1].buttons[2].label == "Choose loadout" and spawnedSlots[1].buttons[3].label == "All weapons")
assert(lastXml:find("Place models on tiles:", 1, true))
commandNodeSelectSlot({color = "White"}, nil, "slot_1")
assert(not lastXml:find("[x]", 1, true))
commandNodeLoadoutDone({color = "White"})
assert(spawnedSlots[1].buttons[2].label == "Choose loadout")
commandNodePage({color = "White"}, nil, "page_next")
assert(lastXml:find('id="slot_11"', 1, true))
assert(assertPanelAboveNode() < teamPanelHeight)
assert(lastXml:find('interactable="false">&gt;</Button>', 1, true))
commandNodeSlotsBack({color = "Red"})
assert(objects[spawnedSlots[1].guid])
commandNodeSlotsBack({color = "White"})
assert(not objects[spawnedSlots[1].guid] and not objects[spawnedSlots[11].guid])
assert(lastXml:find('id="plus_1"', 1, true) and lastXml:find('color="#FFFFFF">11</Text>', 1, true))
commandNodeCancel({color = "White"})
assert(startButton.label == "New team" and startButton.width == 900)

spawnedSlots = {}
nodeYaw = 0
cardData.base_size = "75x42"
cardData.keywords = {"MOUNTED"}
extraCard = copy(cardData)
extraCard.name = "ZZZ FOOT OPERATIVE"
extraCard.base_size = 32
extraCard.keywords = {}
commandNodeStart(nil, "White")
commandNodeChooseTeam({color = "White"}, nil, "team_1")
for _ = 1, 7 do commandNodeChangeCount({color = "White"}, nil, "plus_1") end
commandNodeChangeCount({color = "White"}, nil, "plus_2")
commandNodeCreateSlots({color = "White"})
flushCallbacks()
assert(#spawnedSlots == 8)
for index, marker in ipairs(spawnedSlots) do
    local bounds = marker.getBoundsNormalized().size
    assert(math.abs(bounds.x * 25.4 - 60) < 0.001)
    assert(math.abs(bounds.z * 25.4 - (index == 8 and 60 or 70)) < 0.001)
    assert(marker.lines == nil)
    assert(marker.tint[1] == 0 and marker.tint[2] == 0 and marker.tint[3] == 0)
    if index < 8 then
        assert(marker.getRotation().y == nodeYaw)
        assert(marker.position.z + 37.5 / 25.4 < -self.getBoundsNormalized().size.z * 0.5)
    end
end
assert(math.abs((spawnedSlots[1].position.x - spawnedSlots[2].position.x) * 25.4 - 70) < 0.001)
assert(math.abs((spawnedSlots[1].position.z - spawnedSlots[7].position.z) * 25.4 - 85) < 0.001)
hits = {}
commandNodeConfirm({color = "White"})
assert(math.abs(lastCast.size[1] * 25.4 - 60) < 0.001)
assert(math.abs(lastCast.size[3] * 25.4 - 75) < 0.001)
commandNodeCancel({color = "White"})
cardData.base_size = 32
cardData.keywords = nil
extraCard = nil

cardData.name = "UPDATED GUNNER"
commandNodeStart(nil, "White")
commandNodeChooseTeam({color = "White"}, nil, "team_1")
assert(lastXml:find("UPDATED GUNNER", 1, true))
commandNodeCancel({color = "White"})

spawnedSlots = {}
local originalSelection = copy(cardData.node.selection)
for option = 3, 12 do
    cardData.node.selection.groups[1][option] = {label = "Weapon " .. option, weapons = {1}}
end
commandNodeStart(nil, "White")
commandNodeChooseTeam({color = "White"}, nil, "team_1")
commandNodeChangeCount({color = "White"}, nil, "plus_1")
commandNodeCreateSlots({color = "White"})
flushCallbacks()
commandNodeSlotLoadout(spawnedSlots[1], "White")
assert(not lastXml:find('id="option_1_12"', 1, true))
commandNodePage({color = "White"}, nil, "page_next")
assert(lastXml:find('id="option_1_12"', 1, true))
assertPanelAboveNode()
commandNodeSelectOption({color = "White"}, nil, "option_1_12")
assert(lastXml:find('[x] Weapon 12', 1, true))
commandNodeLoadoutDone({color = "White"})
assert(lastXml:find('id="confirm"', 1, true))
commandNodeCancel({color = "White"})

spawnedSlots = {}
cardData.node.selection = {fixed = {0, 1}, groups = {}}
commandNodeStart(nil, "White")
commandNodeChooseTeam({color = "White"}, nil, "team_1")
commandNodeChangeCount({color = "White"}, nil, "plus_1")
commandNodeCreateSlots({color = "White"})
flushCallbacks()
assert(#spawnedSlots[1].buttons == 1)
assert(math.abs(spawnedSlots[1].position.x) < 0.001)
assert(lastXml:find('>1. UPDATED GUNNER</Text></HorizontalLayout>', 1, true))
assert(not lastXml:find('id="slot_1"', 1, true) and not lastXml:find('loadout', 1, true))
commandNodeSelectSlot({color = "White"}, nil, "slot_1")
assert(lastXml:find('id="confirm"', 1, true))
commandNodeCancel({color = "White"})
cardData.node.selection = originalSelection

local rangedOptions = {}
for index = 1, 6 do
    rangedOptions[index] = {label = "Ranged " .. index, weapons = {1}}
end
cardData.node.selection = {
    groups = {rangedOptions, {
        {label = "Melee one", weapons = {0}},
        {label = "Melee two", weapons = {0}},
    }},
}
spawnedSlots = {}
commandNodeStart(nil, "White")
commandNodeChooseTeam({color = "White"}, nil, "team_1")
commandNodeChangeCount({color = "White"}, nil, "plus_1")
commandNodeCreateSlots({color = "White"})
flushCallbacks()
commandNodeSlotLoadout(spawnedSlots[1], "White")
assert(lastXml:find('id="option_1_6"', 1, true))
assert(not lastXml:find('id="option_2_1"', 1, true))
assertPanelAboveNode()
commandNodePage({color = "White"}, nil, "page_next")
assert(lastXml:find('id="option_2_1"', 1, true))
assert(lastXml:find('id="option_2_2"', 1, true))
assert(lastXml:find("Choose one", 1, true))
assertPanelAboveNode()
commandNodeSelectOption({color = "White"}, nil, "option_2_2")
assert(lastXml:find("[x] Melee two", 1, true))
commandNodePage({color = "White"}, nil, "page_prev")
assert(lastXml:find("[x] Ranged 1", 1, true))
commandNodePage({color = "White"}, nil, "page_next")
assert(lastXml:find("[x] Melee two", 1, true))
commandNodeCancel({color = "White"})
cardData.node.selection = originalSelection

for index = 1, 9 do
    local card = copy(cardData)
    card.name = "ZZZ OPERATIVE " .. index
    extraCards[#extraCards + 1] = card
end
commandNodeStart(nil, "White")
commandNodeChooseTeam({color = "White"}, nil, "team_1")
assert(lastXml:find('id="plus_7"', 1, true))
assert(not lastXml:find('id="plus_8"', 1, true))
assert(lastXml:find('id="page_next"', 1, true) < lastXml:find('id="setup_cardbox"', 1, true))
local rosterPanelHeight = assertPanelAboveNode()
commandNodePage({color = "White"}, nil, "page_next")
assert(lastXml:find('id="plus_9"', 1, true))
assert(lastXml:find('id="plus_10"', 1, true))
assert(assertPanelAboveNode() < rosterPanelHeight)
commandNodePage({color = "White"}, nil, "page_next")
assert(lastXml:find('id="plus_10"', 1, true))
commandNodeCancel({color = "White"})
extraCards = {}

local function startSupplySetup()
    spawnedSlots = {}
    commandNodeStart(nil, "White")
    commandNodeChooseTeam({color = "White"}, nil, "team_1")
    commandNodeToggleCardbox({color = "White"})
end

expectCardbox = true
local initialSupplyCount = #spawnedSupplies
suppliesMissing = true
startSupplySetup()
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == initialSupplyCount and messages[#messages]:find("HTTP 404", 1, true))
suppliesMissing = false
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == initialSupplyCount + 1)
commandNodeCancel({color = "White"})

local originalSupplyBox = copy(supplyBox)
supplyBox = {ContainedObjects = {}}
initialSupplyCount = #spawnedSupplies
startSupplySetup()
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == initialSupplyCount)
assert(messages[#messages] == "Invalid team cardbox object: test/tts_objects/Test.json")
supplyBox = {ObjectStates = {originalSupplyBox}}
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == initialSupplyCount + 1)
commandNodeCancel({color = "White"})
supplyBox = originalSupplyBox

supplyAttempts, supplyFailAt = 0, 1
initialSupplyCount = #spawnedSupplies
startSupplySetup()
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == initialSupplyCount and messages[#messages]:find("Could not spawn", 1, true))
supplyFailAt = nil
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == initialSupplyCount + 1)
commandNodeCancel({color = "White"})

initialSupplyCount = #spawnedSupplies
startSupplySetup()
deferRequest = true
local initialRequests = #requests
commandNodeSpawnSupplies({color = "White"})
commandNodeSpawnSupplies({color = "White"})
assert(#requests == initialRequests + 1)
commandNodeCancel({color = "White"})
flushCallbacks()
assert(#spawnedSupplies == initialSupplyCount and lastXml == "")
deferRequest = false

startSupplySetup()
deferRequest = true
commandNodeSpawnSupplies({color = "White"})
local suppliesCallback = table.remove(callbacks, 1)
commandNodeChangeCount({color = "White"}, nil, "plus_1")
commandNodeCreateSlots({color = "White"})
flushCallbacks()
assert(lastXml:find("Place models on tiles:", 1, true))
suppliesCallback()
flushCallbacks()
assert(lastXml:find("Place models on tiles:", 1, true))
commandNodeCancel({color = "White"})
deferRequest = false

startSupplySetup()
initialSupplyCount = #spawnedSupplies
deferRequest = true
commandNodeSpawnSupplies({color = "White"})
supplyTimeouts[#supplyTimeouts]()
assert(messages[#messages]:find("timed out", 1, true))
flushCallbacks()
assert(#spawnedSupplies == initialSupplyCount)
deferRequest = false
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == initialSupplyCount + 1)
commandNodeCancel({color = "White"})
expectCardbox = false

local selections = {
    {box = false, count = 0},
    {box = true, count = 1},
    {box = true, count = 1, wrapped = true},
}
for _, selected in ipairs(selections) do
    supplyBox = selected.wrapped and {ObjectStates = {originalSupplyBox}} or originalSupplyBox
    spawnedSlots = {}
    commandNodeStart(nil, "White")
    commandNodeChooseTeam({color = "White"}, nil, "team_1")
    assert(not lastXml:find('id="supplies"', 1, true))
    assert(not lastXml:find('id="setup_supplies"', 1, true))
    if selected.box then commandNodeToggleCardbox({color = "White"}) end
    local beforeRequests, beforeSupplies = #requests, #spawnedSupplies
    commandNodeNext({color = "White"})
    assert(#requests == beforeRequests and #spawnedSlots == 0)
    commandNodeChangeCount({color = "White"}, nil, "plus_1")
    expectCardbox = selected.box
    rawCardbox = selected.box and not selected.wrapped
    commandNodeNext({color = "White"})
    commandNodeNext({color = "White"})
    flushCallbacks()
    assert(#spawnedSlots == 1 and #spawnedSupplies == beforeSupplies + selected.count)
    assert(#requests == beforeRequests + selected.count)
    assert(lastXml:find("Place models on tiles:", 1, true))
    if selected.box then
        local box = spawnedSupplies[#spawnedSupplies].data
        assert(box.Nickname == "Test cardbox" and #box.ContainedObjects == 5)
        assert(spawnedSupplies[#spawnedSupplies].position.z == 3)
        assert(requests[#requests]:find("/tts_objects/Test.json?v=", 1, true))
        if rawCardbox then
            assert(spawnedSupplies[#spawnedSupplies].spawnJson == rawCardboxText)
        else
            assert(type(spawnedSupplies[#spawnedSupplies].spawnJson) == "table")
        end
    end
    commandNodeCancel({color = "White"})
    expectCardbox = false
    rawCardbox = false
end
supplyBox = originalSupplyBox

spawnedSlots = {}
commandNodeStart(nil, "White")
commandNodeChooseTeam({color = "White"}, nil, "team_1")
commandNodeToggleCardbox({color = "White"})
assert(lastXml:find('>Cardbox added (tokens + dice)</Button>', 1, true))
commandNodeToggleCardbox({color = "White"})
assert(lastXml:find('>Add cardbox (tokens + dice)</Button>', 1, true))
commandNodeCancel({color = "White"})

counterSupported = true
for _, enabled in ipairs({true, false}) do
    spawnedSlots = {}
    commandNodeStart(nil, "White")
    commandNodeChooseTeam({color = "White"}, nil, "team_1")
    commandNodeChangeCount({color = "White"}, nil, "plus_1")
    assert(lastXml:find('id="setup_cardbox"', 1, true))
    assert(lastXml:find('id="setup_rules" onClick="commandNodeToggleRules"', 1, true))
    assert(lastXml:find('colors="#237A60|#56686D|#293336|#333333" textColor="#FFFFFF">Gore Tank added</Button>', 1, true))
    assert(lastXml:find('<VerticalLayout preferredHeight="74" flexibleHeight="0" spacing="6"', 1, true))
    assertPanelAboveNode()
    assert(not lastXml:find('id="setup_supplies"', 1, true))
    if not enabled then
        commandNodeToggleRules({color = "White"})
        assert(lastXml:find('textColor="#FFFFFF">Add Gore Tank</Button>', 1, true))
    end
    commandNodeNext({color = "White"})
    flushCallbacks()
    local marker = spawnedSlots[1]
    local model = newObject("Figurine", Vector(0, 1, 0))
    hits[string.format("%.1f,%.1f", marker.position.x, marker.position.z)] = {{hit_object = model}}
    commandNodeConfirm({color = "White"})
    flushCallbacks()
    assert(model.applied and model.uiVisible)
    assert(#model.applied.weapons == 3)
    commandNodeUpdateModel({guid = model.guid, color = "White"})
    flushCallbacks()
    assert(#model.updated.weapons == 3 and model.script_state.kt_source.loadout == nil)
    if enabled then
        assert(model.counterInstalls == 1 and model.script_state.operative_counter.name == "Gore Tank")
        assert(model.frontReloads == 2)
    else
        assert(not model.counterInstalls and not model.script_state.operative_counter)
        assert(model.frontReloads == 1)
    end
end
counterSupported = false

choicesSupported = true
for _, enabled in ipairs({true, false}) do
    spawnedSlots = {}
    commandNodeStart(nil, "White")
    commandNodeChooseTeam({color = "White"}, nil, "team_1")
    assert(lastXml:find('>Chapter Tactics added</Button>', 1, true))
    assert(lastXml:find('id="choose_rules"', 1, true))
    assert(lastXml:find('>Select Chapter Tactics</Button>', 1, true))
    if enabled then
        commandNodeChooseRules({color = "White"})
        assert(lastXml:find("Primary", 1, true))
        commandNodeRuleOption({color = "White"}, nil, "rule_1_4")
        commandNodePage({color = "White"}, nil, "page_next")
        assert(lastXml:find("Secondary", 1, true))
        commandNodeRuleOption({color = "White"}, nil, "rule_2_4")
        assert(lastXml:find("[x] Stealthy", 1, true))
        commandNodePage({color = "White"}, nil, "page_prev")
        assert(lastXml:find("[x] Dueller", 1, true))
        commandNodeRulesDone({color = "White"})
    else
        commandNodeToggleRules({color = "White"})
        assert(not lastXml:find('id="choose_rules"', 1, true))
    end
    commandNodeChangeCount({color = "White"}, nil, "plus_1")
    commandNodeNext({color = "White"})
    flushCallbacks()
    local marker = spawnedSlots[1]
    local model = newObject("Figurine", Vector(0, 1, 0))
    hits[string.format("%.1f,%.1f", marker.position.x, marker.position.z)] = {{hit_object = model}}
    commandNodeConfirm({color = "White"})
    flushCallbacks()
    assert(model.uiVisible and not model.counterInstalls)
    if enabled then
        assert(model.applied.abilities[1].name == "Dueller (Primary)")
        assert(model.applied.abilities[1].text == "Tactic text 2")
        commandNodeUpdateModel({guid = model.guid, color = "White"})
        flushCallbacks()
        assert(model.updated.abilities[1].name == "Dueller (Primary)")
        assert(model.updated.abilities[2].name == "Stealthy (Secondary)")
        assert(model.applied.abilities[2].name == "Stealthy (Secondary)")
        assert(model.applied.abilities[2].text == "Tactic text 4")
    else
        assert(#model.applied.abilities == 0)
    end
end
choicesSupported = false

choicesSupported = true
choiceOverride = {
    name = "Accursed Gifts", select = 1, kind = "choice", applies_to = {"MUTANT", "TORMENT"},
    operative_select_count = {MUTANT = 1, TORMENT = 2},
    options = {{name = "Fleet"}, {name = "Chitinous"}},
}
local originalCard = copy(cardData)
cardData.name = "A MUTANT"
cardData.keywords = {"MUTANT"}
extraCards = {copy(cardData), copy(cardData)}
extraCards[1].name = "B TORMENT"
extraCards[1].keywords = {"TORMENT"}
extraCards[2].name = "C CULTIST"
extraCards[2].keywords = {"CULTIST"}
spawnedSlots = {}
commandNodeStart(nil, "White")
commandNodeChooseTeam({color = "White"}, nil, "team_1")
assert(lastXml:find('>Select Accursed Gifts</Button>', 1, true))
commandNodeChooseRules({color = "White"})
assert(lastXml:find('id="rule_1_1"', 1, true))
assert(lastXml:find('id="rule_2_2"', 1, true))
commandNodeRulesDone({color = "White"})
for index = 1, 3 do commandNodeChangeCount({color = "White"}, nil, "plus_" .. index) end
commandNodeNext({color = "White"})
flushCallbacks()
local cultModels = {}
for _, marker in ipairs(spawnedSlots) do
    local model = newObject("Figurine", Vector(0, 1, 0))
    cultModels[#cultModels + 1] = model
    hits[string.format("%.1f,%.1f", marker.position.x, marker.position.z)] = {{hit_object = model}}
end
commandNodeConfirm({color = "White"})
flushCallbacks()
assert(#cultModels[1].applied.abilities == 1)
assert(cultModels[1].applied.abilities[1].name == "Fleet")
assert(#cultModels[2].applied.abilities == 2)
assert(cultModels[2].applied.abilities[1].name == "Fleet (Primary)")
assert(cultModels[2].applied.abilities[2].name == "Chitinous (Secondary)")
assert(#cultModels[3].applied.abilities == 0)
for _, model in ipairs(cultModels) do assert(model.uiVisible and not model.counterInstalls) end
cardData = originalCard
extraCards = {}
choicesSupported = false
choiceOverride = nil

loaderMetadataTruncated = true
commandNodeStart(nil, "White")
commandNodeChooseTeam({color = "White"}, nil, "team_1")
assert(messages[#messages]:find("special-rule setup update", 1, true))
assert(lastXml:find('id="team_1"', 1, true))
commandNodeCancel({color = "White"})
loaderMetadataTruncated = false

loaderOutdated = true
commandNodeStart(nil, "White")
commandNodeChooseTeam({color = "White"}, nil, "team_1")
assert(messages[#messages]:find("special-rule setup update", 1, true))
assert(lastXml:find('id="team_1"', 1, true))
commandNodeCancel({color = "White"})
loaderOutdated = false

loaderMissing = true
commandNodeStart(nil, "White")
commandNodeChooseTeam({color = "White"}, nil, "team_1")
assert(messages[#messages]:find("HTTP 404", 1, true))
assert(lastXml:find('id="team_1"', 1, true))
commandNodeCancel({color = "White"})
loaderMissing = false

metadataMissing = true
commandNodeStart(nil, "White")
commandNodeChooseTeam({color = "White"}, nil, "team_1")
assert(messages[#messages]:find("HTTP 404", 1, true))
assert(lastXml:find('id="team_1"', 1, true))
commandNodeCancel({color = "White"})
metadataMissing = false

deferRequest = true
commandNodeStart(nil, "White")
commandNodeCancel({color = "White"})
flushCallbacks()
assert(lastXml == "")
deferRequest = false

indexMissing = true
commandNodeStart(nil, "White")
assert(startButton.label == "New team" and startButton.width == 900)
assert(lastXml == "" and messages[#messages]:find("HTTP 404", 1, true))
indexMissing = false

indexEmpty = true
commandNodeStart(nil, "White")
assert(startButton.label == "New team" and startButton.width == 900)
assert(lastXml == "" and messages[#messages]:find("No teams", 1, true))
indexEmpty = false
for _, url in ipairs(requests) do
    assert(url:sub(1, #NODE_REPO_BASE_URL) == NODE_REPO_BASE_URL, "Request escaped configured branch: " .. url)
end
print("command node workflow passed")