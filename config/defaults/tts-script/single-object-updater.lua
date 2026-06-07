-- kt-datacards: Single object updater
-- Adds right-click "Update" on cards and token dispensers.
-- It checks object-urls.json for this specific object and respawns it from
-- the latest team box JSON when an update is available.

local function ktu_strip_query(url)
    if not url or url == "" then return "" end
    return (string.match(url, "^[^?]+") or url)
end

local function ktu_url_signature(url)
    local clean = ktu_strip_query(url or "")
    if clean == "" then return "" end
    local sig = string.match(clean, "(/output/[^%s]+)$")
    if sig and sig ~= "" then
        return string.lower(sig)
    end
    return string.lower(clean)
end

local function ktu_append_cache_bust(url, value)
    if not url or url == "" then return url end
    if string.find(url, "?", 1, true) then
        return url .. "&v=" .. tostring(value)
    end
    return url .. "?v=" .. tostring(value)
end

local function ktu_get_v_query(url)
    if not url or url == "" then return nil end
    local v = string.match(url, "[?&]v=(%d+)")
    if not v then return nil end
    return tonumber(v)
end

local function ktu_is_target_url(currentUrl, targetUrl)
    if not targetUrl or targetUrl == "" then return false end
    local curSig = ktu_url_signature(currentUrl or "")
    local tgtSig = ktu_url_signature(targetUrl or "")
    if curSig == "" or tgtSig == "" or curSig ~= tgtSig then
        return false
    end

    local tgtV = ktu_get_v_query(targetUrl)
    if not tgtV then
        return true
    end

    local curV = ktu_get_v_query(currentUrl)
    return curV ~= nil and curV == tgtV
end

local function ktu_to_stamp(ts)
    local num = tostring(ts or ""):gsub("[^%d]", "")
    return tonumber(num) or 0
end

local function ktu_decode_script_state()
    if not self.script_state or self.script_state == "" then
        return {}
    end
    local ok, state = pcall(function() return JSON.decode(self.script_state) end)
    if ok and state and type(state) == "table" then
        return state
    end
    return {}
end

local function ktu_clone(value)
    local ok, encoded = pcall(function() return JSON.encode(value) end)
    if not ok or not encoded then return value end
    local ok2, decoded = pcall(function() return JSON.decode(encoded) end)
    if ok2 and decoded then return decoded end
    return value
end

local function ktu_save_script_state(state)
    local encoded = JSON.encode(state or {})
    self.script_state = encoded
    -- Some object types persist better through the setter API.
    pcall(function()
        if self.setLuaScriptState then
            self.setLuaScriptState(encoded)
        end
    end)
end

local function ktu_get_custom_deck_entry(cardData)
    local customDeck = cardData and cardData.CustomDeck
    if type(customDeck) ~= "table" then return nil end
    for _, entry in pairs(customDeck) do
        if type(entry) == "table" and entry.FaceURL then
            return entry
        end
    end
    return nil
end

local function ktu_script_has_updater(scriptText)
    if not scriptText or scriptText == "" then return false end
    return string.find(scriptText, "registerSingleObjectUpdaterMenu", 1, true) ~= nil
end

local function ktu_pick_script_with_updater(preferredScript, fallbackScript)
    if ktu_script_has_updater(preferredScript) then
        return preferredScript
    end
    if ktu_script_has_updater(fallbackScript) then
        return fallbackScript
    end
    return preferredScript or fallbackScript or ""
end

local function ktu_collect_self_info()
    local data = self.getData()
    if type(data) ~= "table" then
        return nil, "Could not read object data"
    end

    local info = { data = data, kind = "" }

    if data.Name == "Card" then
        local entry = ktu_get_custom_deck_entry(data)
        info.kind = "card"

        local face = ""
        local back = ""
        if entry then
            face = entry.FaceURL or ""
            back = entry.BackURL or ""
        end

        -- Some spawned cards do not preserve BackURL in getData().
        -- Fall back to getCustomObject() so no-op checks stay accurate.
        local custom = self.getCustomObject() or {}
        if face == "" then
            face = custom.FaceURL or custom.face or ""
        end
        if back == "" then
            back = custom.BackURL or custom.back or ""
        end

        info.face = face
        info.back = back
        info.firstUrl = info.face ~= "" and info.face or info.back

        if info.firstUrl == "" then
            return nil, "Card has no custom deck URLs"
        end

    elseif data.Name == "Custom_Model_Infinite_Bag" then
        local meshUrl = ((data.CustomMesh or {}).MeshURL) or ""
        local texUrl = ""
        if type(data.ContainedObjects) == "table" and #data.ContainedObjects > 0 then
            texUrl = (((data.ContainedObjects[1] or {}).CustomImage or {}).ImageURL) or ""
        end
        if texUrl == "" and type(data.ChildObjects) == "table" and #data.ChildObjects > 0 then
            texUrl = (((data.ChildObjects[1] or {}).CustomImage or {}).ImageURL) or ""
        end
        info.kind = "token-dispenser"
        info.mesh = meshUrl
        info.texture = texUrl
        info.firstUrl = meshUrl ~= "" and meshUrl or texUrl

    else
        return nil, "Update is supported on cards and token dispensers only"
    end

    if info.firstUrl == "" then
        return nil, "Could not determine source URL"
    end

    info.team = string.match(info.firstUrl, "/output/([^/]+)/")
    if not info.team or info.team == "" then
        return nil, "Could not determine team"
    end

    local stripped = ktu_strip_query(info.firstUrl)
    info.rawBase = string.match(stripped, "^(.-)/output/")
    if (not info.rawBase or info.rawBase == "") then
        -- Legacy fallback for older URL shapes.
        info.rawBase = string.match(stripped, "^(https://raw%.githubusercontent%.com/[^/]+/[^/]+/[^/]+)")
    end
    if not info.rawBase or info.rawBase == "" then
        return nil, "Could not determine repo branch URL"
    end

    info.tags = data.Tags or {}
    info.isDatacard = false
    for _, t in ipairs(info.tags) do
        if t == "KTCardsDatacard" then
            info.isDatacard = true
            break
        end
    end

    return info
end

local function ktu_find_matching_metadata_object(teamData, info)
    if not teamData or type(teamData.objects) ~= "table" then
        return nil
    end

    if info.kind == "card" then
        local faceNow = ktu_strip_query(info.face)
        local backNow = ktu_strip_query(info.back)
        local faceSigNow = ktu_url_signature(info.face)
        local backSigNow = ktu_url_signature(info.back)
        for _, obj in ipairs(teamData.objects) do
            if obj.face_url and obj.back_url then
                local faceRemote = ktu_strip_query(obj.face_url)
                local backRemote = ktu_strip_query(obj.back_url)
                local faceSigRemote = ktu_url_signature(obj.face_url)
                local backSigRemote = ktu_url_signature(obj.back_url)
                if (faceNow ~= "" and faceNow == faceRemote)
                    or (backNow ~= "" and backNow == backRemote)
                    or (faceSigNow ~= "" and faceSigNow == faceSigRemote)
                    or (backSigNow ~= "" and backSigNow == backSigRemote) then
                    return obj
                end
            end
        end
    elseif info.kind == "token-dispenser" then
        local meshNow = ktu_strip_query(info.mesh)
        local texNow = ktu_strip_query(info.texture)
        local meshSigNow = ktu_url_signature(info.mesh)
        local texSigNow = ktu_url_signature(info.texture)
        for _, obj in ipairs(teamData.objects) do
            if obj.type == "token" and obj.mesh_url and obj.texture_url then
                local meshRemote = ktu_strip_query(obj.mesh_url)
                local texRemote = ktu_strip_query(obj.texture_url)
                local meshSigRemote = ktu_url_signature(obj.mesh_url)
                local texSigRemote = ktu_url_signature(obj.texture_url)
                if (meshNow ~= "" and meshNow == meshRemote)
                    or (texNow ~= "" and texNow == texRemote)
                    or (meshSigNow ~= "" and meshSigNow == meshSigRemote)
                    or (texSigNow ~= "" and texSigNow == texSigRemote) then
                    return obj
                end
            end
        end
    end

    return nil
end

local function ktu_find_source_object_in_box(boxData, info, targetMeta)
    if type(boxData) ~= "table" then return nil end
    local states = boxData.ObjectStates or {}
    if #states == 0 then return nil end

    local wantedFace = targetMeta and ktu_strip_query(targetMeta.face_url) or ""
    local wantedFaceSig = targetMeta and ktu_url_signature(targetMeta.face_url) or ""
    local wantedMesh = targetMeta and ktu_strip_query(targetMeta.mesh_url) or ""
    local wantedMeshSig = targetMeta and ktu_url_signature(targetMeta.mesh_url) or ""
    local currentFace = ktu_strip_query(info.face or "")
    local currentFaceSig = ktu_url_signature(info.face or "")
    local currentMesh = ktu_strip_query(info.mesh or "")
    local currentMeshSig = ktu_url_signature(info.mesh or "")

    local function card_matches(faceUrl)
        local face = ktu_strip_query(faceUrl or "")
        local sig = ktu_url_signature(faceUrl or "")
        return (wantedFace ~= "" and face == wantedFace)
            or (currentFace ~= "" and face == currentFace)
            or (wantedFaceSig ~= "" and sig == wantedFaceSig)
            or (currentFaceSig ~= "" and sig == currentFaceSig)
    end

    local function mesh_matches(meshUrl)
        local mesh = ktu_strip_query(meshUrl or "")
        local sig = ktu_url_signature(meshUrl or "")
        return (wantedMesh ~= "" and mesh == wantedMesh)
            or (currentMesh ~= "" and mesh == currentMesh)
            or (wantedMeshSig ~= "" and sig == wantedMeshSig)
            or (currentMeshSig ~= "" and sig == currentMeshSig)
    end

    local function card_from_deck(deckObj)
        local customDeck = deckObj and deckObj.CustomDeck
        local contained = deckObj and deckObj.ContainedObjects
        if type(customDeck) ~= "table" or type(contained) ~= "table" then
            return nil
        end

        for deckId, deckEntry in pairs(customDeck) do
            if type(deckEntry) == "table" and card_matches(deckEntry.FaceURL) then
                local wantedCardId = tonumber(tostring(deckId) .. "00")
                local chosen = nil
                for _, c in ipairs(contained) do
                    if type(c) == "table" and c.Name == "Card" and c.CardID == wantedCardId then
                        chosen = c
                        break
                    end
                end
                if not chosen then
                    for _, c in ipairs(contained) do
                        if type(c) == "table" and c.Name == "Card" then
                            chosen = c
                            break
                        end
                    end
                end
                if chosen then
                    local out = ktu_clone(chosen)
                    out.CustomDeck = { [tostring(deckId)] = ktu_clone(deckEntry) }
                    out.Name = "Card"
                    out.SidewaysCard = false
                    out.HideWhenFaceDown = true
                    out.Hands = true
                    out.LuaScriptState = out.LuaScriptState or ""
                    out.XmlUI = out.XmlUI or ""
                    return out
                end
            end
        end
        return nil
    end

    local found = nil
    local function recurse(obj)
        if found then return end
        if type(obj) ~= "table" then return end

        if info.kind == "card" and obj.Name == "Card" then
            local entry = ktu_get_custom_deck_entry(obj)
            if entry and entry.FaceURL then
                if card_matches(entry.FaceURL) then
                    found = obj
                    return
                end
            end
        elseif info.kind == "card" and obj.Name == "Deck" then
            local extracted = card_from_deck(obj)
            if extracted then
                found = extracted
                return
            end
        elseif info.kind == "token-dispenser" and obj.Name == "Custom_Model_Infinite_Bag" then
            local mesh = ((obj.CustomMesh or {}).MeshURL) or ""
            if mesh_matches(mesh) then
                found = obj
                return
            end
        end

        for _, v in pairs(obj) do
            if type(v) == "table" then
                recurse(v)
                if found then return end
            end
        end
    end

    recurse(states[1])
    return found
end

-- Forward declaration so ktu_spawn_replacement closes over the local helper,
-- not a nil global.
local ktu_apply_current_transform

local function ktu_spawn_replacement(sourceObj, playerColor, targetModified)
    local spawnPos = self.getPosition()
    local spawnRot = self.getRotation()
    local wasLocked = self.getLock()

    local objCopy = ktu_clone(sourceObj)
    ktu_apply_current_transform(objCopy)

    -- Preserve updater capability even if remote source object script is stale.
    objCopy.LuaScript = ktu_pick_script_with_updater(
        objCopy.LuaScript,
        self.getLuaScript and self.getLuaScript() or ""
    )

    local newState = ktu_decode_script_state()
    newState.lastObjectUpdate = targetModified or os.date("!%Y-%m-%dT%H:%M:%SZ")
    objCopy.LuaScriptState = JSON.encode(newState)

    local spawned = spawnObjectJSON({
        json = JSON.encode(objCopy),
        position = spawnPos
    })

    Wait.condition(
        function()
            if spawned and not spawned.isDestroyed() then
                spawned.setRotationSmooth(spawnRot, false, true)
                spawned.setLock(wasLocked)
                self.destruct()
                broadcastToColor("Object updated", playerColor or "White", {0, 1, 0})
            end
        end,
        function()
            return spawned ~= nil and not spawned.spawning
        end,
        8
    )
end

local function ktu_update_card_in_place(targetMeta, sourceCardObj, playerColor)
    local custom = self.getCustomObject() or {}
    if targetMeta and targetMeta.face_url then
        custom.FaceURL = targetMeta.face_url
    end
    if targetMeta and targetMeta.back_url then
        custom.BackURL = targetMeta.back_url
    end

    local okSetCustom = pcall(function()
        self.setCustomObject(custom)
    end)
    if not okSetCustom then
        broadcastToColor("Could not update card URLs in place", playerColor or "White", {1, 0.5, 0})
        return false
    end

    if sourceCardObj and type(sourceCardObj) == "table" then
        if sourceCardObj.GMNotes ~= nil then
            pcall(function() self.setGMNotes(sourceCardObj.GMNotes or "") end)
        end
        local chosenScript = ktu_pick_script_with_updater(
            sourceCardObj.LuaScript,
            self.getLuaScript and self.getLuaScript() or ""
        )
        pcall(function() self.setLuaScript(chosenScript or "") end)
    end

    return true
end

ktu_apply_current_transform = function(sourceObj)
    local current = self.getData()
    local tr = current and current.Transform
    if type(tr) == "table" then
        sourceObj.Transform = sourceObj.Transform or {}
        sourceObj.Transform.posX = tr.posX or sourceObj.Transform.posX or 0
        sourceObj.Transform.posY = tr.posY or sourceObj.Transform.posY or 0
        sourceObj.Transform.posZ = tr.posZ or sourceObj.Transform.posZ or 0
        sourceObj.Transform.rotX = tr.rotX or sourceObj.Transform.rotX or 0
        sourceObj.Transform.rotY = tr.rotY or sourceObj.Transform.rotY or 0
        sourceObj.Transform.rotZ = tr.rotZ or sourceObj.Transform.rotZ or 0
        sourceObj.Transform.scaleX = tr.scaleX or sourceObj.Transform.scaleX or 1
        sourceObj.Transform.scaleY = tr.scaleY or sourceObj.Transform.scaleY or 1
        sourceObj.Transform.scaleZ = tr.scaleZ or sourceObj.Transform.scaleZ or 1
    end
end

function click_update_single_object(playerColor)
    local info, err = ktu_collect_self_info()
    if not info then
        broadcastToColor("Update failed: " .. tostring(err), playerColor or "White", {1, 0.5, 0})
        return
    end

    broadcastToColor("Checking update for this object...", playerColor or "White", {1, 1, 0})

    local metadataUrl = ktu_append_cache_bust(info.rawBase .. "/output/object-urls.json", os.time())
    WebRequest.get(metadataUrl, function(metaReq)
        if metaReq.is_error then
            broadcastToColor("Could not fetch object metadata: " .. tostring(metaReq.error), playerColor or "White", {1, 0.5, 0})
            return
        end

        local okMeta, metadata = pcall(function() return JSON.decode(metaReq.text) end)
        if not okMeta or type(metadata) ~= "table" then
            broadcastToColor("Could not parse object metadata", playerColor or "White", {1, 0.5, 0})
            return
        end

        local teamData = metadata[info.team]
        if (not teamData) and type(metadata) == "table" then
            -- Backward compatibility for old list-style metadata formats.
            for _, entry in ipairs(metadata) do
                if type(entry) == "table" and entry.team == info.team then
                    teamData = entry
                    break
                end
            end
        end
        if type(teamData) ~= "table" then
            broadcastToColor("No metadata entry for team: " .. tostring(info.team), playerColor or "White", {1, 0.5, 0})
            return
        end

        local targetMeta = ktu_find_matching_metadata_object(teamData, info)
        if not targetMeta then
            broadcastToColor("No matching metadata found for this object", playerColor or "White", {1, 0.5, 0})
            return
        end

        local state = ktu_decode_script_state()
        local localStamp = ktu_to_stamp(state.lastObjectUpdate)
        local remoteStamp = ktu_to_stamp(targetMeta.modified)

        local urlsChanged = false
        local alreadyAtTarget = false
        if info.kind == "card" then
            urlsChanged = (targetMeta.face_url and ktu_strip_query(targetMeta.face_url) ~= ktu_strip_query(info.face))
                or (targetMeta.back_url and ktu_strip_query(targetMeta.back_url) ~= ktu_strip_query(info.back))
            alreadyAtTarget = (not targetMeta.face_url or ktu_is_target_url(info.face, targetMeta.face_url))
                and (not targetMeta.back_url or ktu_is_target_url(info.back, targetMeta.back_url))
        elseif info.kind == "token-dispenser" then
            urlsChanged = (targetMeta.mesh_url and ktu_strip_query(targetMeta.mesh_url) ~= ktu_strip_query(info.mesh))
                or (targetMeta.texture_url and ktu_strip_query(targetMeta.texture_url) ~= ktu_strip_query(info.texture))
            alreadyAtTarget = (not targetMeta.mesh_url or ktu_is_target_url(info.mesh, targetMeta.mesh_url))
                and (not targetMeta.texture_url or ktu_is_target_url(info.texture, targetMeta.texture_url))
        end

        if alreadyAtTarget then
            broadcastToColor("This object is already up to date", playerColor or "White", {0, 1, 0})
            return
        end

        if (not urlsChanged) and remoteStamp ~= 0 and localStamp >= remoteStamp then
            broadcastToColor("This object is already up to date", playerColor or "White", {0, 1, 0})
            return
        end

        -- Always refresh from team box JSON so cards/token dispensers can pick up
        -- script/notes changes in addition to URL changes.
        if not teamData.box or not teamData.box.url then
            broadcastToColor("No team box URL found in metadata", playerColor or "White", {1, 0.5, 0})
            return
        end

        local boxUrl = ktu_append_cache_bust(teamData.box.url, os.time())
        WebRequest.get(boxUrl, function(boxReq)
            if boxReq.is_error then
                broadcastToColor("Could not download team box JSON: " .. tostring(boxReq.error), playerColor or "White", {1, 0.5, 0})
                return
            end

            local okBox, boxData = pcall(function() return JSON.decode(boxReq.text) end)
            if not okBox or type(boxData) ~= "table" then
                broadcastToColor("Could not parse team box JSON", playerColor or "White", {1, 0.5, 0})
                return
            end

            local sourceObj = ktu_find_source_object_in_box(boxData, info, targetMeta)
            if not sourceObj then
                broadcastToColor("Could not find matching object in team box JSON", playerColor or "White", {1, 0.5, 0})
                return
            end

            if info.kind == "token-dispenser" then
                ktu_spawn_replacement(sourceObj, playerColor, targetMeta.modified)
                return
            end

            if ktu_update_card_in_place(targetMeta, sourceObj, playerColor) then
                local newState = ktu_decode_script_state()
                newState.lastObjectUpdate = targetMeta.modified or os.date("!%Y-%m-%dT%H:%M:%SZ")
                ktu_save_script_state(newState)
                pcall(function() self.reload() end)
                broadcastToColor("Object updated", playerColor or "White", {0, 1, 0})
            end
        end)
    end)
end

function registerSingleObjectUpdaterMenu()
    if _ktu_update_menu_registered then return end
    _ktu_update_menu_registered = true
    self.addContextMenuItem("Update", function(playerColor)
        click_update_single_object(playerColor)
    end)
end

-- Preserve any existing onLoad logic by chaining it.
local _ktu_prev_onLoad = onLoad
function onLoad(...)
    if _ktu_prev_onLoad then
        pcall(_ktu_prev_onLoad, ...)
    end
    registerSingleObjectUpdaterMenu()
end
