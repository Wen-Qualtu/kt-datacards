-- ===== FACTION RULE: {{FACTION_RULE_NAME}} =====

FACTION_RULE_NAME = "{{FACTION_RULE_NAME}}"
FACTION_RULE_OPTIONS = {
{{FACTION_RULE_OPTIONS}}
}

local frPendingModel = nil
local frPendingPlayerColor = nil
local frPrimarySelection = 1
local frSecondarySelection = 2

function buildFactionRulePanel()
    local rows = ""

    -- Primary selection
    rows = rows .. '<Text fontSize="11" fontStyle="Bold" color="#FF6600" '
        .. 'preferredHeight="20" alignment="MiddleLeft">Primary:</Text>\n'
    for i, opt in ipairs(FACTION_RULE_OPTIONS) do
        local isOn = (i == frPrimarySelection) and "true" or "false"
        local label = opt.name:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
        rows = rows .. string.format(
            '<Toggle id="fr_p_%d" isOn="%s" '
            .. 'onValueChanged="onFrPrimaryToggle" '
            .. 'fontSize="10" textColor="#FFFFFF" colors="#444444|#666666|#333333|#222222" '
            .. 'toggleWidth="16" toggleHeight="16">%s</Toggle>\n',
            i, isOn, label
        )
    end

    -- Separator
    rows = rows .. '<Image color="rgba(255,255,255,0.3)" preferredHeight="1" />\n'

    -- Secondary selection
    rows = rows .. '<Text fontSize="11" fontStyle="Bold" color="#FF6600" '
        .. 'preferredHeight="20" alignment="MiddleLeft">Secondary:</Text>\n'
    for i, opt in ipairs(FACTION_RULE_OPTIONS) do
        local isOn = (i == frSecondarySelection) and "true" or "false"
        local label = opt.name:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
        rows = rows .. string.format(
            '<Toggle id="fr_s_%d" isOn="%s" '
            .. 'onValueChanged="onFrSecondaryToggle" '
            .. 'fontSize="10" textColor="#FFFFFF" colors="#444444|#666666|#333333|#222222" '
            .. 'toggleWidth="16" toggleHeight="16">%s</Toggle>\n',
            i, isOn, label
        )
    end

    return '<Panel preferredWidth="800" preferredHeight="600" padding="12 12 12 12" spacing="4" '
        .. 'color="rgba(0,0,0,0.85)" childForceExpandWidth="true">\n'
        .. '<VerticalLayout spacing="4" childForceExpandWidth="true">\n'
        .. rows
        .. '</VerticalLayout>\n</Panel>\n'
end

function onFrPrimaryToggle(player, value, id)
    if value == "False" then return end
    local idx = tonumber(id:match("fr_p_(%d+)"))
    if not idx then return end
    frPrimarySelection = idx
    Global.UI.setAttribute("fr_info_panel", "active", "false")
    updateUI()
end

function onFrSecondaryToggle(player, value, id)
    if value == "False" then return end
    local idx = tonumber(id:match("fr_s_(%d+)"))
    if not idx then return end
    frSecondarySelection = idx
    Global.UI.setAttribute("fr_info_panel", "active", "false")
    updateUI()
end

function onLoadToModelClick(player)
    local model = findModelOnCard()
    if not model then
        broadcastToColor("No model found on this card.", player.color, {1, 0.5, 0})
        return
    end
    frPendingModel = model
    frPendingPlayerColor = player.color
    local xml = buildFactionRulePanel()
    Global.UI.setXml(xml)
    Wait.frames(function()
        Global.UI.show("fr_info_panel")
    end, 2)
end

function onFrConfirm(player)
    if not frPendingModel or not frPendingModel.getData() then
        broadcastToColor("Model not found or was deleted.", player.color, {1, 0.5, 0})
        Global.UI.hide("fr_info_panel")
        frPendingModel = nil
        frPendingPlayerColor = nil
        return
    end

    local primary = FACTION_RULE_OPTIONS[frPrimarySelection]
    local secondary = FACTION_RULE_OPTIONS[frSecondarySelection]
    
    if not primary or not secondary then
        broadcastToColor("Invalid selection.", player.color, {1, 0.5, 0})
        Global.UI.hide("fr_info_panel")
        return
    end

    local data = frPendingModel.getData()
    local script = data.LuaScript or ""
    
    -- Update faction rule state
    script = script:gsub("frPrimarySelection = %d+", "frPrimarySelection = " .. frPrimarySelection)
    script = script:gsub("frSecondarySelection = %d+", "frSecondarySelection = " .. frSecondarySelection)
    
    frPendingModel.setLuaScript(script)
    
    broadcastToColor(string.format("Applied: Primary=%s, Secondary=%s", primary.name, secondary.name), player.color, {0, 1, 0})
    Global.UI.hide("fr_info_panel")
    frPendingModel = nil
    frPendingPlayerColor = nil
end

function onFrCancel()
    Global.UI.hide("fr_info_panel")
    frPendingModel = nil
    frPendingPlayerColor = nil
end
