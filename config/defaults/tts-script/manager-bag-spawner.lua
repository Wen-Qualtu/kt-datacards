-- Manager bag one-shot spawner.
--
-- Downloads the bare Custom_Bag JSON for the KT Display Manager
-- (output/_generic-tts-objects/Kill Team Card Boxes.json) and hands the raw
-- text straight to spawnObjectJSON. No JSON.decode of the ~30MB payload.
-- After spawning, this spawner tile destroys itself.
--
-- The bare JSON contains all 47 team boxes pre-cache-busted by the Python
-- pipeline, so no in-Lua URL rewriting is needed.

local MANAGER_BAG_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/_generic-tts-objects/Kill%20Team%20Card%20Boxes.json"

local BUTTON_SPAWN = {
    label = "SPAWN\nMANAGER\nBAG",
    click_function = "click_spawn_manager",
    function_owner = self,
    position = {0, 0.3, 0},
    rotation = {0, 180, 0},
    height = 1100, width = 1400,
    font_size = 220,
    color = {0.1, 0.5, 0.85}, font_color = {1, 1, 1},
    tooltip = "Download and spawn the KT Display Manager bag with all 47 teams."
}

function onLoad()
    self.clearButtons()
    self.createButton(BUTTON_SPAWN)
    self.addContextMenuItem("Spawn Manager Bag", click_spawn_manager)
end

function click_spawn_manager()
    broadcastToAll("Downloading manager bag (~30MB, may take a moment)...", {0.2, 0.7, 1})

    local url = MANAGER_BAG_URL .. "?v=" .. tostring(os.time())
    WebRequest.get(url, function(resp)
        local code = tonumber(resp.response_code) or 0
        if resp.is_error or code >= 400 then
            local msg = resp.error
            if msg == nil or msg == "" then msg = "HTTP " .. tostring(code) end
            broadcastToAll("Download failed: " .. msg, {1, 0.5, 0})
            return
        end

        local body = resp.text or ""
        -- Skip leading whitespace; bare object must start with '{'.
        local startIdx = 1
        while startIdx <= #body do
            local b = body:byte(startIdx)
            if b ~= 32 and b ~= 9 and b ~= 10 and b ~= 13 then break end
            startIdx = startIdx + 1
        end
        if startIdx > #body or body:byte(startIdx) ~= 123 then
            broadcastToAll("Spawn failed: unexpected response format (HTTP " .. tostring(code) .. ")", {1, 0.5, 0})
            return
        end
        local objJson = (startIdx == 1) and body or body:sub(startIdx)

        local pos = self.getPosition()
        local rot = self.getRotation()

        broadcastToAll("Spawning manager bag with 47 teams...", {0.2, 0.7, 1})

        local spawned = spawnObjectJSON({
            json = objJson,
            position = pos + Vector(0, 2, 0),
            rotation = rot
        })

        if spawned == nil then
            broadcastToAll("Spawn failed: spawnObjectJSON returned nil", {1, 0.5, 0})
            return
        end

        Wait.condition(
            function()
                Wait.time(function()
                    if spawned == nil or spawned.isDestroyed() then
                        broadcastToAll("Spawn failed during initialization", {1, 0.5, 0})
                        return
                    end
                    broadcastToAll("Manager bag spawned!", {0, 1, 0})
                    self.destruct()
                end, 0.5)
            end,
            function() return spawned ~= nil and not spawned.spawning end,
            60
        )
    end)
end
