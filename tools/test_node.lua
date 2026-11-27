-- Test node: installs the embedded tool blocks (NODE_BLOCKS) onto models so tools
-- can be tested without regenerating any datacards.
-- Built by tools/build_test_node.py, which prepends NODE_TOOL, NODE_BUILD,
-- NODE_HINT, NODE_BLOCKS ({start, finish, code} per block) and the shared
-- injectBlock/healExtenderScript helpers.

function isModelLike(obj)
    if obj == nil or obj == self then return false end
    if obj.hasTag("KTUIMini") then return true end
    local t = obj.type
    return t == "Figurine" or t == "Generic" or t == "Model"
end

function modelsOnNode()
    local pos = self.getPosition()
    local scale = self.getScale()
    local hits = Physics.cast({
        origin       = Vector(pos.x, pos.y + 2, pos.z),
        direction    = {0, -1, 0},
        type         = 3,
        size         = {2 * scale.x + 0.5, 4, 2 * scale.z + 0.5},
        max_distance = 0,
    })
    local found, seen = {}, {}
    for _, hit in ipairs(hits) do
        local obj = hit.hit_object
        if isModelLike(obj) and not seen[obj.getGUID()] then
            seen[obj.getGUID()] = true
            table.insert(found, obj)
        end
    end
    return found
end

function targetModels(playerColor)
    local found = {}
    local player = Player[playerColor]
    if player ~= nil then
        for _, obj in ipairs(player.getSelectedObjects() or {}) do
            if isModelLike(obj) then table.insert(found, obj) end
        end
    end
    if #found == 0 then found = modelsOnNode() end
    return found
end

-- Apply every block to the script TEXT, then set it and reload once. injectBlock
-- sets the script and schedules its own reload, so it runs against a plain-table
-- stand-in here; calling it on the model per block would reload it repeatedly.
function installBlocks(model)
    local text = model.getLuaScript() or ""
    local proxy = {
        getLuaScript = function() return text end,
        setLuaScript = function(s) text = s end,
        reload = function() end,
    }
    local existed = false
    for _, b in ipairs(NODE_BLOCKS) do
        if injectBlock(proxy, b.start, b.finish, b.code) then existed = true end
    end
    model.setLuaScript(text)
    Wait.frames(function() if model ~= nil then model.reload() end end, 10)
    return existed
end

function installTool(playerColor)
    local models = targetModels(playerColor)
    if #models == 0 then
        broadcastToColor("Place a model on the node, or select models, then load again.", playerColor, Color.Orange)
        return
    end
    local added, updated = 0, 0
    for _, model in ipairs(models) do
        if installBlocks(model) then
            updated = updated + 1
        else
            added = added + 1
        end
    end
    broadcastToColor(string.format("%s test (%s): added to %d, updated on %d model(s). %s",
        NODE_TOOL, NODE_BUILD, added, updated, NODE_HINT), playerColor, {0.2, 0.85, 0.3})
end

function removeTool(playerColor)
    local removed = 0
    for _, model in ipairs(targetModels(playerColor)) do
        local lua = model.getLuaScript() or ""
        local changed = false
        for _, b in ipairs(NODE_BLOCKS) do
            local s = lua:find(b.start, 1, true)
            if s then
                local e = lua:find(b.finish, s, true)
                local nl = e and lua:find("\n", e, true)
                lua = (lua:sub(1, s - 1) .. (nl and lua:sub(nl + 1) or "")):gsub("%s+$", "")
                changed = true
            end
        end
        if changed then
            model.setLuaScript(lua)
            Wait.frames(function() if model ~= nil then model.reload() end end, 10)
            removed = removed + 1
        end
    end
    broadcastToColor(string.format("%s removed from %d model(s).", NODE_TOOL, removed), playerColor, {0.9, 0.9, 0.9})
end

function onLoadButton(_, playerColor)
    installTool(playerColor)
end

-- Move-tool catcher debug switches (Global vars read by move-tool.lua at the
-- start of each Move/Dash). Take effect on the NEXT move.
function moveDebugReport(playerColor)
    broadcastToColor(string.format("Move catcher: mode=%s  visible=%s  helper interactable=%s  (applies to the next move)",
        tostring(Global.getVar("KT_MOVE_CATCHER_MODE") or "player_ui"),
        tostring(Global.getVar("KT_MOVE_CATCHER_DEBUG") == true),
        tostring(Global.getVar("KT_MOVE_HELPER_INTERACTABLE") == true)), playerColor, {0.6, 1, 0.6})
end

function addMoveDebugItems()
    self.addContextMenuItem("Debug: catcher visible", function(pc)
        Global.setVar("KT_MOVE_CATCHER_DEBUG", Global.getVar("KT_MOVE_CATCHER_DEBUG") ~= true)
        moveDebugReport(pc)
    end, true)
    self.addContextMenuItem("Debug: catcher mode", function(pc)
        local m = Global.getVar("KT_MOVE_CATCHER_MODE")
        Global.setVar("KT_MOVE_CATCHER_MODE", (m == "button") and "player_ui" or "button")
        moveDebugReport(pc)
    end, true)
    self.addContextMenuItem("Debug: helper interactable", function(pc)
        Global.setVar("KT_MOVE_HELPER_INTERACTABLE", Global.getVar("KT_MOVE_HELPER_INTERACTABLE") ~= true)
        moveDebugReport(pc)
    end, true)
    self.addContextMenuItem("Debug: remove stray catchers", function(pc)
        local n = 0
        for _, o in ipairs(getObjectsWithTag("KTMoveCatcher")) do
            o.destruct()
            n = n + 1
        end
        broadcastToColor(string.format("Removed %d move-catcher helper(s).", n), pc, {0.6, 1, 0.6})
    end)
end

function onLoad()
    self.addContextMenuItem("Load " .. NODE_TOOL:lower() .. " onto model", function(pc) installTool(pc) end)
    self.addContextMenuItem("Remove " .. NODE_TOOL:lower() .. " from model", function(pc) removeTool(pc) end)
    if NODE_MOVE_DEBUG then addMoveDebugItems() end
    self.createButton({
        click_function = "onLoadButton",
        function_owner = self,
        label          = "Load " .. NODE_TOOL,
        tooltip        = "Install the " .. NODE_TOOL:lower() .. " tool (" .. NODE_BUILD .. ") on the selected models, or the models standing on this node.",
        position       = {0, 0.15, 0.75},
        width          = 1100,
        height         = 260,
        font_size      = 130,
    })
end
