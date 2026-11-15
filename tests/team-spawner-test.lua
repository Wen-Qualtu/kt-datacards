local lastXml = ""
local attributes = {}
local requests = {}
local spawned = {}
local broadcasts = {}
local startButton

function Vector(x, y, z) return {x = x, y = y, z = z} end
local vectorMeta = {__add = function(left, right) return Vector(left.x + right.x, left.y + right.y, left.z + right.z) end}
local function vector(x, y, z) return setmetatable(Vector(x, y, z), vectorMeta) end

local index = {}
for _, slug in ipairs({"kasrkin", "angels-of-death", "death-korps", "wolf-scouts", "hearthkyn-salvagers"}) do
    index[slug] = {box = {url = "https://example.test/" .. slug .. ".json?v=1"}}
end
index["no-box"] = {team_url = "https://example.test/no-box"}

JSON = {decode = function(text) assert(text == "team-index"); return index end}
WebRequest = {get = function(url, callback)
    requests[#requests + 1] = url
    local text = url:find("team%-urls%.json") and "team-index" or ' \n{"Name":"Custom_Model_Bag"}'
    callback({is_error = false, response_code = 200, text = text, error = ""})
end}
Physics = {cast = function() return {} end}
function spawnObjectJSON(parameters) spawned[#spawned + 1] = parameters; return {} end
function broadcastToAll(message) broadcasts[#broadcasts + 1] = message end
local originalPrint = print
function print() end
local function player(color)
    return {color = color, broadcast = function(message) broadcasts[#broadcasts + 1] = message end}
end
Player = {White = player("White")}

self = {
    setName = function() end,
    setDescription = function(text) self.description = text end,
    createButton = function(parameters) startButton = parameters end,
    getPosition = function() return vector(0, 1, 0) end,
    getScale = function() return {x = 1, y = 1, z = 1} end,
    getBoundsNormalized = function() return {size = {x = 2, y = 0.2, z = 2}} end,
    UI = {
        setXml = function(xml) lastXml = xml; attributes = {} end,
        setAttribute = function(id, name, value) attributes[id .. "." .. name] = value end,
    },
}

dofile("config/defaults/tts-script/team-spawner-clean-script.lua")
onLoad()
assert(startButton.label == "Spawn Team" and startButton.click_function == "onSpawnClick")
assert(startButton.position[3] < -1 and math.abs(startButton.position[2] - 0.15) < 0.001)
assert(self.description:find("5 teams available", 1, true))

onSpawnClick(self, "White")
assert(lastXml:find('id="spawner_search" onValueChanged="spawnerSearch" onSubmit="spawnerSubmit"', 1, true))
assert(lastXml:find('constraint="FixedColumnCount" constraintCount="3"', 1, true))
assert(not lastXml:find("tooltip=", 1, true))
local order = {}
for id, name in lastXml:gmatch('id="(team_%d+)".->([^<]+)</Button>') do order[#order + 1] = id .. "=" .. name end
assert(table.concat(order, ",") == "team_1=Angels Of Death,team_2=Death Korps,team_3=Hearthkyn Salvagers,"
    .. "team_4=Kasrkin,team_5=Wolf Scouts", table.concat(order, ","))
local scaleX, scaleY = lastXml:match('scale="([%d.]+) ([%d.]+) 1"')
assert(math.abs(tonumber(scaleX) - tonumber(scaleY)) < 0.001, "Panel must not be stretched by the token scale")

spawnerSearch(Player.White, "DEATH")
assert(attributes["team_1.active"] == "true" and attributes["team_2.active"] == "true")
assert(attributes["team_4.active"] == "false" and attributes["team_5.active"] == "false")
spawnerSearch(Player.White, "")
assert(attributes["team_4.active"] == "true")

spawnerSubmit(Player.White, "death")
assert(#spawned == 0 and broadcasts[#broadcasts]:find("2 teams match", 1, true))
spawnerSubmit(Player.White, "zzz")
assert(#spawned == 0 and broadcasts[#broadcasts]:find("No team matches", 1, true))
spawnerSubmit(Player.White, "kas")
assert(#spawned == 1 and lastXml == "")
assert(requests[#requests] == "https://example.test/kasrkin.json?v=1")
assert(spawned[1].json == '{"Name":"Custom_Model_Bag"}')

onSpawnClick(self, "White")
assert(lastXml ~= "")
spawnerChooseTeam(Player.White, nil, "team_5")
assert(#spawned == 2 and lastXml == "" and requests[#requests]:find("wolf-scouts", 1, true))

onSpawnClick(self, "White")
onSpawnClick(self, "White")
assert(lastXml == "", "Spawn Team toggles the menu closed")
onSpawnClick(self, "White")
spawnerClose()
assert(lastXml == "")

originalPrint("team spawner workflow passed")
