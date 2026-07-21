-- kt-datacards: Load Stats to Model
-- Card stores operative data in GMNotes (JSON).
-- Context menu "Load stats to model" finds a KTUIMini on top,
-- shows a weapon selection popup (if multiple weapons),
-- compares current vs new, reports diffs, and applies changes.

-- Persistent state for selection flow
local pendingData = nil
local pendingModel = nil
local pendingPlayerColor = nil
local selectionData = nil
local groupSelections = {}
local exclusiveSets = {}
local activeSet = 1

function onLoad()
    self.addContextMenuItem("Load stats to model", loadStatsToModel)
    self.addContextMenuItem("Load stats (all)", loadStatsToModelAll)
end

-- helpers

-- Object types we accept as a "model" that can receive stats. Any of these can
-- be turned into a KTUI extender mini on the fly.
local MODEL_TYPES = {
    Custom_Model      = true,
    Figurine_Custom   = true,
    Custom_Assetbundle= true,
    Figurine          = true,
}

function isModelLike(obj)
    return obj ~= nil and MODEL_TYPES[obj.type] == true
end

function findModelOnCard()
    local pos = self.getPosition()
    local hits = Physics.cast({
        origin       = Vector(pos.x, pos.y + 1.5, pos.z),
        direction    = {0, -1, 0},
        type         = 2,
        size         = {2, 2, 2},
        max_distance = 3,
    })
    for _, hit in ipairs(hits) do
        local obj = hit.hit_object
        if obj and obj ~= self and obj.hasTag("KTUIMini") then return obj end
    end
    for _, hit in ipairs(hits) do
        local obj = hit.hit_object
        if obj and obj ~= self and isModelLike(obj) then return obj end
    end
    return nil
end

function trunc(s, n)
    if s == nil then return "" end
    s = tostring(s)
    if #s <= n then return s end
    return s:sub(1, n) .. "..."
end

function valEq(a, b)
    return tostring(a) == tostring(b)
end

function tableEq(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return valEq(a, b) end
    if #a ~= #b then return false end
    for i = 1, #a do
        if not tableEq(a[i], b[i]) then return false end
    end
    for k, v in pairs(a) do
        if not tableEq(v, b[k]) then return false end
    end
    for k, v in pairs(b) do
        if a[k] == nil then return false end
    end
    return true
end

function rebuildDescription(data)
    local lines = {}
    table.insert(lines, string.format(
        "[D36B3E][[84E680]APL[-] [ffffff]%s[-]] [[84E680]MOVE[-] [ffffff]%s\"[-]]",
        tostring(data.stats.APL), tostring(data.stats.Move)))
    table.insert(lines, string.format(
        "[[84E680]SAVE[-] [ffffff]%s+[-]] [[84E680]WOUNDS[-] [ffffff]%s[-]][-]",
        tostring(data.stats.Save), tostring(data.stats.Wounds)))
    if data.keywords then
        table.insert(lines, "[C5C5C5]" .. table.concat(data.keywords, ", ") .. "[-]")
    end
    table.insert(lines, "[31B32B]Weapons[-]")
    if data.weapons then
        for _, w in ipairs(data.weapons) do
            table.insert(lines, w.name or "?")
            local s = w.stats or {}
            table.insert(lines, string.format("[84E680]ATK[-] %s [84E680]HIT[-] %s [84E680]DMG[-] %s",
                s.ATK or "?", s.HIT or "?", s.DMG or "?"))
            if s.WR and s.WR ~= "" then
                table.insert(lines, "[84E680]WR[-]: " .. s.WR)
            end
            table.insert(lines, "")
        end
    end
    if data.abilities and #data.abilities > 0 then
        table.insert(lines, "---")
        table.insert(lines, "[31B32B]Abilities[-]")
        for _, ab in ipairs(data.abilities) do
            table.insert(lines, "- [EF8450]" .. (ab.name or "?") .. "[-]")
        end
    end
    if data.actions and #data.actions > 0 then
        table.insert(lines, "[31B32B]Actions[-]")
        for _, ac in ipairs(data.actions) do
            table.insert(lines, "- [D46D6C]" .. (ac.name or "?") .. "[-]")
        end
    end
    return table.concat(lines, "\n")
end

-- weapon selection popup

function findSetForGroup(g)
    for s, set in ipairs(exclusiveSets) do
        for _, sg in ipairs(set) do
            if sg == g then return s end
        end
    end
    return 1
end

function isGroupInActiveSet(g)
    if #exclusiveSets == 0 then return true end
    for _, sg in ipairs(exclusiveSets[activeSet] or {}) do
        if sg == g then return true end
    end
    return false
end

function buildSelectionPanelXml(selection)
    local rows = ""
    local totalOptions = 0
    local orDividers = 0

    -- Track which groups start a new exclusive set (for OR dividers)
    local setStartGroups = {}
    if #exclusiveSets > 1 then
        for s = 2, #exclusiveSets do
            local firstGroup = exclusiveSets[s][1]
            setStartGroups[firstGroup] = true
        end
    end

    for g, group in ipairs(selection.groups) do
        local inActive = isGroupInActiveSet(g)

        -- OR divider between exclusive sets
        if setStartGroups[g] then
            rows = rows .. '<Text id="or_div" fontSize="10" fontStyle="Bold" color="#FF6600" '
                .. 'preferredHeight="20" alignment="MiddleCenter">---- OR ----</Text>\n'
            orDividers = orDividers + 1
        elseif g > 1 then
            rows = rows .. '<Image color="rgba(255,255,255,0.15)" preferredHeight="1" />\n'
        end
        if #selection.groups > 1 then
            local headerColor = inActive and "#AAAAAA" or "#555555"
            rows = rows .. string.format(
                '<Text id="hdr_%d" fontSize="10" fontStyle="Bold" color="%s" '
                .. 'preferredHeight="18" alignment="MiddleLeft">Choose one:</Text>\n',
                g, headerColor)
        end
        for o, option in ipairs(group) do
            local isOn = (inActive and o == 1) and "true" or "false"
            local textColor = inActive and "#FFFFFF" or "#666666"
            local label = option.label or ("Option " .. o)
            label = label:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;")
            label = label:gsub("; ", " + ")

            rows = rows .. string.format(
                '<Toggle id="sel_%d_%d" isOn="%s" '
                .. 'onValueChanged="onSelectionToggle" '
                .. 'fontSize="10" textColor="%s" colors="#444444|#666666|#333333|#222222" '
                .. 'toggleWidth="16" toggleHeight="16">'
                .. '%s</Toggle>\n',
                g, o, isOn, textColor, label
            )
            totalOptions = totalOptions + 1
        end
    end

    local headerText = #selection.groups > 1 and "Select Loadout" or "Select Weapon"

    return string.format([[
<Panel id="selectionPanel" active="true"
       width="224" height="%d"
       color="rgba(0,0,0,0.92)"
       padding="6 6 6 6"
       position="0 0 -50"
       rotation="0 0 180"
       allowDragging="true">
  <VerticalLayout spacing="2" childForceExpandWidth="true" childForceExpandHeight="false">
    <Text fontSize="12" fontStyle="Bold" color="#FF9900"
          alignment="MiddleCenter" preferredHeight="20">%s</Text>
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    %s
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    <HorizontalLayout spacing="4" preferredHeight="24">
      <Button id="btnApply" onClick="onApplySelection"
              fontSize="10" fontStyle="Bold"
              colors="#2E7D32|#388E3C|#1B5E20|#555555"
              textColor="#FFFFFF">Apply</Button>
      <Button id="btnCancel" onClick="onCancelSelection"
              fontSize="10"
              colors="#C62828|#D32F2F|#B71C1C|#555555"
              textColor="#FFFFFF">Cancel</Button>
    </HorizontalLayout>
  </VerticalLayout>
</Panel>
]], 64 + totalOptions * 22 + #selection.groups * 20 + orDividers * 22, headerText, rows)
end

function onSelectionToggle(player, value, id)
    local g, o = id:match("sel_(%d+)_(%d+)")
    g, o = tonumber(g), tonumber(o)
    if not g or not o then return end

    -- Handle exclusive set switching
    if #exclusiveSets > 1 and value == "True" then
        local clickedSet = findSetForGroup(g)
        if clickedSet ~= activeSet then
            activeSet = clickedSet
            -- Deselect and dim toggles in other sets; brighten active set
            for s, set in ipairs(exclusiveSets) do
                if s ~= activeSet then
                    for _, sg in ipairs(set) do
                        groupSelections[sg] = nil
                        self.UI.setAttribute("hdr_" .. sg, "color", "#555555")
                        for i = 1, #selectionData.groups[sg] do
                            self.UI.setAttribute("sel_" .. sg .. "_" .. i, "isOn", "false")
                            self.UI.setAttribute("sel_" .. sg .. "_" .. i, "textColor", "#666666")
                        end
                    end
                else
                    for _, sg in ipairs(set) do
                        self.UI.setAttribute("hdr_" .. sg, "color", "#AAAAAA")
                        for i = 1, #selectionData.groups[sg] do
                            self.UI.setAttribute("sel_" .. sg .. "_" .. i, "textColor", "#FFFFFF")
                        end
                        if not groupSelections[sg] and sg ~= g then
                            groupSelections[sg] = 1
                            self.UI.setAttribute("sel_" .. sg .. "_1", "isOn", "true")
                        end
                    end
                end
            end
        end
    end

    if value == "True" then
        groupSelections[g] = o
        -- Radio behavior: turn off other options in same group
        if selectionData and selectionData.groups and selectionData.groups[g] then
            for i = 1, #selectionData.groups[g] do
                if i ~= o then
                    self.UI.setAttribute("sel_" .. g .. "_" .. i, "isOn", "false")
                end
            end
        end
    else
        -- Prevent deselecting the current selection (radio: always one selected)
        if groupSelections[g] == o then
            self.UI.setAttribute(id, "isOn", "true")
        end
    end
end

function onApplySelection(player, value, id)
    self.UI.setXml("")
    if not pendingData or not pendingModel or not selectionData then return end

    -- Collect weapon indices from selections + fixed weapons
    local weaponSet = {}

    if selectionData.fixed then
        for _, idx in ipairs(selectionData.fixed) do
            weaponSet[idx + 1] = true  -- Convert 0-based to Lua 1-based
        end
    end

    -- Determine which groups to include (active set only, or all if no exclusive sets)
    local activeGroups = {}
    if #exclusiveSets > 0 then
        for _, g in ipairs(exclusiveSets[activeSet] or {}) do
            activeGroups[g] = true
        end
    else
        for g = 1, #selectionData.groups do
            activeGroups[g] = true
        end
    end

    for g, group in ipairs(selectionData.groups) do
        if activeGroups[g] then
            local sel = groupSelections[g] or 1
            local option = group[sel]
            if option and option.weapons then
                for _, idx in ipairs(option.weapons) do
                    weaponSet[idx + 1] = true
                end
            end
        end
    end

    -- Filter weapons to selected set
    local selectedWeapons = {}
    for i, w in ipairs(pendingData.weapons) do
        if weaponSet[i] then
            table.insert(selectedWeapons, w)
        end
    end
    pendingData.weapons = selectedWeapons

    -- Rebuild description with filtered weapons
    pendingData.description = rebuildDescription(pendingData)

    local changes = diffAndApply(pendingModel, pendingData)

    if #changes == 0 then
        broadcastToColor("Already up to date.", pendingPlayerColor, Color.White)
    elseif #changes == 1 then
        broadcastToColor("Updated: " .. changes[1], pendingPlayerColor, Color.Green)
    else
        local msg = "Updated:\n"
        for _, c in ipairs(changes) do
            msg = msg .. " - " .. c .. "\n"
        end
        broadcastToColor(msg, pendingPlayerColor, Color.Green)
    end

    pendingData = nil
    pendingModel = nil
    pendingPlayerColor = nil
    selectionData = nil
end

function onCancelSelection(player, value, id)
    self.UI.setXml("")
    broadcastToColor("Selection cancelled.", pendingPlayerColor or player.color, Color.White)
    pendingData = nil
    pendingModel = nil
    pendingPlayerColor = nil
    selectionData = nil
end

-- diff and apply

-- Backfill the minimal state that the KTUI extender model script expects so a
-- plain model becomes KTUI-compatible after loading stats. This only fills
-- missing fields, so it never overwrites an existing extender mini's data.
-- Only the bare basics needed by the extender (onLoad / refreshUI /
-- refreshVectors) are set here -- not the full Command Node feature set.
function ensureKtuiState(ms, data)
    ms.stats = ms.stats or {}
    ms.info  = ms.info or {}
    ms.info.categories = ms.info.categories or {}
    ms.info.weapons    = ms.info.weapons or {}
    ms.info.special    = ms.info.special or {}
    ms.info.psychic    = ms.info.psychic or {}
    ms.info.abilities  = ms.info.abilities or {}
    ms.info.actions    = ms.info.actions or {}
    ms.info.upgrades   = ms.info.upgrades or {}
    if ms.roles         == nil then ms.roles = {} end
    if ms.hiddenRoles   == nil then ms.hiddenRoles = {} end
    if ms.items         == nil then ms.items = {} end
    if ms.attachments   == nil then ms.attachments = {} end
    if ms.holding       == nil then ms.holding = false end
    -- uiHeight/uiAngle are read unguarded by the real KT UI extender's refreshUI
    -- (e.g. `"0 0 -"..tostring(state.uiHeight*100)`). A nil or non-number here is
    -- the classic "attempt to concatenate a nil value at refreshUI" crash, so we
    -- force them to valid numbers on every apply -- never leave them as-is.
    if type(ms.uiHeight) ~= "number" or ms.uiHeight <= 0 then ms.uiHeight = 2 end
    if type(ms.uiAngle)  ~= "number" then ms.uiAngle = 0 end
    if ms.display_arrows == nil then ms.display_arrows = false end
    if ms.base          == nil then
        local size = tonumber(data.stats and data.stats.Base) or 25
        ms.base = { x = size, z = size }
    end
    if ms.modelid == nil or ms.modelid == "" then
        local slug = tostring(data.name or "operative"):lower():gsub("[^%w]+", "-")
        slug = slug:gsub("^%-+", ""):gsub("%-+$", "")
        if slug == "" then slug = "operative" end
        ms.modelid = "ktui-" .. slug
    end
    -- owner intentionally left unset => the model is visible to all players.
end

function diffAndApply(model, data)
    local changes = {}

    local msRaw = model.script_state
    local ms = {}
    if msRaw and msRaw ~= "" then
        local ok, parsed = pcall(function() return JSON.decode(msRaw) end)
        if ok and parsed then ms = parsed end
    end

    -- What kind of model is this?
    --  * isKtui    : already a KTUI mini of ANY kind (our bundled one OR the real
    --                KT UI extender). If so we NEVER replace its script -- we just
    --                update its state in place so a fancy extender keeps its UI.
    --  * isManaged : specifically OUR bundled mini (we tag those "KTUIMiniDatacard").
    --                Only our own mini is safe to hard-reload() as a fallback,
    --                because its onLoad tolerates a missing owner.
    -- A truly plain model (neither tag) gets our bundled script installed.
    local isKtui    = model.hasTag("KTUIMini")
    local isManaged = model.hasTag("KTUIMiniDatacard")

    ms.stats = ms.stats or {}
    ms.info  = ms.info or {}

    ensureKtuiState(ms, data)

    -- 1. Core stats
    local oldMaxWounds = ms.stats["Wounds"]
    local statMap = {
        { key = "APL",    src = data.stats.APL    },
        { key = "Move",   src = data.stats.Move   },
        { key = "Save",   src = data.stats.Save   },
        { key = "Wounds", src = data.stats.Wounds },
    }
    for _, s in ipairs(statMap) do
        local old = ms.stats[s.key]
        local new = s.src
        if not valEq(old, new) then
            table.insert(changes, string.format("%s: %s -> %s", s.key, tostring(old or "-"), tostring(new)))
            ms.stats[s.key] = new
        end
    end

    -- Base size: physical base diameter (mm) used for the extender's base ring.
    -- Update it on every apply so swapping operatives resizes the ring.
    if data.stats and data.stats.Base ~= nil then
        local newBase = tonumber(data.stats.Base)
        if newBase then
            local oldBase = (type(ms.base) == "table") and tonumber(ms.base.x) or nil
            if not valEq(oldBase, newBase) then
                table.insert(changes, string.format("Base: %smm -> %smm", tostring(oldBase or "-"), tostring(newBase)))
            end
            ms.base = { x = newBase, z = newBase }
            ms.stats.Base = newBase
        end
    end

    -- Always reset wounds to full when loading stats
    if data.stats.Wounds then
        ms.wounds = data.stats.Wounds
        -- The real KT UI extender reads MAX wounds from the abbreviated key
        -- `state.stats.W` (not `Wounds`). Keep it in sync so switching operatives
        -- updates the fancy wound bar instead of showing the previous op's max.
        ms.stats.W = data.stats.Wounds
    end

    -- 2. Name
    if data.name and ms.info.name ~= data.name then
        table.insert(changes, string.format("Name: %s -> %s", trunc(ms.info.name, 30), data.name))
        ms.info.name = data.name
        ms.info.modelType = data.name
    end

    -- 3. Keywords
    if data.keywords and not tableEq(ms.info.categories, data.keywords) then
        table.insert(changes, "Keywords updated")
        ms.info.categories = data.keywords
    end

    -- 4. Weapons (always clear and replace)
    if data.weapons then
        local weaponNames = {}
        for _, w in ipairs(data.weapons) do
            table.insert(weaponNames, w.plain_name or "?")
        end
        table.insert(changes, string.format("Weapons: %s", table.concat(weaponNames, ", ")))

        ms.info.weapons = data.weapons

        local ups = {}
        for _, w in ipairs(data.weapons) do
            table.insert(ups, w.plain_name or w.name)
        end
        ms.info.upgrades = ups

        if data.weapon_rules then
            ms.info.rules = data.weapon_rules
        else
            ms.info.rules = {}
        end
    end

    -- 5. Abilities
    if data.abilities then
        local oldA = ms.info.abilities or {}
        if not tableEq(oldA, data.abilities) then
            for _, ab in ipairs(data.abilities) do
                table.insert(changes, string.format("Ability: %s", ab.name or "?"))
            end
            ms.info.abilities = data.abilities
        end
    end

    -- 6. Actions
    if data.actions then
        local oldAc = ms.info.actions or {}
        if not tableEq(oldAc, data.actions) then
            for _, ac in ipairs(data.actions) do
                table.insert(changes, string.format("Action: %s", ac.name or "?"))
            end
            ms.info.actions = data.actions
        end
    end

    -- 7. Description
    if data.description then
        local oldDesc = model.getDescription()
        if oldDesc ~= data.description then
            model.setDescription(data.description)
            if #changes == 0 then
                table.insert(changes, "Description updated")
            end
        end
    end

    -- 8. Nickname (order + wounds + name)
    if data.stats and data.stats.Wounds then
        local w = data.stats.Wounds
        local cur = model.getName()
        local wStr = string.format("{%d/%d}", w, w)
        -- Extract order prefix (e.g. "[FF5500]E[-] ") if present
        local prefix = cur:match("^(%[%x+%].-%[%-%]%s*)") or ""
        cur = prefix .. wStr .. " " .. (data.name or cur)
        model.setName(cur)
    end

    -- Write back
    -- Only a truly plain model (no KTUI mini tag at all) gets our bundled script
    -- installed. If the model is already a KTUI mini -- whether our bundled one or
    -- the real KT UI extender the player upgraded it to -- we leave its script and
    -- fancy UI intact and just refresh it in place.
    local needsScript = (not isKtui) and KTUI_MODELSCRIPT ~= nil and KTUI_MODELSCRIPT ~= ""
    if #changes > 0 or needsScript then
        model.script_state = JSON.encode(ms)
        if needsScript then
            -- Convert a plain model into our bundled KTUI mini: attach our model
            -- script + tags, then reload to activate. Our onLoad tolerates a missing
            -- owner, so this is safe.
            model.setLuaScript(KTUI_MODELSCRIPT)
            if not model.hasTag("KTUIMini") then model.addTag("KTUIMini") end
            model.addTag("KTUIMiniDatacard")
            table.insert(changes, "Prepared model for KTUI extender")
            model.reload()
        else
            -- Already a KTUI mini (ours OR the real extender): refresh in place so
            -- the existing script/UI is preserved. Redraw the base ring
            -- (refreshVectors) AND the status UI (refreshUI). Each is guarded so one
            -- failure can't halt the apply. Fall back to a full reload() ONLY for our
            -- own bundled mini -- reloading a foreign extender could nil-crash its
            -- ownership setup, and we must never wipe the player's fancy UI.
            local ok = pcall(function()
                model.call("loadState")
                pcall(function() model.call("refreshVectors") end)
                model.call("refreshUI")
            end)
            -- If an in-place refresh threw (e.g. a foreign extender hit an
            -- unguarded field before our written state fully applied), fall back to
            -- a full reload. reload() re-runs the extender's own onLoad -> loadState,
            -- which re-reads the valid script_state we just wrote (uiHeight etc.
            -- guaranteed present), rebuilding the fancy UI cleanly. Guarded so a
            -- foreign onLoad that dislikes reload can't halt the apply.
            if not ok then
                pcall(function() model.reload() end)
            end
        end
    end

    return changes
end

-- main entry

function loadStatsToModelAll(playerColor)
    local raw = self.getGMNotes()
    if raw == nil or raw == "" then
        broadcastToColor("No stat data on this card.", playerColor, Color.Red)
        return
    end

    local ok, data = pcall(function() return JSON.decode(raw) end)
    if not ok or data == nil then
        broadcastToColor("Failed to parse card data.", playerColor, Color.Red)
        return
    end

    local model = findModelOnCard()
    if model == nil then
        broadcastToColor("Place a model on this card first.", playerColor, Color.Orange)
        return
    end

    -- Apply all weapons directly, ignoring selection
    local changes = diffAndApply(model, data)
    if #changes == 0 then
        broadcastToColor("Already up to date.", playerColor, Color.White)
    elseif #changes == 1 then
        broadcastToColor("Updated: " .. changes[1], playerColor, Color.Green)
    else
        local msg = "Updated:\n"
        for _, c in ipairs(changes) do
            msg = msg .. " - " .. c .. "\n"
        end
        broadcastToColor(msg, playerColor, Color.Green)
    end
end

function loadStatsToModel(playerColor)
    local raw = self.getGMNotes()
    if raw == nil or raw == "" then
        broadcastToColor("No stat data on this card.", playerColor, Color.Red)
        return
    end

    local ok, data = pcall(function() return JSON.decode(raw) end)
    if not ok or data == nil then
        broadcastToColor("Failed to parse card data.", playerColor, Color.Red)
        return
    end

    local model = findModelOnCard()
    if model == nil then
        broadcastToColor("Place a model on this card first.", playerColor, Color.Orange)
        return
    end

    -- Check for selection data (operatives with weapon loadout choices)
    if data.selection and data.selection.groups and #data.selection.groups > 0 then
        pendingData = data
        pendingModel = model
        pendingPlayerColor = playerColor
        selectionData = data.selection

        -- Initialize exclusive sets (convert 0-based to 1-based)
        exclusiveSets = {}
        if data.selection.exclusive_sets then
            for _, set in ipairs(data.selection.exclusive_sets) do
                local luaSet = {}
                for _, idx in ipairs(set) do
                    table.insert(luaSet, idx + 1)
                end
                table.insert(exclusiveSets, luaSet)
            end
        end
        activeSet = 1

        -- Pre-select first option in each group of the active set
        groupSelections = {}
        if #exclusiveSets > 0 then
            for _, g in ipairs(exclusiveSets[activeSet]) do
                groupSelections[g] = 1
            end
        else
            for g = 1, #data.selection.groups do
                groupSelections[g] = 1
            end
        end

        self.UI.setXml(buildSelectionPanelXml(data.selection))
        broadcastToColor("Select loadout, then click Apply.", playerColor, Color.Yellow)
    else
        -- No selection choices: apply all weapons directly
        local changes = diffAndApply(model, data)
        if #changes == 0 then
            broadcastToColor("Already up to date.", playerColor, Color.White)
        elseif #changes == 1 then
            broadcastToColor("Updated: " .. changes[1], playerColor, Color.Green)
        else
            local msg = "Updated:\n"
            for _, c in ipairs(changes) do
                msg = msg .. " - " .. c .. "\n"
            end
            broadcastToColor(msg, playerColor, Color.Green)
        end
    end
end
