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
local supplyTimeouts = {}
local supplyBox = {ContainedObjects = {
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
function rebuildDescription(data) return "Chosen loadout" end
function diffAndApply(model, data, color, replaceScript, modelScript)
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
    encode = copy,
    decode = function(value)
        if value == "team-index" then return index end
        if value == "empty-index" then return {} end
        if value == "team-metadata" then return {
            team = "test", team_data = {url = "https://example.test/main/test-data", hash = "abc123"},
            box = {url = "https://example.test/main/output/test/tts_objects/Test.json", hash = "def456"},
            objects = {{type = "token-bag"}},
        } end
        if type(value) == "string" and value:match("^supply:") then
            local root = supplyBox.ObjectStates and supplyBox.ObjectStates[1] or supplyBox
            local object = copy(root.ContainedObjects[tonumber(value:match("%d+"))])
            return supplyBox.ObjectStates and {ObjectStates = {object}} or object
        end
        if value == "test-roster" then
            local cards = {copy(cardData)}
            if extraCard then cards[#cards + 1] = copy(extraCard) end
            for _, card in ipairs(extraCards) do cards[#cards + 1] = copy(card) end
            return {team = "test", datacards = cards}
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
local deferRequest = false
WebRequest = {get = function(url, callback)
    assert(not url:find("/tts_objects/Test.json", 1, true), "Must not download the full team box")
    requests[#requests + 1] = url
    local text
    if url:find("team%-urls%.json") and not indexMissing then
        text = indexEmpty and "empty-index" or "team-index"
    elseif url:find("/output/test/test-object-urls.json", 1, true) and not metadataMissing then text = "team-metadata"
    elseif url:find("/output/test/data/test-team-data.json", 1, true) then text = "test-roster"
    elseif url:find("/output/test/tts_objects/", 1, true) and not suppliesMissing then
        local tags = {
            ["test-token-bag"] = "KTCardsTokenBag", ["dice/test-dice"] = "KTDice_Team",
            ["dice/test-light-dice"] = "KTDice_Light", ["dice/test-dark-dice"] = "KTDice_Dark",
        }
        local wanted = tags[url:match("/tts_objects/(.-)%.json")]
        local root = supplyBox.ObjectStates and supplyBox.ObjectStates[1] or supplyBox
        for index, object in ipairs(root.ContainedObjects or {}) do
            for _, tag in ipairs(object.Tags or {}) do
                if tag == wanted then text = "supply:" .. index end
            end
        end
    elseif url:find("command%-node%-loader%.lua") and not loaderMissing then
        text = loaderOutdated and cardScript:gsub("color, replaceScript, modelScript%)", "color)") or cardScript
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
        local environment = setmetatable({applied = applied}, {__index = _G})
        assert(load(object.script, "helper", "t", environment))()
        applyAdapter = environment.ktCommandNodeApply
        object.call = function(name, parameters) return environment[name](parameters) end
    end
    object.destruct = function() objects[guid] = nil end
    return object
end

function spawnObjectJSON(parameters)
    supplyAttempts = supplyAttempts + 1
    if supplyAttempts == supplyFailAt then return nil end
    local object = newObject(parameters.json.Name, parameters.position)
    object.data = copy(parameters.json)
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
self = {
    UI = {setXml = function(xml) lastXml = xml end},
    getGUID = function() return "node" end,
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
    assert(height >= 116 and height <= 550)
    return height
end

dofile("config/defaults/tts-script/command-node.lua")
local converted = assert(commandNodeModelData({
    name = "GUNNER", apl = 2, movement = '6"', save = "4+", wounds = 8, base_size = 32,
    keywords = {"TEST"}, weapons = {{name = "Gun & blade", attacks = "4", hit = "3+", damage = "3/4"}},
    passive_abilities = {{name = " Steady ", description = " Ready "}},
    node = {weapon_types = {"ranged"}, weapon_rules = {}, selection = {groups = {}}},
}))
assert(converted.stats.Move == 6 and converted.stats.Base == 32)
assert(converted.weapons[1].name == "[1E87FF]R[-] Gun and blade")
assert(converted.abilities[1].name == "Steady" and converted.abilities[1].text == "Ready")
assert(commandNodeModelData({name = "Missing"}) == nil)
local longAbility = string.rep("Grit. ", 1200)
local trimmedAbility = string.rep("Grit. ", 1199) .. "Grit."
local unicodeData = assert(commandNodeModelData({
    name = "HEARTHKYN D\195\148ZR",
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
assert(teamPanelHeight == 550)
assert(lastXml:find('minHeight="28" preferredHeight="28" flexibleHeight="0" childForceExpandHeight="false"', 1, true))
assert(lastXml:find('preferredWidth="36" flexibleWidth="0" minHeight="28" preferredHeight="28" flexibleHeight="0"', 1, true))
assert(lastXml:find('interactable="false">&lt;</Button>', 1, true))
assert(lastXml:find('tooltip="Next page"', 1, true))
assert(lastXml:find('id="team_1"', 1, true))
assert(lastXml:find('id="team_10"', 1, true))
assert(not lastXml:find('id="team_11"', 1, true))
for _ = 1, 4 do commandNodePage({color = "White"}, nil, "page_next") end
assert(lastXml:find('id="team_50"', 1, true))
assert(not lastXml:find('id="team_51"', 1, true))
for _ = 1, 4 do commandNodePage({color = "White"}, nil, "page_prev") end
commandNodeChooseTeam({color = "White"}, nil, "team_1")
assert(requests[2]:find(NODE_REPO_BASE_URL .. "/output/test/test-object-urls.json", 1, true) == 1)
assert(requests[3] == NODE_REPO_BASE_URL .. "/output/test/data/test-team-data.json?v=abc123")
assert(#requests == 3)
assert(lastXml:find('id="supplies"', 1, true))
commandNodeSpawnSupplies({color = "Red"})
assert(#requests == 3 and #spawnedSupplies == 0)
commandNodeSpawnSupplies({color = "White"})
assert(requests[4]:find(NODE_REPO_BASE_URL .. "/output/test/tts_objects/test-token-bag.json?v=", 1, true) == 1)
assert(requests[#requests]:find("/tts_objects/dice/test-dark-dice.json?v=", 1, true))
assert(#spawnedSupplies == 4)
assert(spawnedSupplies[1].data.LuaScript == "token-bag-script")
assert(#spawnedSupplies[1].data.ContainedObjects == 1)
assert(spawnedSupplies[2].data.LuaScript == "dice-script")
assert(spawnedSupplies[1].position.x > 10)
assert(spawnedSupplies[2].position.z - spawnedSupplies[1].position.z == 3)
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == 4)
assert(assertPanelAboveNode() < teamPanelHeight)
assert(not lastXml:find('id="page_next"', 1, true))
assert(lastXml:find('<HorizontalLayout preferredHeight="42" flexibleHeight="0" spacing="4" childForceExpandWidth="false"', 1, true))
assert(lastXml:find('preferredWidth="310" flexibleWidth="0"', 1, true))
assert(lastXml:find('preferredWidth="48" flexibleWidth="0"', 1, true))
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
for line in spawnedSlots[1].buttons[1].label:gmatch("[^\n]+") do assert(#line <= 16) end
assert(math.abs((spawnedSlots[2].position.x - spawnedSlots[1].position.x) - (70 / 25.4)) < 0.001)
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
commandNodeSelectOption({color = "White"}, nil, "option_1_2")
assert(lastXml:find('[x] Flamer', 1, true))
commandNodeLoadoutDone({color = "White"})
assert(lastXml:find('id="confirm"', 1, true))
commandNodeSlotLoadout(spawnedSlots[2], "White")
assert(lastXml:find('[x] Plasma', 1, true))
commandNodeSelectOption({color = "White"}, nil, "option_1_1")
commandNodeLoadoutDone({color = "White"})
commandNodeSlotLoadout(spawnedSlots[1], "White")
assert(lastXml:find('[x] Flamer', 1, true))
commandNodeLoadoutDone({color = "White"})

commandNodeConfirm({color = "White"})
assert(#applied == 0 and messages[#messages]:find("exactly one model", 1, true))

local modelOne = newObject("Custom_Model", Vector(0, 1, 0))
local modelTwo = newObject("Figurine", Vector(0, 1, 0))
modelOne.rotation = {x = 10, y = 27, z = 20}
modelTwo.rotation = {x = 0, y = 47, z = 0}
modelTwo.script_state = {kt_front = 180, base = {x = 32, z = 32}}
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
loaderMissing = true
commandNodeConfirm({color = "White"})
assert(#applied == 0 and messages[#messages]:find("HTTP 404", 1, true))
assert(modelOne.rotation.y == 27 and modelTwo.rotation.y == 47)
loaderMissing = false
loaderOutdated = true
commandNodeConfirm({color = "White"})
assert(#applied == 0 and messages[#messages]:find("loader is outdated", 1, true))
assert(#modelTwo.buttons == 1 and #modelTwo.inputs == 1 and not modelTwo.buttonsCleared)
loaderOutdated = false
commandNodeConfirm({color = "White"})
flushCallbacks()
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
        loaderEnvironment.diffAndApply(model, {stats = {}}, "White")
        assert(not model.script and model.reloads == 0)
    end
    loaderEnvironment.diffAndApply(model, {stats = {}}, "White", true)
    assert(model.script == "latest composed extender" and model.reloads == 1)
    assert(model.tags.KTUIMini and model.tags.KTUIMiniDatacard)
    assert(model.script_state.owner == "existing-owner" and model.script_state.wounds == 4)
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
assert(math.abs((spawnedSlots[2].position.x - spawnedSlots[1].position.x) - 70 / 25.4) < 0.001)
assert(lastXml:find('id="slot_1"', 1, true))
assert(not lastXml:find('id="slot_11"', 1, true))
commandNodeSelectSlot({color = "White"}, nil, "slot_1")
assert(lastXml:find('id="option_1_2"', 1, true))
assertPanelAboveNode()
commandNodeLoadoutDone({color = "White"})
commandNodePage({color = "White"}, nil, "page_next")
assert(lastXml:find('id="slot_11"', 1, true))
assert(assertPanelAboveNode() < teamPanelHeight)
assert(lastXml:find('interactable="false">&gt;</Button>', 1, true))
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
assert(math.abs((spawnedSlots[2].position.x - spawnedSlots[1].position.x) * 25.4 - 70) < 0.001)
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
assert(lastXml:find('id="plus_8"', 1, true))
assert(not lastXml:find('id="plus_9"', 1, true))
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
end

local initialSupplyCount = #spawnedSupplies
suppliesMissing = true
startSupplySetup()
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == initialSupplyCount and messages[#messages]:find("HTTP 404", 1, true))
suppliesMissing = false
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == initialSupplyCount + 4)
commandNodeCancel({color = "White"})

local originalSupplyBox = copy(supplyBox)
table.remove(supplyBox.ContainedObjects, 1)
initialSupplyCount = #spawnedSupplies
startSupplySetup()
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == initialSupplyCount + 3)
assert(messages[#messages]:find("no standalone token bag", 1, true))
commandNodeCancel({color = "White"})

supplyBox = {ContainedObjects = {}}
initialSupplyCount = #spawnedSupplies
startSupplySetup()
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == initialSupplyCount and messages[#messages]:find("HTTP 404", 1, true))
supplyBox = {ObjectStates = {originalSupplyBox}}
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == initialSupplyCount + 4)
commandNodeCancel({color = "White"})
supplyBox = originalSupplyBox

supplyAttempts, supplyFailAt = 0, 2
initialSupplyCount = #spawnedSupplies
startSupplySetup()
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == initialSupplyCount + 1)
assert(objects[spawnedSupplies[#spawnedSupplies].guid] == nil)
supplyFailAt = nil
commandNodeSpawnSupplies({color = "White"})
assert(#spawnedSupplies == initialSupplyCount + 5)
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
assert(#spawnedSupplies == initialSupplyCount + 4)
commandNodeCancel({color = "White"})

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