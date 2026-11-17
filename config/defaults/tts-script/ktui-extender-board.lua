-- KT Datacards UI Extender board.
-- Does what the "UI Extender + Tools" board of the KT Command Node UI Extender
-- does (original authors: Nyirsh, Feuerfritas, Ixidior, Mal20k), but stamps OUR
-- composed KTUI model script -- tagged START/END blocks, oval-aware targeting
-- with cover/obscured, and our Move/Dash (or Sprint/Turn/Leap for MOUNTED
-- operatives) instead of the KTMT Movement tool -- downloaded from the
-- kt-datacards repo. tools/build_ktui_extender.py prepends KT_SCRIPTS_URL.

-- Non-player operatives leaving an "_NPO bag" are extended too. The original
-- NPO autoextender may also be on the table and re-stamps them ~0.3 s + a
-- download later, so ours runs after it.
local NPO_DELAY = 2.5

local scripts = nil   -- downloaded {version, model, move, sprint}
local pending = {}    -- callbacks waiting for that download

local function withScripts(callback)
  if scripts then return callback(scripts) end
  table.insert(pending, callback)
  if #pending > 1 then return end
  WebRequest.get(KT_SCRIPTS_URL, function(req)
    local waiting = pending
    pending = {}
    if req.is_error then
      log(req.error)
      broadcastToAll("KT UI Extender: could not download the model script.", {1, 0.5, 0})
      return
    end
    local ok, data = pcall(function() return JSON.decode(req.text) end)
    if not ok or type(data) ~= "table" or type(data.model) ~= "string" then
      broadcastToAll("KT UI Extender: the downloaded model script is invalid.", {1, 0.5, 0})
      return
    end
    scripts = data
    for _, cb in ipairs(waiting) do cb(scripts) end
  end)
end

local function isMounted(model)
  local ok, state = pcall(function() return JSON.decode(model.script_state or "") end)
  local categories = ok and type(state) == "table" and type(state.info) == "table" and state.info.categories
  for _, keyword in ipairs(type(categories) == "table" and categories or {}) do
    if tostring(keyword):upper() == "MOUNTED" then return true end
  end
  return false
end

-- Our script + the model's movement block; saved state (stats, wounds, base,
-- owner) lives in script_state and survives the swap.
function extendModel(model, steamId)
  local movement = isMounted(model) and scripts.sprint or scripts.move
  model.setLuaScript(scripts.model .. "\n\n" .. movement)
  model = model.reload()
  model.addTag("KTUIMini")
  model.addTag("KTUIMiniDatacard")
  if steamId then
    Wait.frames(function() model.call("setOwningPlayer", steamId) end, 1)
  end
  return model
end

function KTUI_ResetScripts()
  broadcastToAll("Reloading KT UI Extender")
  local r = 0
  for _, obj in ipairs(getAllObjects()) do
    if obj.hasTag('KTUIMini') then
      obj.reload()
      r = r+1
    end
  end
  broadcastToAll("Reloaded "..r.." items")
end

function detectItemOnTop()
  local pos = self.getPosition()
  return Physics.cast({
    origin       = {pos[1], pos[2]+3.1, pos[3]},
    direction    = {0,1,0},
    type         = 2,
    size         = {15,15,15},
    max_distance = 3,
  })
end

function ExtendUI(player)
  withScripts(function()
    local extended = 0
    for _, hit in ipairs(detectItemOnTop()) do
      local object = hit.hit_object
      if object.tag == "Figurine" then
        extendModel(object, player.steam_id)
        extended = extended + 1
      end
    end
    player.broadcast("Extended KT UI on "..extended.." model(s)")
  end)
end

function onObjectLeaveContainer(container, object)
  if container.hasTag('_NPO bag') and object.hasTag('KTUIMini') and object.hasTag('Operative') then
    local guid = object.getGUID()
    Wait.time(function()
      withScripts(function()
        local npo = getObjectFromGUID(guid)
        if npo then extendModel(npo, nil) end
      end)
    end, NPO_DELAY)
  end
end

local function forOwned(objects, fn)
  for _, obj in ipairs(objects) do
    if obj.hasTag('KTUIMini') and obj.call("getOwningPlayer") ~= nil then fn(obj) end
  end
end

local function onBoard()
  local found = {}
  for _, hit in ipairs(detectItemOnTop()) do table.insert(found, hit.hit_object) end
  return found
end

function SaveAllPositions(player)
  forOwned(getAllObjects(), function(obj) obj.call("savePosition") end)
  player.broadcast("All positions saved")
end

function LoadAllPositions(player)
  forOwned(getAllObjects(), function(obj) obj.call("loadPosition") end)
  player.broadcast("All positions loaded")
end

function ReadyAllOperatives(player)
  forOwned(getAllObjects(), function(obj) obj.call("KTUI_ReadyOperative") end)
  player.broadcast("All operatives have been readied")
end

function CleanAllOperatives(player)
  forOwned(onBoard(), function(obj) obj.call("KTUI_CleanOperative") end)
  player.broadcast("All operatives have been cleaned of their tokens")
end

function EngageAllOperatives()
  forOwned(onBoard(), function(obj) obj.call("setEngage") end)
end

function ConcealAllOperatives()
  forOwned(onBoard(), function(obj) obj.call("setConceal") end)
end
