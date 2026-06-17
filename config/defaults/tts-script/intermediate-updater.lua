-- Intermediate box updater (slim).
--
-- Embedded in the legacy save-file wrapper {Team} Box.json. Sole purpose:
-- replace this box with the full clean {Team}.json from team-urls.json.
--
-- The wrapper exists only as a compatibility hop for in-the-wild boxes that
-- still reference the old Box.json filename. Users who land here should
-- update immediately and never reuse this intermediate.
--
-- Spawn-format note: the target file is a bare Custom_Model_Bag object
-- handed straight to spawnObjectJSON (no save-file slicing needed).

local BUTTON_UPDATE_NOW = {
    label = "UPDATE\nNOW",
    click_function = "click_update_now",
    function_owner = self,
    position = {0, 0.3, 0},
    rotation = {0, 180, 0},
    height = 900, width = 1400,
    font_size = 280,
    color = {0.85, 0.1, 0.1}, font_color = {1, 1, 1},
    tooltip = "Replace this intermediate box with the latest full version."
}

function onLoad()
    self.clearButtons()
    self.createButton(BUTTON_UPDATE_NOW)
    self.addContextMenuItem("Update to latest", click_update_now)
end

function click_update_now()
    -- Derive team slug + base repo URL from this box's MeshURL so we follow
    -- whichever branch/fork the user spawned the box from.
    local data = self.getData() or {}
    local meshUrl = ((data.CustomMesh or {}).MeshURL) or ""
    if meshUrl == "" then
        broadcastToAll("Update failed: missing box mesh URL", {1, 0.5, 0})
        return
    end
    local cleanMeshUrl = string.match(meshUrl, "^[^?]+") or meshUrl
    local baseUrl = string.match(cleanMeshUrl, "^(.-)/output/")
    local teamSlug = string.match(cleanMeshUrl, "/output/([^/]+)/")
    if not baseUrl or baseUrl == "" or not teamSlug or teamSlug == "" then
        broadcastToAll("Update failed: could not parse repository URL", {1, 0.5, 0})
        return
    end

    local metadataUrl = baseUrl .. "/output/team-urls.json?v=" .. tostring(os.time())
    broadcastToAll("Checking for latest " .. teamSlug .. "...", {1, 1, 0})

    WebRequest.get(metadataUrl, function(req)
        if req.is_error then
            broadcastToAll("Update failed: " .. req.error, {1, 0.5, 0})
            return
        end
        local ok, metadata = pcall(function() return JSON.decode(req.text) end)
        if not ok or type(metadata) ~= "table" then
            broadcastToAll("Update failed: could not parse team-urls.json", {1, 0.5, 0})
            return
        end
        local entry = metadata[teamSlug]
        if type(entry) ~= "table" or type(entry.box) ~= "table" then
            broadcastToAll("Update failed: team not found in team-urls.json", {1, 0.5, 0})
            return
        end
        local boxUrl = entry.box.url or ""
        if boxUrl == "" then
            broadcastToAll("Update failed: no box URL for team", {1, 0.5, 0})
            return
        end

        broadcastToAll("Downloading latest version...", {0, 0.7, 1})
        WebRequest.get(boxUrl, function(resp)
            local code = tonumber(resp.response_code) or 0
            if resp.is_error or code >= 400 then
                local msg = resp.error
                if msg == nil or msg == "" then msg = "HTTP " .. tostring(code) end
                broadcastToAll("Download failed: " .. msg .. " (" .. boxUrl .. ")", {1, 0.5, 0})
                return
            end
            local body = resp.text or ""
            -- Strip leading whitespace; bare object must start with '{'.
            local startIdx = 1
            while startIdx <= #body and (body:byte(startIdx) == 32 or body:byte(startIdx) == 9 or body:byte(startIdx) == 10 or body:byte(startIdx) == 13) do
                startIdx = startIdx + 1
            end
            if startIdx > #body or body:byte(startIdx) ~= 123 then
                broadcastToAll("Update failed: unexpected response format (HTTP " .. tostring(code) .. ")", {1, 0.5, 0})
                return
            end
            local objJson = (startIdx == 1) and body or body:sub(startIdx)

            local pos = self.getPosition()
            local rot = self.getRotation()
            local locked = self.getLock()

            local spawned = spawnObjectJSON({
                json = objJson,
                position = pos + Vector(5, 0, 0),
                rotation = rot
            })
            if spawned == nil then
                broadcastToAll("Update failed: could not spawn new box", {1, 0.5, 0})
                return
            end

            Wait.condition(
                function()
                    Wait.time(function()
                        if spawned == nil or spawned.isDestroyed() then
                            broadcastToAll("Update failed during spawn", {1, 0.5, 0})
                            return
                        end
                        spawned.setLock(locked)
                        self.destruct()
                        Wait.time(function()
                            spawned.setPositionSmooth(pos, false, true)
                            spawned.setRotationSmooth(rot, false, true)
                            broadcastToAll("Updated to latest version!", {0, 1, 0})
                        end, 0.5)
                    end, 0.5)
                end,
                function() return spawned ~= nil and not spawned.spawning end,
                10
            )
        end)
    end)
end
