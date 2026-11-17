-- Test node: installs one embedded tool block (NODE_BLOCK_CODE) onto models so a
-- tool can be tested without regenerating any datacards.
-- Built by tools/build_test_node.py, which prepends NODE_TOOL, NODE_BUILD,
-- NODE_BLOCK_START/END, NODE_BLOCK_CODE, NODE_HINT and the shared
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

-- Replace mode (NODE_REPLACE): swap the model's whole script for NODE_BLOCK_CODE,
-- as the original extender's "Extend KT UI" does. Saved state is kept.
function replaceScript(model, playerColor)
    model.setLuaScript(NODE_BLOCK_CODE)
    model = model.reload()
    model.addTag("KTUIMini")
    local player = Player[playerColor]
    if player and player.steam_id then
        Wait.frames(function() model.call("setOwningPlayer", player.steam_id) end, 1)
    end
end

function installTool(playerColor)
    local models = targetModels(playerColor)
    if #models == 0 then
        broadcastToColor("Place a model on the node, or select models, then load again.", playerColor, Color.Orange)
        return
    end
    if NODE_REPLACE then
        for _, model in ipairs(models) do replaceScript(model, playerColor) end
        broadcastToColor(string.format("%s test (%s): replaced the script on %d model(s). %s",
            NODE_TOOL, NODE_BUILD, #models, NODE_HINT), playerColor, {0.2, 0.85, 0.3})
        return
    end
    local added, updated = 0, 0
    for _, model in ipairs(models) do
        if injectBlock(model, NODE_BLOCK_START, NODE_BLOCK_END, NODE_BLOCK_CODE) then
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
        local s = lua:find(NODE_BLOCK_START, 1, true)
        if s then
            local e = lua:find(NODE_BLOCK_END, s, true)
            local nl = e and lua:find("\n", e, true)
            lua = (lua:sub(1, s - 1) .. (nl and lua:sub(nl + 1) or "")):gsub("%s+$", "")
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

function onLoad()
    self.addContextMenuItem("Load " .. NODE_TOOL:lower() .. " onto model", function(pc) installTool(pc) end)
    if not NODE_REPLACE then
        self.addContextMenuItem("Remove " .. NODE_TOOL:lower() .. " from model", function(pc) removeTool(pc) end)
    end
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
