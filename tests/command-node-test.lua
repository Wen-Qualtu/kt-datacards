local objects = {}
local spawnedSlots = {}
local messages = {}
local applied = {}
local nextGuid = 0
local hits = {}
local lastXml = ""
local callbacks = {}
local startButton

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
function rebuildDescription(data) return "Chosen loadout" end
function diffAndApply(model, data, color)
    model.applied = data
    model.color = color
    applied[#applied + 1] = model
    return {"updated"}
end
]]

local cardData = {
    name = "GUNNER",
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
        if value == "team-metadata" then return {team = "test", team_data = {url = "https://example.test/main/test-data", hash = "abc123"}} end
        if value == "test-roster" then return {team = "test", datacards = {copy(cardData)}} end
        return value
    end,
}
local requests = {}
local indexMissing = false
local indexEmpty = false
local metadataMissing = false
local loaderMissing = false
local deferRequest = false
WebRequest = {get = function(url, callback)
    requests[#requests + 1] = url
    local text
    if url:find("team%-urls%.json") and not indexMissing then
        text = indexEmpty and "empty-index" or "team-index"
    elseif url:find("/output/test/test-object-urls.json", 1, true) and not metadataMissing then text = "team-metadata"
    elseif url:find("/output/test/data/test-team-data.json", 1, true) then text = "test-roster"
    elseif url:find("command%-node%-loader%.lua") and not loaderMissing then text = cardScript end
    local response = {response_code = text and 200 or 404, is_error = not text, text = text, error = ""}
    if deferRequest then
        callbacks[#callbacks + 1] = function() callback(response) end
    else
        callback(response)
    end
end}
Physics = {cast = function(parameters)
    return hits[string.format("%.1f,%.1f", parameters.origin.x, parameters.origin.z)] or {}
end}
Wait = {frames = function(callback) callbacks[#callbacks + 1] = callback end}
function broadcastToColor(message) messages[#messages + 1] = message end
function getObjectsWithTag() return {} end
function getObjectFromGUID(guid) return objects[guid] end

local function newObject(kind, position)
    nextGuid = nextGuid + 1
    local guid = tostring(nextGuid)
    local object = {type = kind, position = position, guid = guid}
    objects[guid] = object
    object.getGUID = function()
        assert(not object.spawning, "GUID requested before spawn completed")
        return guid
    end
    object.getPosition = function() return position end
    object.getRotation = function() return {0, 0, 0} end
    object.setLock = function() end
    object.setName = function() end
    object.setColorTint = function() end
    object.addTag = function() end
    object.createButton = function() end
    object.setVectorLines = function() end
    object.setInvisibleTo = function() end
    object.setGMNotes = function() end
    object.setLuaScript = function(script) object.script = script end
    object.reload = function()
        local environment = setmetatable({applied = applied}, {__index = _G})
        assert(load(object.script, "helper", "t", environment))()
        object.call = function(name, parameters) return environment[name](parameters) end
    end
    object.destruct = function() objects[guid] = nil end
    return object
end

function spawnObject(parameters)
    local object = newObject(parameters.type, parameters.position)
    object.spawning = true
    if parameters.scale[2] == 0.08 then spawnedSlots[#spawnedSlots + 1] = object end
    callbacks[#callbacks + 1] = function()
        object.spawning = false
        if parameters.callback_function then parameters.callback_function(object) end
    end
    return object
end

self = {
    UI = {setXml = function(xml) lastXml = xml end},
    getGUID = function() return "node" end,
    setName = function() end,
    createButton = function(parameters) startButton = parameters end,
    editButton = function(parameters)
        for key, value in pairs(parameters) do startButton[key] = value end
    end,
    positionToWorld = function(position) return Vector(position[1], position[2], position[3]) end,
    getPosition = function() return Vector(0, 1, 0) end,
    getRotation = function() return {0, 0, 0} end,
}

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
assert(startButton.position[3] < -1 and startButton.position[2] > 0.5)
commandNodeStart(nil, "White")
assert(startButton.label == "" and startButton.width == 0 and startButton.height == 0)
assert(not lastXml:find("<VerticalScrollView", 1, true))
assert(not lastXml:find('allowDragging="true"', 1, true))
assert(lastXml:find('position="0 0 -80"', 1, true))
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
commandNodeChangeCount({color = "White"}, nil, "plus_1")
commandNodeChangeCount({color = "White"}, nil, "plus_1")
commandNodeCreateSlots({color = "White"})
assert(#spawnedSlots == 2)
flushCallbacks()
commandNodeSelectSlot({color = "White"}, nil, "slot_2")
commandNodeSelectOption({color = "White"}, nil, "option_1_2")

commandNodeConfirm({color = "White"})
assert(#applied == 0 and messages[#messages]:find("exactly one model", 1, true))

local modelOne = newObject("Custom_Model", Vector(0, 1, 0))
local modelTwo = newObject("Figurine", Vector(0, 1, 0))
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
loaderMissing = false
commandNodeConfirm({color = "White"})
flushCallbacks()
assert(#applied == 2, "Applied " .. #applied .. ": " .. tostring(messages[#messages]))
assert(modelOne.applied.weapons[1].plain_name == "fixed" and modelOne.applied.weapons[2].plain_name == "plasma")
assert(modelTwo.applied.weapons[1].plain_name == "fixed" and modelTwo.applied.weapons[2].plain_name == "flamer")
assert(modelOne.color == "White" and modelTwo.color == "White")
assert(not objects[spawnedSlots[1].guid] and not objects[spawnedSlots[2].guid])
assert(startButton.label == "Start" and startButton.width == 900)

spawnedSlots = {}
commandNodeStart(nil, "White")
commandNodeChooseTeam({color = "White"}, nil, "team_1")
for _ = 1, 11 do commandNodeChangeCount({color = "White"}, nil, "plus_1") end
commandNodeCreateSlots({color = "White"})
flushCallbacks()
assert(lastXml:find('id="slot_1"', 1, true))
assert(not lastXml:find('id="slot_11"', 1, true))
commandNodeSelectSlot({color = "White"}, nil, "slot_1")
assert(lastXml:find('id="slot_11"', 1, true))
assert(lastXml:find('id="option_1_2"', 1, true))
commandNodeCancel({color = "White"})
assert(startButton.label == "Start" and startButton.width == 900)

cardData.name = "UPDATED GUNNER"
commandNodeStart(nil, "White")
commandNodeChooseTeam({color = "White"}, nil, "team_1")
assert(lastXml:find("UPDATED GUNNER", 1, true))
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
assert(startButton.label == "Start" and startButton.width == 900)
assert(lastXml == "" and messages[#messages]:find("HTTP 404", 1, true))
indexMissing = false

indexEmpty = true
commandNodeStart(nil, "White")
assert(startButton.label == "Start" and startButton.width == 900)
assert(lastXml == "" and messages[#messages]:find("No teams", 1, true))
indexEmpty = false
for _, url in ipairs(requests) do
    assert(url:sub(1, #NODE_REPO_BASE_URL) == NODE_REPO_BASE_URL, "Request escaped configured branch: " .. url)
end
print("command node workflow passed")