-- Sprint test node: installs the embedded SPRINT_TOOL_CODE onto models so the
-- sprint tool can be tested without regenerating any datacards.
-- Built by tools/build_sprint_test_node.py, which prepends SPRINT_TOOL_CODE,
-- SPRINT_TEST_BUILD and the shared injectBlock/healExtenderScript helpers.

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

function installSprint(playerColor)
    local models = targetModels(playerColor)
    if #models == 0 then
        broadcastToColor("Place a model on the node, or select models, then load again.", playerColor, Color.Orange)
        return
    end
    local added, updated = 0, 0
    for _, model in ipairs(models) do
        if injectBlock(model, "-- START KT_SPRINT_TOOL_", "-- END KT_SPRINT_TOOL_", SPRINT_TOOL_CODE) then
            updated = updated + 1
        else
            added = added + 1
        end
    end
    broadcastToColor(string.format(
        "Sprint test (%s): added to %d, updated on %d model(s). Right-click model -> Sprint / Turn / Leap.",
        SPRINT_TEST_BUILD, added, updated), playerColor, {0.2, 0.85, 0.3})
end

function removeSprint(playerColor)
    local removed = 0
    for _, model in ipairs(targetModels(playerColor)) do
        local lua = model.getLuaScript() or ""
        local s = lua:find("-- START KT_SPRINT_TOOL_", 1, true)
        if s then
            local e = lua:find("-- END KT_SPRINT_TOOL_", s, true)
            local nl = e and lua:find("\n", e, true)
            lua = (lua:sub(1, s - 1) .. (nl and lua:sub(nl + 1) or "")):gsub("%s+$", "")
            model.setLuaScript(lua)
            Wait.frames(function() if model ~= nil then model.reload() end end, 10)
            removed = removed + 1
        end
    end
    broadcastToColor(string.format("Sprint tool removed from %d model(s).", removed), playerColor, {0.9, 0.9, 0.9})
end

function onLoadButton(_, playerColor)
    installSprint(playerColor)
end

function onLoad()
    self.addContextMenuItem("Load sprint onto model", function(pc) installSprint(pc) end)
    self.addContextMenuItem("Remove sprint from model", function(pc) removeSprint(pc) end)
    self.createButton({
        click_function = "onLoadButton",
        function_owner = self,
        label          = "Load Sprint",
        tooltip        = "Install the sprint tool (" .. SPRINT_TEST_BUILD .. ") on the selected models, or the models standing on this node.",
        position       = {0, 0.15, 0.75},
        width          = 900,
        height         = 260,
        font_size      = 130,
    })
end
