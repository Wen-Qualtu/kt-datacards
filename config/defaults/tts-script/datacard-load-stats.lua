-- kt-datacards: Load Stats to Model
-- Card stores operative data in GMNotes (JSON).
-- Context menu "Load stats to model" finds a KTUIMini on top,
-- compares current vs new, reports diffs, and applies changes.

function onLoad()
    self.addContextMenuItem("Load stats to model", loadStatsToModel)
end

-- helpers

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
        if obj and obj ~= self and obj.type == "Custom_Model" then return obj end
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

-- diff and apply

function diffAndApply(model, data)
    local changes = {}

    local msRaw = model.script_state
    local ms = {}
    if msRaw and msRaw ~= "" then
        local ok, parsed = pcall(function() return JSON.decode(msRaw) end)
        if ok and parsed then ms = parsed end
    end

    ms.stats = ms.stats or {}
    ms.info  = ms.info or {}

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

    -- Reset wounds to full when max wounds changes (up or down)
    if data.stats.Wounds then
        if ms.wounds == nil or (oldMaxWounds and not valEq(oldMaxWounds, data.stats.Wounds)) then
            ms.wounds = data.stats.Wounds
        end
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

    -- 4. Weapons
    if data.weapons then
        local oldW = ms.info.weapons or {}
        if not tableEq(oldW, data.weapons) then
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
        end

        if data.weapon_rules and not tableEq(ms.info.rules, data.weapon_rules) then
            table.insert(changes, "Weapon rules updated")
            ms.info.rules = data.weapon_rules
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
    if #changes > 0 then
        model.script_state = JSON.encode(ms)
        Wait.frames(function() model.reload() end, 5)
    end

    return changes
end

-- main entry

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
        broadcastToColor("Place a KTUIMini model on this card first.", playerColor, Color.Orange)
        return
    end

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
