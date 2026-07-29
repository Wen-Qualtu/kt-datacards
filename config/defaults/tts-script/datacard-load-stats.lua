-- kt-datacards: Load Stats to Model
-- Card stores operative data in GMNotes (JSON).
-- Context menu "Load stats" finds a KTUIMini on top,
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

-- Faction-rule "Choose upgrades" flow. Mounted operatives pick N of the
-- <archetype> UPGRADE options embedded in GMNotes.upgrades = {select, options}.
local upgradeOptions = nil
local upgradeChosen = {}
local upgradeSelect = 2
local upgradeModel = nil
local upgradeData = nil
local upgradePlayerColor = nil

-- Context menu order (TTS shows items top -> bottom in REGISTRATION order):
--   1. Update card        reserved top slot (self-update lives in the updater
--                          tools; not wired here yet -- see TODO).
--   2. Load everything    one button: stats (+loadout) -> faction upgrades ->
--                          operative counters -> movement. Excludes Rotate base.
--   3. Load stats          stats + weapons; ALWAYS forces the loadout popup when present.
--   4. Movement           Move (non-mounted) or Sprint/Turn/Leap (mounted).
--   5. Faction specifics   e.g. Choose upgrades (chapter tactics / gore tank / counters).
--   6. Special            low-frequency extras (Rotate base 90), always last.
function onLoad()
    -- 1. TODO: "Update card" self-update item belongs here, at the very top.

    -- 2. One-button setup: stats + loadout + faction rules + movement.
    self.addContextMenuItem("Load everything", loadEverything)

    -- 3. Stats only. Always prompts the loadout selection when the operative has
    --    one (there is no silent "apply all" anymore).
    self.addContextMenuItem("Load stats", loadStatsToModel)

    -- 4. Movement action for the model on top (keyword-gated by embedded code).
    if type(SPRINT_TOOL_CODE) == "string" and hasKeyword("MOUNTED") then
        self.addContextMenuItem("Add sprint action", addSprintAction)
    end
    if type(MOVE_TOOL_CODE) == "string" and not hasKeyword("MOUNTED") then
        self.addContextMenuItem("Add Move Action", addMoveAction)
    end

    -- 5. Faction specifics.
    if hasUpgrades() then
        self.addContextMenuItem("Choose upgrades", chooseUpgrades)
    end

    -- 6. Special (always last).
    if hasOvalBase() then
        self.addContextMenuItem("Special: Rotate base 90", rotateBase90)
    end
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

-- Parse a base-size stat into (x, z) millimetres. Round bases are a single
-- number (e.g. 32 -> 32,32); oval bases are "AxB" (e.g. "75x42" -> 75,42). The
-- KTUI extender draws base.x and base.z independently, so an oval base ring/mesh
-- falls out for free once the two dimensions are split. Returns nil,nil on junk.
function parseBaseSize(raw)
    if type(raw) == "number" then
        return raw, raw
    end
    if type(raw) == "string" then
        local a, b = string.match(raw, "^%s*(%d+%.?%d*)%s*[xX]%s*(%d+%.?%d*)%s*$")
        if a and b then
            return tonumber(a), tonumber(b)
        end
        local n = tonumber(raw)
        if n then return n, n end
    end
    return nil, nil
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

    local changes = diffAndApply(pendingModel, pendingData, pendingPlayerColor)

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

    local pc = pendingPlayerColor
    pendingData = nil
    pendingModel = nil
    pendingPlayerColor = nil
    selectionData = nil
    -- Advance the "Load everything" chain (no-op unless active).
    if loadEverythingActive then afterStatsLoaded(pc) end
end

function onCancelSelection(player, value, id)
    self.UI.setXml("")
    cancelLoadEverything()
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
        local bx, bz = parseBaseSize(data.stats and data.stats.Base)
        ms.base = { x = bx or 25, z = bz or 25 }
    end
    if ms.modelid == nil or ms.modelid == "" then
        local slug = tostring(data.name or "operative"):lower():gsub("[^%w]+", "-")
        slug = slug:gsub("^%-+", ""):gsub("%-+$", "")
        if slug == "" then slug = "operative" end
        ms.modelid = "ktui-" .. slug
    end
    -- owner intentionally left unset => the model is visible to all players.
end

function diffAndApply(model, data, playerColor)
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

    -- Ownership + discovery for the base table's UI Extender tools. Those tools
    -- (Ready Operatives / Save Positions / Load Positions) only act on objects
    -- tagged 'KTUIMini' whose getOwningPlayer() is non-nil (state.owner == a seated
    -- player's steam_id). Ensure the tag so the tools can find the model.
    if not model.hasTag("KTUIMini") then model.addTag("KTUIMini") end
    -- Owner is only meaningful for the REAL KT UI extender: its table tools gate on
    -- getOwningPlayer(), and only it defines setOwningPlayer. Detect it by checking
    -- the model's OWN script (robust even if a model carried over our mini's tags
    -- before being extended). Our bundled mini is intentionally ownerless (secrets
    -- stay visible to all) and has NO setOwningPlayer, so calling it there throws
    -- "function is not a function". ms.owner must be written too, or the
    -- script_state we save below would wipe the owner the extender just set.
    local isRealExtender = ((model.getLuaScript() or ""):find("function setOwningPlayer", 1, true)) ~= nil
    if isRealExtender and playerColor then
        local pl = Player[playerColor]
        local sid = pl and pl.steam_id or nil
        if sid ~= nil and sid ~= "" then
            ms.owner = sid
            pcall(function() model.call("setOwningPlayer", sid) end)
        end
    end

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
        local bx, bz = parseBaseSize(data.stats.Base)
        if bx then
            local function baseStr(x, z)
                if x == nil then return "-" end
                if valEq(x, z) then return tostring(x) end
                return string.format("%sx%s", tostring(x), tostring(z))
            end
            -- Store the long dimension on Z (front-back). "Rotate base 90" can
            -- later swap x/z to put the long axis left-right instead. Round bases
            -- (bx==bz) are orientation-independent.
            if not valEq(bx, bz) then
                bx, bz = math.min(bx, bz), math.max(bx, bz)
            end
            local oldX = (type(ms.base) == "table") and tonumber(ms.base.x) or nil
            local oldZ = (type(ms.base) == "table") and tonumber(ms.base.z) or nil
            local oldStr, newStr = baseStr(oldX, oldZ), baseStr(bx, bz)
            if oldStr ~= newStr then
                table.insert(changes, string.format("Base: %smm -> %smm", oldStr, newStr))
            end
            ms.base = { x = bx, z = bz }
            ms.stats.Base = data.stats.Base
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
    -- fancy UI intact and just refresh it in place (never overwrite the extender).
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
            -- the existing script/UI is preserved.
            --
            -- First heal the real extender's malformed getWoundPanelWidth (see
            -- healExtenderScript). If we detect it, patch this model's OWN copy of
            -- the script (never the extender object) and reload so the corrected
            -- chunk re-parses; onLoad rebuilds the fancy UI from the script_state we
            -- just wrote. This is what makes repeat loads consistent.
            local healed, didHeal = healExtenderScript(model.getLuaScript() or "")
            if didHeal then
                model.setLuaScript(healed)
                pcall(function() model.reload() end)
                table.insert(changes, "Patched extender UI script")
            else
                -- Redraw the base ring (refreshVectors) AND the status UI
                -- (refreshUI). Each is guarded so one failure can't halt the apply.
                -- Fall back to a full reload() only if the in-place refresh throws;
                -- reload re-runs the extender's onLoad -> loadState, which re-reads
                -- the valid script_state we just wrote (uiHeight etc. guaranteed
                -- present), rebuilding the fancy UI cleanly.
                local ok = pcall(function()
                    model.call("loadState")
                    pcall(function() model.call("refreshVectors") end)
                    model.call("refreshUI")
                end)
                if not ok then
                    pcall(function() model.reload() end)
                end
            end
        end
    end

    return changes
end

-- main entry

function reportChanges(changes, playerColor)
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

function showSelectionPanel(data, model, playerColor)
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
    broadcastToColor("Choose options, then click Apply.", playerColor, Color.Yellow)
end

-- True only when this card's operative has faction-rule upgrade choices in its
-- GMNotes. Operatives without upgrades get no "Choose upgrades" context item.
function hasUpgrades()
    local ok, data = pcall(function() return JSON.decode(self.getGMNotes() or "") end)
    if not ok or type(data) ~= "table" then return false end
    local up = data.upgrades
    return up ~= nil and type(up.options) == "table" and #up.options > 0
end

-- True when this card's operative has the given keyword (e.g. "MOUNTED"),
-- read from GMNotes.keywords. Used to gate the "Add sprint action" item.
function hasKeyword(kw)
    local ok, data = pcall(function() return JSON.decode(self.getGMNotes() or "") end)
    if not ok or type(data) ~= "table" or type(data.keywords) ~= "table" then return false end
    kw = tostring(kw):upper()
    for _, k in ipairs(data.keywords) do
        if tostring(k):upper() == kw then return true end
    end
    return false
end

-- Generic in-place injector/updater for a TAGGED block of Lua on a MODEL.
-- Strips any existing block delimited by `startMarker` .. `endMarker` (any
-- version) and appends the current `code`. When the tag is ABSENT (an older
-- model, or a first install) it simply appends -- so it works as both installer
-- and updater, and still overwrites/extends models that predate the tags. The
-- host script and script_state are left intact. Returns true if a block existed
-- (i.e. this was an update rather than a fresh install).
-- Convention going forward: wrap every injectable function block in the model
-- source with `-- START KT_<NAME> --` / `-- END KT_<NAME> --` so it can be
-- find/replaced in place with an improved version.

-- Heal a known defect in the third-party "KT Command Node UI Extender" script
-- that the extender object stamps onto models. Its getWoundPanelWidth() is
-- written with bare `if` where it needs `elseif`:
--     if wounds <= 7 then  return 60
--     if wounds <= 10 then return 80      -- should be elseif
--     if wounds <= 14 then return 100     -- should be elseif
--     elseif wounds <= 18 then return 120
--     else return 140 end
--     end
-- Those two bare ifs nest instead of chaining, so the function is 2 `end`s short.
-- On its own the missing ends are tolerated at end-of-file, but as soon as we
-- append our movement tool the deficit swallows the start of the appended code
-- and a callee inside refreshUI resolves to nil ("attempt to call a nil value"
-- -- the model loads once, then breaks the next time it is loaded).
--
-- We cannot edit the extender object, but every model carries its OWN copy of the
-- script, so we patch that copy: converting the two bare ifs to `elseif` makes the
-- two existing `end`s correctly close the if-chain and the function. Returns the
-- (possibly healed) code plus a boolean telling whether anything changed.
function healExtenderScript(code)
    if type(code) ~= "string" or code == "" then return code, false end
    if not code:find("getWoundPanelWidth", 1, true) then return code, false end
    local healed, a, b = code, 0, 0
    healed, a = healed:gsub("(return%s+60%s+)if(%s+wounds%s*<=%s*10%s+then)", "%1elseif%2")
    healed, b = healed:gsub("(return%s+80%s+)if(%s+wounds%s*<=%s*14%s+then)", "%1elseif%2")
    return healed, (a + b) > 0
end

function injectBlock(model, startMarker, endMarker, code)
    local lua = model.getLuaScript() or ""
    local existed = false
    -- 1) Remove EVERY current-format block (startMarker..endMarker). Looping so
    --    that several stacked copies (from older always-append builds) all go.
    while true do
        local s = lua:find(startMarker, 1, true)
        if not s then break end
        existed = true
        local e = lua:find(endMarker, s, true)
        if e then
            local nl = lua:find("\n", e, true)
            lua = nl and (lua:sub(1, s - 1) .. lua:sub(nl + 1)) or lua:sub(1, s - 1)
        else
            lua = lua:sub(1, s - 1)
            break
        end
    end
    -- 2) Remove any LEGACY bare-marker block. Older builds appended the tool with
    --    just "-- KT_<NAME>_V1" and no END marker, always at the END of the
    --    script, so strip from the first legacy marker to the end (this clears
    --    however many copies accumulated). Derived from startMarker:
    --    "-- START KT_SPRINT_TOOL_" -> "-- KT_SPRINT_TOOL_V1".
    local legacyMarker = startMarker:gsub("START ", "") .. "V1"
    local ls = lua:find(legacyMarker, 1, true)
    if ls then
        existed = true
        lua = lua:sub(1, ls - 1)
    end
    lua = lua:gsub("%s+$", "")
    -- Heal a malformed foreign extender script (see healExtenderScript) BEFORE
    -- appending so the extender's missing `end`s can't swallow our code.
    lua = healExtenderScript(lua)
    model.setLuaScript(lua .. "\n\n" .. code)
    Wait.frames(function() if model ~= nil then model.reload() end end, 10)
    return existed
end

-- Append the movement tool (SPRINT_TOOL_CODE, embedded on mounted cards) to the
-- model on top, adding "Sprint", "Turn" and "Leap" context items to it.
-- Injection-safe: the tool chains onLoad/onPickUp and never writes script_state.
function addSprintAction(playerColor)
    if type(SPRINT_TOOL_CODE) ~= "string" or SPRINT_TOOL_CODE == "" then
        broadcastToColor("Sprint tool code missing - regenerate the cards.", playerColor, Color.Orange)
        return
    end
    local model = findModelOnCard()
    if not model then
        broadcastToColor("Place the model on this card first.", playerColor, Color.Orange)
        return
    end
    -- Re-running installs the CURRENT version (doubles as an updater).
    local updating = injectBlock(model, "-- START KT_SPRINT_TOOL_", "-- END KT_SPRINT_TOOL_", SPRINT_TOOL_CODE)
    if updating then
        broadcastToColor("Sprint action updated to the latest version.", playerColor, {0.2, 0.85, 0.3})
    else
        broadcastToColor("Sprint action added. Right-click the model -> Sprint / Turn / Leap.", playerColor, {0.2, 0.85, 0.3})
    end
end

-- Append the Move tool (MOVE_TOOL_CODE, embedded on non-mounted cards) to the
-- model on top, adding a "Move" context item to it. Injection-safe: the tool
-- chains onLoad/onPickUp and never writes script_state.
function addMoveAction(playerColor)
    if type(MOVE_TOOL_CODE) ~= "string" or MOVE_TOOL_CODE == "" then
        broadcastToColor("Move tool code missing - regenerate the cards.", playerColor, Color.Orange)
        return
    end
    local model = findModelOnCard()
    if not model then
        broadcastToColor("Place the model on this card first.", playerColor, Color.Orange)
        return
    end
    -- Re-running installs the CURRENT version (doubles as an updater).
    local updating = injectBlock(model, "-- START KT_MOVE_TOOL_", "-- END KT_MOVE_TOOL_", MOVE_TOOL_CODE)
    if updating then
        broadcastToColor("Move action updated to the latest version.", playerColor, {0.2, 0.85, 0.3})
    else
        broadcastToColor("Move action added. Right-click the model -> Move.", playerColor, {0.2, 0.85, 0.3})
    end
end

-- True only when this card's operative uses an oval base (two different base
-- dimensions). Round-base operatives get no "Rotate base 90" context item.
function hasOvalBase()
    local ok, data = pcall(function() return JSON.decode(self.getGMNotes() or "") end)
    if not ok or type(data) ~= "table" then return false end
    local bx, bz = parseBaseSize(data.stats and data.stats.Base)
    return bx ~= nil and bz ~= nil and not valEq(bx, bz)
end

-- Rotate the oval base 90 degrees (KT UI compatible). The KT UI extender stores
-- base = { x, z } (axis-aligned, no rotation field), so swapping x<->z is the only
-- orientation it can render. We patch the model's OWN state and reload its OWN
-- script -- never setLuaScript -- so the KT UI extender is preserved.
function rotateBase90(playerColor)
    local model = findModelOnCard()
    if not model then
        broadcastToColor("Place the model on this card first.", playerColor, Color.Orange)
        return
    end
    local okd, ms = pcall(function() return JSON.decode(model.script_state or "") end)
    if not okd or type(ms) ~= "table" then
        broadcastToColor("Load stats to this model first.", playerColor, Color.Orange)
        return
    end
    local bx = ms.base and tonumber(ms.base.x)
    local bz = ms.base and tonumber(ms.base.z)
    if not (bx and bz) then
        local ok2, data = pcall(function() return JSON.decode(self.getGMNotes() or "") end)
        if ok2 and data then bx, bz = parseBaseSize(data.stats and data.stats.Base) end
    end
    if not (bx and bz) or valEq(bx, bz) then
        broadcastToColor("This operative has a round base -- nothing to rotate.", playerColor, Color.Orange)
        return
    end
    ms.base = { x = bz, z = bx }   -- swap = rotate the oval 90 degrees
    model.script_state = JSON.encode(ms)
    model.reload()
    broadcastToColor(string.format("Base rotated 90 (now %sx%s).", tostring(bz), tostring(bx)), playerColor, Color.Green)
end

function proceedLoad(playerColor, data, model, ignoreWeapons)
    if (not ignoreWeapons) and data.selection and data.selection.groups and #data.selection.groups > 0 then
        showSelectionPanel(data, model, playerColor)
    else
        local changes = diffAndApply(model, data, playerColor)
        reportChanges(changes, playerColor)
        pendingData = nil
        pendingModel = nil
        pendingPlayerColor = nil
        -- No loadout popup: the stats step finished synchronously, so advance the
        -- "Load everything" chain now (no-op unless it is active).
        if loadEverythingActive then afterStatsLoaded(playerColor) end
    end
end

-- ===== "Load everything" orchestrator =====
-- One click runs the full setup IN ORDER: load stats (forcing the loadout popup
-- when the operative has one) -> apply faction upgrades if any -> faction-rule
-- popup if any (chapter tactics / gore tanks) -> operative counters if any ->
-- movement. The stats, upgrade and faction-rule steps use ASYNC selection
-- popups, so the chain is advanced from their Apply handlers, guarded by this
-- flag; the counters + movement steps are synchronous. Any Cancel aborts the
-- chain. The individual menu items still work standalone. (Rotate base excluded.)
--
-- Each stats/counters/movement step rewrites the model's Lua and reload()s it
-- (~10 frames later). Reloads that stack in the same frame make TTS leave TWO
-- overlapping copies of the model, so between every mutate+reload step we WAIT a
-- short window for the previous reload to settle. Each step re-acquires the
-- model via findModelOnCard(), so it always works on the freshly reloaded object.
loadEverythingActive = false
local LOAD_EVERYTHING_STEP_FRAMES = 25   -- window between mutate+reload steps

-- Run nextFn(playerColor) after a short settle window, if the chain is still active.
function loadEverythingWait(nextFn, playerColor)
    if not loadEverythingActive then return end
    Wait.frames(function()
        if loadEverythingActive then nextFn(playerColor) end
    end, LOAD_EVERYTHING_STEP_FRAMES)
end

function loadEverything(playerColor)
    loadEverythingActive = true
    loadStatsToModel(playerColor)          -- continues via afterStatsLoaded(...)
end

-- After the STATS step (called from onApplySelection and the sync path above).
function afterStatsLoaded(playerColor)
    if not loadEverythingActive then return end
    if hasUpgrades() then
        chooseUpgrades(playerColor)        -- async -> continues via afterUpgradesLoaded
    else
        -- Stats just reloaded the model; settle before the next step.
        loadEverythingWait(afterFactionRuleStep, playerColor)
    end
end

-- After the UPGRADES step (Exodite <archetype> UPGRADE picks). Continue to the
-- faction-rule popup step.
function afterUpgradesLoaded(playerColor)
    if not loadEverythingActive then return end
    -- Upgrades just refreshed/reloaded the model; settle before the next step.
    loadEverythingWait(afterFactionRuleStep, playerColor)
end

-- Faction-rule popup step (e.g. AoD "Chapter Tactics", Goremongers "Gore Tanks"),
-- generated as applyFactionRule() on teams that use the select-1/2 popup. It is
-- an ASYNC popup: its Apply handler resumes via afterFactionRuleLoaded and its
-- Cancel aborts the chain. Cards without a popup skip straight ahead.
function afterFactionRuleStep(playerColor)
    if not loadEverythingActive then return end
    if type(applyFactionRule) == "function" then
        applyFactionRule(playerColor)      -- async -> continues via afterFactionRuleLoaded
    else
        afterFactionRuleLoaded(playerColor)
    end
end

-- After the FACTION-RULE popup (or when there is none). Continue to counters.
function afterFactionRuleLoaded(playerColor)
    if not loadEverythingActive then return end
    loadEverythingWait(afterCountersStep, playerColor)
end

-- Operative counters are injected by an APPENDED feature block. A card may have
-- the MULTI counter menu (addOperativeCountersToModel, e.g. Exodite) OR the
-- SINGLE counter (addOperativeCounterToModel, e.g. Goremongers "Gore Tank") --
-- run whichever exists. Both are synchronous (model rewrite + reload), so settle
-- before movement; when neither exists, go straight to movement.
function afterCountersStep(playerColor)
    if not loadEverythingActive then return end
    local didCounter = false
    if type(addOperativeCountersToModel) == "function" then
        addOperativeCountersToModel(playerColor)
        didCounter = true
    end
    if type(addOperativeCounterToModel) == "function" then
        addOperativeCounterToModel(playerColor)
        didCounter = true
    end
    if didCounter then
        loadEverythingWait(afterCountersLoaded, playerColor)
    else
        afterCountersLoaded(playerColor)
    end
end

-- After the COUNTERS step. Adds the movement action (the final step) and ends.
function afterCountersLoaded(playerColor)
    if not loadEverythingActive then return end
    loadEverythingActive = false
    if type(SPRINT_TOOL_CODE) == "string" and hasKeyword("MOUNTED") then
        addSprintAction(playerColor)
    elseif type(MOVE_TOOL_CODE) == "string" then
        addMoveAction(playerColor)
    end
end

-- Abort the chain (called from the Cancel handlers of either popup).
function cancelLoadEverything()
    loadEverythingActive = false
end

-- ===== Faction-rule upgrades (mounted operatives pick N of M) =====

function chooseUpgrades(playerColor)
    local raw = self.getGMNotes()
    local ok, data = pcall(function() return JSON.decode(raw or "") end)
    if not ok or not data then
        broadcastToColor("No stat data on this card.", playerColor, Color.Red)
        return
    end
    local up = data.upgrades
    if not up or not up.options or #up.options == 0 then
        broadcastToColor("This datacard has no upgrade choices.", playerColor, Color.Orange)
        return
    end
    local model = findModelOnCard()
    if not model then
        broadcastToColor("Place the model on this card first.", playerColor, Color.Orange)
        return
    end
    upgradeOptions = up.options
    upgradeSelect = tonumber(up.select) or 2
    upgradeChosen = {}
    upgradeModel = model
    upgradeData = data
    upgradePlayerColor = playerColor
    self.UI.setXml(buildUpgradePanelXml(up.options, upgradeSelect))
    broadcastToColor(string.format("Select %d upgrades, then click Apply.", upgradeSelect), playerColor, Color.Yellow)
end

function buildUpgradePanelXml(options, selectN)
    local rows = ""
    for i, opt in ipairs(options) do
        local label = opt.name or ("Upgrade " .. i)
        label = label:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;")
        rows = rows .. string.format(
            '<Toggle id="upg_%d" isOn="false" onValueChanged="onUpgradeToggle" '
            .. 'fontSize="11" textColor="#FFFFFF" colors="#444444|#666666|#333333|#222222" '
            .. 'toggleWidth="18" toggleHeight="18">%s</Toggle>\n', i, label)
    end
    local h = 74 + #options * 26
    return string.format([[
<Panel id="upgradePanel" active="true" width="264" height="%d"
       color="rgba(0,0,0,0.92)" padding="6 6 6 6" position="0 0 -50"
       rotation="0 0 180" allowDragging="true">
  <VerticalLayout spacing="3" childForceExpandWidth="true" childForceExpandHeight="false">
    <Text fontSize="12" fontStyle="Bold" color="#FF9900" alignment="MiddleCenter" preferredHeight="20">Choose %d Upgrades</Text>
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    %s
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    <HorizontalLayout spacing="4" preferredHeight="24">
      <Button id="btnUpgApply" onClick="onApplyUpgrades" fontSize="10" fontStyle="Bold" colors="#2E7D32|#388E3C|#1B5E20|#555555" textColor="#FFFFFF">Apply</Button>
      <Button id="btnUpgCancel" onClick="onCancelUpgrades" fontSize="10" colors="#C62828|#D32F2F|#B71C1C|#555555" textColor="#FFFFFF">Cancel</Button>
    </HorizontalLayout>
  </VerticalLayout>
</Panel>
]], h, selectN, rows)
end

function _upgradeCount()
    local n = 0
    for _ in pairs(upgradeChosen) do n = n + 1 end
    return n
end

function onUpgradeToggle(player, value, id)
    local i = tonumber(id:match("upg_(%d+)"))
    if not i then return end
    if value == "True" then
        if _upgradeCount() >= upgradeSelect then
            -- Enforce the limit: bounce this toggle back off.
            self.UI.setAttribute(id, "isOn", "false")
            broadcastToColor(string.format("Pick exactly %d -- deselect one first.", upgradeSelect), upgradePlayerColor, Color.Orange)
            return
        end
        upgradeChosen[i] = true
    else
        upgradeChosen[i] = nil
    end
end

function onApplyUpgrades(player, value, id)
    if _upgradeCount() ~= upgradeSelect then
        broadcastToColor(string.format("Select exactly %d upgrades.", upgradeSelect), upgradePlayerColor, Color.Orange)
        return
    end
    self.UI.setXml("")
    if not upgradeData or not upgradeModel or not upgradeOptions then return end
    local data = upgradeData
    data.abilities = data.abilities or {}
    local chosenNames = {}
    for i in pairs(upgradeChosen) do
        local opt = upgradeOptions[i]
        if opt then
            table.insert(data.abilities, { name = opt.name, text = opt.text })
            table.insert(chosenNames, opt.name)
        end
    end
    local changes = diffAndApply(upgradeModel, data, upgradePlayerColor)
    broadcastToColor("Upgrades applied: " .. table.concat(chosenNames, ", "), upgradePlayerColor, Color.Green)
    local pc = upgradePlayerColor
    upgradeChosen = {}
    upgradeModel = nil
    upgradeData = nil
    upgradeOptions = nil
    -- Advance the "Load everything" chain to the movement step (no-op unless active).
    if loadEverythingActive then afterUpgradesLoaded(pc) end
end

function onCancelUpgrades(player, value, id)
    self.UI.setXml("")
    cancelLoadEverything()
    broadcastToColor("Upgrade selection cancelled.", upgradePlayerColor or (player and player.color) or "White", Color.White)
    upgradeChosen = {}
    upgradeModel = nil
    upgradeData = nil
    upgradeOptions = nil
end

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

    -- Base (incl. oval) applies in its default orientation; use "Rotate base 90"
    -- afterwards if a mesh needs the oval turned.
    local modelAll = findModelOnCard()
    if modelAll == nil then
        broadcastToColor("Place a model on this card first.", playerColor, Color.Orange)
        return
    end
    proceedLoad(playerColor, data, modelAll, true)
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

    -- Base (incl. oval) applies in its default orientation; use "Rotate base 90"
    -- afterwards if a mesh needs the oval turned.
    local model = findModelOnCard()
    if model == nil then
        broadcastToColor("Place a model on this card first.", playerColor, Color.Orange)
        return
    end
    proceedLoad(playerColor, data, model, false)
end
