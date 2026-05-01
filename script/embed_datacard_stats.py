"""
Embed operative stats (GMNotes + Lua) into existing TTS datacard objects.

For each team:
  1. Reads roster.json (produced by extract_statlines.py) as sole data source
  2. Patches every datacard in tts_objects/{team}/*.json with GMNotes + LuaScript

Usage:
    python script/embed_datacard_stats.py [--teams team1,team2] [--dry-run]
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LUA_SCRIPT_PATH = ROOT / "config" / "defaults" / "tts-script" / "datacard-load-stats.lua"
WEAPON_RULES_PATH = ROOT / "config" / "weapon_rules.json"
OUTPUT_DIR = ROOT / "output"
TTS_DIR = ROOT / "tts_objects"
TEAM_CONFIG_PATH = ROOT / "config" / "team-config.yaml"

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ── Team config helpers ──

def _load_team_config() -> dict:
    """Load team-config.yaml"""
    with open(TEAM_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_team_faction(team: str) -> str:
    """Get faction for a team from team-config.yaml"""
    config = _load_team_config()
    team_data = config.get("teams", {}).get(team, {})
    return team_data.get("faction", "xenos")  # default to xenos if not found


def _has_operative_counter(team: str) -> bool:
    """Check if team has operative_counter configured"""
    config = _load_team_config()
    team_data = config.get("teams", {}).get(team, {})
    return "operative_counter" in team_data


def _update_bag_timestamp(tts_data: dict) -> None:
    """Update lastCardUpdate in the top-level bag's LuaScriptState to current time."""
    from datetime import datetime
    obj = tts_data.get("ObjectStates", [{}])[0]
    lss = obj.get("LuaScriptState", "")
    try:
        state = json.loads(lss) if lss else {}
    except (json.JSONDecodeError, TypeError):
        state = {}
    state["lastCardUpdate"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    obj["LuaScriptState"] = json.dumps(state)


def _has_faction_rule(team: str) -> bool:
    """Check if team has faction_rule configured"""
    config = _load_team_config()
    team_data = config.get("teams", {}).get(team, {})
    return "faction_rule" in team_data


def _get_faction_rule(team: str) -> dict | None:
    """Get faction_rule config for a team"""
    config = _load_team_config()
    team_data = config.get("teams", {}).get(team, {})
    return team_data.get("faction_rule")


def _inject_faction_rule(lua_script: str, team: str, roster: dict | None = None) -> str:
    """
    Inject faction rule selection into datacard Lua script.
    Supports two modes based on 'select' value:
    - select: 2 → Primary + Secondary selection (e.g. Angels of Death Chapter Tactics)
    - select: 1 → Single choice selection (e.g. Legionaries Marks of Chaos)

    Reads option text from roster.json's faction_rule field (extracted from PDF).
    Falls back to team-config.yaml if roster data is unavailable.
    """
    if not _has_faction_rule(team):
        return lua_script

    # Check if already injected
    if "FACTION_RULE_OPTIONS" in lua_script:
        return lua_script

    # Prefer roster data (extracted from PDF) over YAML config
    roster_rule = roster.get("faction_rule") if roster else None
    yaml_rule = _get_faction_rule(team)

    if roster_rule:
        rule = roster_rule
    elif yaml_rule:
        rule = yaml_rule
    else:
        return lua_script

    log.info(f"{team}: Injecting faction rule '{rule['name']}' into datacard script")

    rule_name = rule["name"]
    options = rule.get("options", [])

    # Build Lua table literal for options
    lua_options = "{\n"
    for opt in options:
        name_escaped = opt["name"].replace('"', '\\"')
        text_escaped = opt.get("text", "").replace('"', '\\"').replace("'", "\\'")
        lua_options += f'    {{name = "{name_escaped}", text = "{text_escaped}"}},\n'
    lua_options += "}"

    select_count = rule.get("select", 2)

    if select_count == 1:
        helper_functions = _build_select1_lua(rule_name, lua_options)
    else:
        helper_functions = _build_select2_lua(rule_name, lua_options)

    lua_script = lua_script.rstrip() + helper_functions

    return lua_script


def _build_select1_lua(rule_name: str, lua_options: str) -> str:
    """Generate Lua for single-choice faction rule (select: 1)."""
    return f'''

-- ===== FACTION RULE: {rule_name.upper()} =====

FACTION_RULE_NAME = "{rule_name}"
FACTION_RULE_OPTIONS = {lua_options}

local frPendingModel = nil
local frPendingPlayerColor = nil
local frSelection = 1

function buildFactionRulePanel()
    local rows = ""

    for i, opt in ipairs(FACTION_RULE_OPTIONS) do
        local isOn = (i == frSelection) and "true" or "false"
        local label = opt.name:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
        rows = rows .. string.format(
            '<Toggle id="fr_%d" isOn="%s" '
            .. 'onValueChanged="onFrToggle" '
            .. 'fontSize="10" textColor="#FFFFFF" colors="#444444|#666666|#333333|#222222" '
            .. 'toggleWidth="16" toggleHeight="16">%s</Toggle>\\n',
            i, isOn, label
        )
    end

    local optionCount = #FACTION_RULE_OPTIONS
    local panelHeight = 70 + optionCount * 22

    return string.format([[
<Panel id="frPanel" active="true"
       width="240" height="%d"
       color="rgba(0,0,0,0.92)"
       padding="6 6 6 6"
       position="0 0 -50"
       rotation="0 0 180"
       allowDragging="true">
  <VerticalLayout spacing="2" childForceExpandWidth="true" childForceExpandHeight="false">
    <Text fontSize="12" fontStyle="Bold" color="#FF9900"
          alignment="MiddleCenter" preferredHeight="22">]] .. FACTION_RULE_NAME .. [[</Text>
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    %s
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    <HorizontalLayout spacing="4" preferredHeight="24">
      <Button id="frApply" onClick="onFrApply"
              fontSize="10" fontStyle="Bold"
              colors="#2E7D32|#388E3C|#1B5E20|#555555"
              textColor="#FFFFFF">Apply</Button>
      <Button id="frCancel" onClick="onFrCancel"
              fontSize="10"
              colors="#C62828|#D32F2F|#B71C1C|#555555"
              textColor="#FFFFFF">Cancel</Button>
    </HorizontalLayout>
  </VerticalLayout>
</Panel>
]], panelHeight, rows)
end

function onFrToggle(player, value, id)
    local idx = tonumber(id:match("fr_(%d+)"))
    if not idx then return end
    if value == "True" then
        frSelection = idx
        for i = 1, #FACTION_RULE_OPTIONS do
            if i ~= idx then
                self.UI.setAttribute("fr_" .. i, "isOn", "false")
            end
        end
    else
        if frSelection == idx then
            self.UI.setAttribute(id, "isOn", "true")
        end
    end
end

function onFrApply(player, value, id)
    self.UI.setXml("")

    if not frPendingModel then
        broadcastToColor("No model pending.", frPendingPlayerColor or player.color, Color.Red)
        return
    end

    local model = frPendingModel
    local pc = frPendingPlayerColor or player.color

    -- Read model state
    local msRaw = model.script_state or "{{}}"
    local ok, ms = pcall(function() return JSON.decode(msRaw) end)
    if not ok or not ms then ms = {{}} end
    ms.info = ms.info or {{}}
    ms.info.abilities = ms.info.abilities or {{}}

    -- Remove any existing faction rule abilities
    local kept = {{}}
    for _, ab in ipairs(ms.info.abilities) do
        local isFactionRule = false
        for _, opt in ipairs(FACTION_RULE_OPTIONS) do
            if ab.name == opt.name then
                isFactionRule = true
                break
            end
        end
        if not isFactionRule then
            table.insert(kept, ab)
        end
    end

    -- Add selected mark as ability
    local selected = FACTION_RULE_OPTIONS[frSelection]
    table.insert(kept, {{name = selected.name, text = selected.text}})

    ms.info.abilities = kept

    -- Update description
    local descLines = {{}}
    local oldDesc = model.getDescription() or ""
    local inFactionSection = false
    for line in oldDesc:gmatch("([^\\n]*)\\n?") do
        if line:find("^%[31B32B%]" .. FACTION_RULE_NAME) then
            inFactionSection = true
        elseif inFactionSection and (line:find("^%[31B32B%]") or line:find("^%-%-%-")) then
            inFactionSection = false
            table.insert(descLines, line)
        elseif not inFactionSection then
            table.insert(descLines, line)
        end
    end

    table.insert(descLines, "---")
    table.insert(descLines, "[31B32B]" .. FACTION_RULE_NAME .. "[-]")
    table.insert(descLines, "- [EF8450]" .. selected.name .. "[-]")

    model.setDescription(table.concat(descLines, "\\n"))
    model.script_state = JSON.encode(ms)
    Wait.frames(function() model.reload() end, 5)

    broadcastToColor(string.format("%s applied: %s",
        FACTION_RULE_NAME, selected.name), pc, Color.Green)

    frPendingModel = nil
    frPendingPlayerColor = nil
end

function onFrCancel(player, value, id)
    self.UI.setXml("")
    broadcastToColor(FACTION_RULE_NAME .. " selection cancelled.", frPendingPlayerColor or player.color, Color.White)
    frPendingModel = nil
    frPendingPlayerColor = nil
end

function applyFactionRule(playerColor)
    local model = findModelOnCard()
    if model == nil then
        broadcastToColor("Place a KTUIMini model on this card first.", playerColor, Color.Orange)
        return
    end

    frPendingModel = model
    frPendingPlayerColor = playerColor
    frSelection = 1
    self.UI.setXml(buildFactionRulePanel())
    broadcastToColor("Select " .. FACTION_RULE_NAME .. ", then click Apply.", playerColor, Color.Yellow)
end

-- Extend onLoad for faction rule
local frBaseOnLoad = onLoad
function onLoad()
    if frBaseOnLoad then frBaseOnLoad() end
    self.addContextMenuItem("{rule_name}", applyFactionRule)
end

-- ===== END FACTION RULE =====
'''


def _build_select2_lua(rule_name: str, lua_options: str) -> str:
    """Generate Lua for dual-choice faction rule (select: 2, primary + secondary)."""
    return f'''

-- ===== FACTION RULE: {rule_name.upper()} =====

FACTION_RULE_NAME = "{rule_name}"
FACTION_RULE_OPTIONS = {lua_options}

local frPendingModel = nil
local frPendingPlayerColor = nil
local frPrimarySelection = 1
local frSecondarySelection = 2

function buildFactionRulePanel()
    local rows = ""

    -- Primary selection
    rows = rows .. '<Text fontSize="11" fontStyle="Bold" color="#FF6600" '
        .. 'preferredHeight="20" alignment="MiddleLeft">Primary:</Text>\\n'
    for i, opt in ipairs(FACTION_RULE_OPTIONS) do
        local isOn = (i == frPrimarySelection) and "true" or "false"
        local label = opt.name:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
        rows = rows .. string.format(
            '<Toggle id="fr_p_%d" isOn="%s" '
            .. 'onValueChanged="onFrPrimaryToggle" '
            .. 'fontSize="10" textColor="#FFFFFF" colors="#444444|#666666|#333333|#222222" '
            .. 'toggleWidth="16" toggleHeight="16">%s</Toggle>\\n',
            i, isOn, label
        )
    end

    -- Separator
    rows = rows .. '<Image color="rgba(255,255,255,0.3)" preferredHeight="1" />\\n'

    -- Secondary selection
    rows = rows .. '<Text fontSize="11" fontStyle="Bold" color="#FF6600" '
        .. 'preferredHeight="20" alignment="MiddleLeft">Secondary:</Text>\\n'
    for i, opt in ipairs(FACTION_RULE_OPTIONS) do
        local isOn = (i == frSecondarySelection) and "true" or "false"
        local label = opt.name:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
        rows = rows .. string.format(
            '<Toggle id="fr_s_%d" isOn="%s" '
            .. 'onValueChanged="onFrSecondaryToggle" '
            .. 'fontSize="10" textColor="#FFFFFF" colors="#444444|#666666|#333333|#222222" '
            .. 'toggleWidth="16" toggleHeight="16">%s</Toggle>\\n',
            i, isOn, label
        )
    end

    local optionCount = #FACTION_RULE_OPTIONS
    local panelHeight = 80 + optionCount * 22 * 2 + 40

    return string.format([[
<Panel id="frPanel" active="true"
       width="240" height="%d"
       color="rgba(0,0,0,0.92)"
       padding="6 6 6 6"
       position="0 0 -50"
       rotation="0 0 180"
       allowDragging="true">
  <VerticalLayout spacing="2" childForceExpandWidth="true" childForceExpandHeight="false">
    <Text fontSize="12" fontStyle="Bold" color="#FF9900"
          alignment="MiddleCenter" preferredHeight="22">]] .. FACTION_RULE_NAME .. [[</Text>
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    %s
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    <HorizontalLayout spacing="4" preferredHeight="24">
      <Button id="frApply" onClick="onFrApply"
              fontSize="10" fontStyle="Bold"
              colors="#2E7D32|#388E3C|#1B5E20|#555555"
              textColor="#FFFFFF">Apply</Button>
      <Button id="frCancel" onClick="onFrCancel"
              fontSize="10"
              colors="#C62828|#D32F2F|#B71C1C|#555555"
              textColor="#FFFFFF">Cancel</Button>
    </HorizontalLayout>
  </VerticalLayout>
</Panel>
]], panelHeight, rows)
end

function onFrPrimaryToggle(player, value, id)
    local idx = tonumber(id:match("fr_p_(%d+)"))
    if not idx then return end
    if value == "True" then
        frPrimarySelection = idx
        for i = 1, #FACTION_RULE_OPTIONS do
            if i ~= idx then
                self.UI.setAttribute("fr_p_" .. i, "isOn", "false")
            end
        end
    else
        if frPrimarySelection == idx then
            self.UI.setAttribute(id, "isOn", "true")
        end
    end
end

function onFrSecondaryToggle(player, value, id)
    local idx = tonumber(id:match("fr_s_(%d+)"))
    if not idx then return end
    if value == "True" then
        frSecondarySelection = idx
        for i = 1, #FACTION_RULE_OPTIONS do
            if i ~= idx then
                self.UI.setAttribute("fr_s_" .. i, "isOn", "false")
            end
        end
    else
        if frSecondarySelection == idx then
            self.UI.setAttribute(id, "isOn", "true")
        end
    end
end

function onFrApply(player, value, id)
    self.UI.setXml("")

    if not frPendingModel then
        broadcastToColor("No model pending.", frPendingPlayerColor or player.color, Color.Red)
        return
    end

    if frPrimarySelection == frSecondarySelection then
        broadcastToColor("Primary and secondary must be different.", frPendingPlayerColor or player.color, Color.Orange)
        -- Re-show panel
        self.UI.setXml(buildFactionRulePanel())
        return
    end

    local model = frPendingModel
    local pc = frPendingPlayerColor or player.color

    -- Read model state
    local msRaw = model.script_state or "{{}}"
    local ok, ms = pcall(function() return JSON.decode(msRaw) end)
    if not ok or not ms then ms = {{}} end
    ms.info = ms.info or {{}}
    ms.info.abilities = ms.info.abilities or {{}}

    -- Remove any existing faction rule abilities
    local kept = {{}}
    for _, ab in ipairs(ms.info.abilities) do
        local isFactionRule = false
        for _, opt in ipairs(FACTION_RULE_OPTIONS) do
            if ab.name == opt.name or ab.name == opt.name .. " (Primary)" or ab.name == opt.name .. " (Secondary)" then
                isFactionRule = true
                break
            end
        end
        if not isFactionRule then
            table.insert(kept, ab)
        end
    end

    -- Add selected tactics as abilities
    local primary = FACTION_RULE_OPTIONS[frPrimarySelection]
    local secondary = FACTION_RULE_OPTIONS[frSecondarySelection]

    table.insert(kept, {{name = primary.name .. " (Primary)", text = primary.text}})
    table.insert(kept, {{name = secondary.name .. " (Secondary)", text = secondary.text}})

    ms.info.abilities = kept

    -- Update description to reflect new abilities
    local descLines = {{}}
    local oldDesc = model.getDescription() or ""
    local inFactionSection = false
    for line in oldDesc:gmatch("([^\\n]*)\\n?") do
        if line:find("^%[31B32B%]" .. FACTION_RULE_NAME) then
            inFactionSection = true
        elseif inFactionSection and (line:find("^%[31B32B%]") or line:find("^%-%-%-")) then
            inFactionSection = false
            table.insert(descLines, line)
        elseif not inFactionSection then
            table.insert(descLines, line)
        end
    end

    -- Append faction rule section before the closing
    table.insert(descLines, "---")
    table.insert(descLines, "[31B32B]" .. FACTION_RULE_NAME .. "[-]")
    table.insert(descLines, "- [EF8450]" .. primary.name .. " (Primary)[-]")
    table.insert(descLines, "- [EF8450]" .. secondary.name .. " (Secondary)[-]")

    model.setDescription(table.concat(descLines, "\\n"))
    model.script_state = JSON.encode(ms)
    Wait.frames(function() model.reload() end, 5)

    broadcastToColor(string.format("%s applied: %s (Primary) + %s (Secondary)",
        FACTION_RULE_NAME, primary.name, secondary.name), pc, Color.Green)

    frPendingModel = nil
    frPendingPlayerColor = nil
end

function onFrCancel(player, value, id)
    self.UI.setXml("")
    broadcastToColor(FACTION_RULE_NAME .. " selection cancelled.", frPendingPlayerColor or player.color, Color.White)
    frPendingModel = nil
    frPendingPlayerColor = nil
end

function applyFactionRule(playerColor)
    local model = findModelOnCard()
    if model == nil then
        broadcastToColor("Place a KTUIMini model on this card first.", playerColor, Color.Orange)
        return
    end

    frPendingModel = model
    frPendingPlayerColor = playerColor
    frPrimarySelection = 1
    frSecondarySelection = 2
    self.UI.setXml(buildFactionRulePanel())
    broadcastToColor("Select primary and secondary " .. FACTION_RULE_NAME .. ", then click Apply.", playerColor, Color.Yellow)
end

-- Extend onLoad for faction rule
local frBaseOnLoad = onLoad
function onLoad()
    if frBaseOnLoad then frBaseOnLoad() end
    self.addContextMenuItem("{rule_name}", applyFactionRule)
end

-- ===== END FACTION RULE =====
'''

    lua_script = lua_script.rstrip() + helper_functions

    return lua_script


def _inject_operative_counter(lua_script: str, team: str) -> str:
    """
    Inject operative counter functionality into datacard Lua script for teams that need it.
    Checks team-config.yaml for operative_counter configuration.
    """
    if not _has_operative_counter(team):
        return lua_script
    
    # Check if already injected
    if "getOperativeCounterImage" in lua_script:
        return lua_script
    
    log.info(f"{team}: Injecting operative counter into datacard script")
    
    # Helper functions to inject at end of script
    helper_functions = '''

-- ===== OPERATIVE COUNTER =====

function getOperativeCounterImage()
  if not state or not state.operative_counter then return "gore-tank-3" end
  local currentValue = state.operative_counter.current or 0
  if currentValue == 0 then return "gore-tank-3"
  elseif currentValue == 1 then return "gore-tank-2"
  elseif currentValue >= 2 then return "gore-tank"
  else return "gore-tank-3" end
end

function getOperativeCounterText()
  if not state or not state.operative_counter then return "Empty" end
  local currentValue = state.operative_counter.current or 0
  if currentValue == 0 then return "Empty"
  elseif currentValue == 1 then return "Half"
  elseif currentValue >= 2 then return "Full"
  else return "Empty" end
end

function change_operative_counter(player, value, id)
  if value == "-1" then decrease_operative_counter(player.color)
  elseif value == "-2" then increase_operative_counter(player.color) end
end

function decrease_operative_counter(pc)
  if not state or not state.operative_counter then return end
  local minVal = state.operative_counter.min or 0
  local currentVal = state.operative_counter.current or 0
  if currentVal > minVal then
    state.operative_counter.current = currentVal - 1
    broadcastToColor(string.format("Gore Tank: %s", getOperativeCounterText()), pc, Color.Yellow)
  else
    broadcastToColor("Gore Tank already Empty", pc, Color.Orange)
  end
end

function increase_operative_counter(pc)
  if not state or not state.operative_counter then return end
  local maxVal = state.operative_counter.max or 2
  local currentVal = state.operative_counter.current or 0
  if currentVal < maxVal then
    state.operative_counter.current = currentVal + 1
    broadcastToColor(string.format("Gore Tank: %s", getOperativeCounterText()), pc, Color.Yellow)
  else
    broadcastToColor("Gore Tank already Full", pc, Color.Orange)
  end
end

-- ===== END OPERATIVE COUNTER =====
-- Add Gore Tank context menu function
function addGoreTankToModel(playerColor)
    local model = findModelOnCard()
    if model == nil then
        broadcastToColor("Place a KTUIMini model on this card first.", playerColor, Color.Orange)
        return
    end
    
    local modelLua = model.getLuaScript() or ""
    if modelLua == "" then
        broadcastToColor("Model has no Lua script (not a KTUI model?).", playerColor, Color.Red)
        return
    end
    
    if modelLua:find("ktcnid%-status%-operative%-counter") then
        broadcastToColor("Model already has Gore Tank counter.", playerColor, Color.White)
        return
    end
    
    -- 1. Add helper functions
    local helperFuncs = [=[

-- Gore Tank Counter
function getOperativeCounterImage()
  local currentValue = state.operative_counter.current or 0
  if currentValue == 0 then return "gore-tank-3"
  elseif currentValue == 1 then return "gore-tank-2"
  elseif currentValue >= 2 then return "gore-tank"
  else return "gore-tank-3" end
end

function change_operative_counter(player, value, id)
  if not state.operative_counter then return end
  local current = state.operative_counter.current or 0
  local max = state.operative_counter.max or 2
  local min = state.operative_counter.min or 0
  
  -- Left click (value "-1"): decrease, Right click (value "-2"): increase
  if value == "-1" then
    if current > min then current = current - 1 end
  elseif value == "-2" then
    if current < max then current = current + 1 end
  end
  
  state.operative_counter.current = current
  refreshUI()
  local labels = {[0]="Empty", [1]="Half", [2]="Full"}
  broadcastToColor("Gore Tank: " .. (labels[current] or "?"), player.color, Color.Yellow)
end
]=]
    
    -- 2. Inject counter panel into refreshUI's xmlTable  
    -- Build the panel text that will be inserted into model source
    local counterPanel = '\\n    <Panel color="#80808000" outline="#FFFF00" outlineSize="3 3" width="45" height="45" offsetXY="0 -10">'
    counterPanel = counterPanel .. '\\n      <Image id="ktcnid-status-operative-counter" image="'
    counterPanel = counterPanel .. ']]' .. '..getOperativeCounterImage()..' .. '[['
    counterPanel = counterPanel .. '" preserveAspect="true" rectAlignment="MiddleCenter" onClick="change_operative_counter" />'
    counterPanel = counterPanel .. '\\n    </Panel>'
    
    local xmlPattern = "(<HorizontalLayout spacing=\\"3\\" width=\\"@totalAtt\\")"
    if modelLua:find(xmlPattern) then
        modelLua = modelLua:gsub(xmlPattern, counterPanel .. "\\n    %1")
    else
        broadcastToColor("Could not find attachment layout in model.", playerColor, Color.Red)
        return
    end
    
    -- 3. Add assets to baseBundle
    -- Build asset entries as text that will be inserted into model source
    local assets = "    {name=\\"gore-tank\\", url="
    assets = assets .. "[" .. "=[https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/chaos/goremongers/tts/token/goremongers-gore-tank-full.png]" .. "=]},\\n"
    assets = assets .. "    {name=\\"gore-tank-2\\", url="
    assets = assets .. "[" .. "=[https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/chaos/goremongers/tts/token/goremongers-gore-tank-half.png]" .. "=]},\\n"
    assets = assets .. "    {name=\\"gore-tank-3\\", url="
    assets = assets .. "[" .. "=[https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/chaos/goremongers/tts/token/goremongers-gore-tank-empty.png]" .. "=]},"
    
    local bundlePattern = "({name=\\"Wound_red\\"[^\\n]+)"
    if modelLua:find(bundlePattern) then
        modelLua = modelLua:gsub(bundlePattern, "%1\\n" .. assets)
    end
    
    -- Append helper functions
    modelLua = modelLua .. helperFuncs
    
    -- Initialize state.operative_counter on the model
    local modelState = model.script_state or "{}"
    local state = JSON.decode(modelState)
    if not state.operative_counter then
        state.operative_counter = {current = 0, max = 2, min = 0}
    end
    model.script_state = JSON.encode(state)
    
    -- Write back and reload
    model.setLuaScript(modelLua)
    Wait.frames(function() model.reload() end, 10)
    
    broadcastToColor("Added Gore Tank counter to model!", playerColor, Color.Green)
end

-- Extend onLoad to add context menu
local baseOnLoad = onLoad
function onLoad()
    if baseOnLoad then baseOnLoad() end
    self.addContextMenuItem("Add Gore Tank", addGoreTankToModel)
end
'''
    
    # Separate counter initialization - just the state, UI injection is done via separate context menu
    counter_init = '''
    -- Initialize operative counter state
    if not ms.operative_counter then
        ms.operative_counter = {
            name = "Gore Tank",
            max = 2,
            min = 0,
            current = 0
        }
        table.insert(changes, "Initialized Gore Tank counter")
    end
    if ms.operative_counter.current == nil then
        ms.operative_counter.current = ms.operative_counter.min or 0
    end
    '''
    
    # Inject helper functions at end
    lua_script = lua_script.rstrip() + helper_functions
    
    # Inject counter initialization before "-- Write back" in diffAndApply
    write_back_pos = lua_script.find("-- Write back")
    if write_back_pos != -1:
        lua_script = lua_script[:write_back_pos] + counter_init + "\n    " + lua_script[write_back_pos:]
    else:
        log.warning(f"{team}: Could not find insertion point for counter initialization")
    
    return lua_script


# ── Weapon type classification ──

_RANGED_RULES_PAT = re.compile(r"(range\s*\d|blast|torrent|silent)", re.IGNORECASE)
_RANGED_NAME_PAT = re.compile(
    r"(pistol|rifle|carbine|blaster|bolter|cannon|gun|launcher|"
    r"flamer|melta|plasma|las(?:cutter|gun|cannon)|auto|bolt|stubber|grenade|"
    r"needle|sniper|mortar|missile|photon|radium|phosphor|igniter|"
    r"scattergun|bow|fusil|jezzail|splinter|shuriken|starcannon|"
    r"deathspitter|strangler|devourer|fleshborer|spinefist)",
    re.IGNORECASE,
)
_MELEE_NAME_PAT = re.compile(
    r"(sword|blade|claw|fist|axe|hammer|mace|glaive|talons?|"
    r"pincer|pike|spear|staff|whip|maul|scythe|gauntlet|"
    r"bayonet|knife|dagger|spike|club|choppa|stave|fangs|"
    r"halberd|trident|sabre|falchion|cleaver|maw|beak|sabres|"
    r"claws|pincers|bonesword|lash|tendril|proboscis|crusher)",
    re.IGNORECASE,
)


def classify_weapon(weapon: dict) -> str:
    rules = weapon.get("special_rules", "")
    name = weapon.get("name", "")
    if _MELEE_NAME_PAT.search(name) and not _RANGED_RULES_PAT.search(rules):
        return "melee"
    if _RANGED_RULES_PAT.search(rules):
        return "ranged"
    if _RANGED_NAME_PAT.search(name):
        return "ranged"
    return "melee"


def tts_weapon_prefix(weapon: dict) -> str:
    if classify_weapon(weapon) == "melee":
        return "[F4641D]M[-]"
    return "[1E87FF]R[-]"


# ── Stat helpers ──

def parse_move(s: str) -> int:
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else 6


def parse_save(s: str) -> int:
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else 5


def match_weapon_rules(special_rules: str, all_rules: dict) -> dict:
    if not special_rules:
        return {}
    matched = {}
    for rule_name, desc in all_rules.items():
        base = rule_name.replace(" x", "").replace(" x+", "")
        if re.search(re.escape(base), special_rules, re.IGNORECASE):
            matched[rule_name] = desc
    return matched


# ── Roster ability helpers ──

# Unicode chars commonly found in Kill Team PDFs
_UNICODE_NORMALIZE = {
    "\u2019": "'",   # RIGHT SINGLE QUOTATION MARK (T'au)
    "\u2018": "'",   # LEFT SINGLE QUOTATION MARK
    "\u201c": '"',   # LEFT DOUBLE QUOTATION MARK
    "\u201d": '"',   # RIGHT DOUBLE QUOTATION MARK
    "\u2010": "-",   # HYPHEN
    "\u2011": "-",   # NON-BREAKING HYPHEN
    "\u2012": "-",   # FIGURE DASH
    "\u2013": "-",   # EN DASH
    "\u2014": "-",   # EM DASH
    "\u2033": '"',   # DOUBLE PRIME (inches)
    "\u2032": "'",   # PRIME
    "\u00e2": "a",   # â
    "\u00f4": "o",   # ô
}


def _normalize_text(s: str) -> str:
    """Strip control characters and normalize Unicode to ASCII equivalents."""
    s = re.sub(r"[\x07\x08]", "", s)
    for uchar, replacement in _UNICODE_NORMALIZE.items():
        s = s.replace(uchar, replacement)
    return s.strip()


def _abilities_from_roster(op: dict) -> tuple[list, list]:
    """Extract abilities and actions from a roster operative entry."""
    abilities = []
    actions = []
    for pa in op.get("passive_abilities", []):
        name = _normalize_text(pa.get("name", ""))
        text = _normalize_text(pa.get("description", ""))
        if name:
            abilities.append({"name": name, "text": text})
    for ua in op.get("unique_actions", []):
        name = _normalize_text(ua.get("name", ""))
        text = _normalize_text(ua.get("description", ""))
        if name:
            actions.append({"name": name, "text": text})
    return abilities, actions


# ── TTS Description builder ──

def build_description(name: str, stats: dict, keywords: list,
                      weapons: list, abilities: list, actions: list) -> str:
    lines = []
    lines.append(
        f'[D36B3E]'
        f'[[84E680]APL[-] [ffffff]{stats["APL"]}[-]] '
        f'[[84E680]MOVE[-] [ffffff]{stats["Move"]}"[-]]'
    )
    lines.append(
        f'[[84E680]SAVE[-] [ffffff]{stats["Save"]}+[-]] '
        f'[[84E680]WOUNDS[-] [ffffff]{stats["Wounds"]}[-]][-]'
    )
    lines.append(f'[C5C5C5]{", ".join(keywords)}[-]')
    lines.append("[31B32B]Weapons[-]")
    for w in weapons:
        s = w["stats"]
        lines.append(f'{w["name"]}')
        lines.append(
            f'[84E680]ATK[-] {s["ATK"]} '
            f'[84E680]HIT[-] {s["HIT"]} '
            f'[84E680]DMG[-] {s["DMG"]}'
        )
        wr = s.get("WR", "")
        if wr:
            lines.append(f"[84E680]WR[-]: {wr}")
        lines.append("")
    if abilities:
        lines.append("---")
        lines.append("[31B32B]Abilities[-]")
        for ab in abilities:
            lines.append(f'- [EF8450]{ab["name"]}[-]')
    if actions:
        lines.append("[31B32B]Actions[-]")
        for ac in actions:
            lines.append(f'- [D46D6C]{ac["name"]}[-]')
    return "\n".join(lines)


def _build_selection_for_gmnotes(
    selection_groups: list[list[str]], weapons: list[dict],
    exclusive_sets: list[list[int]] | None = None,
) -> dict | None:
    """Transform selection groups into indexed format for TTS GMNotes.

    Returns {"groups": [[{"label": str, "weapons": [int]}]], "fixed": [int]}
    where weapon indices are 0-based into the weapons list.
    Optionally includes "exclusive_sets" when groups have an either/or relationship.
    """
    if not selection_groups or not weapons:
        return None

    weapon_names_lower = [(w.get("plain_name") or w.get("name", "")).lower() for w in weapons]
    all_matched: set[int] = set()
    result_groups = []

    for group in selection_groups:
        group_options = []
        for option_label in group:
            # Split "; " or " and " combos into individual weapon fragments
            fragments = [f.strip().lower() for f in re.split(r'\s*;\s*|\s+and\s+', option_label)]
            matched: set[int] = set()
            for frag in fragments:
                # Handle "X or Y" alternatives within a fragment
                sub_frags = [sf.strip() for sf in frag.split(" or ")]
                for sf in sub_frags:
                    for i, wname in enumerate(weapon_names_lower):
                        if wname.startswith(sf):
                            matched.add(i)
            all_matched.update(matched)
            group_options.append({"label": option_label, "weapons": sorted(matched)})
        result_groups.append(group_options)

    # Weapons not covered by any option are always included
    fixed = [i for i in range(len(weapons)) if i not in all_matched]

    result = {"groups": result_groups, "fixed": fixed}
    if exclusive_sets:
        result["exclusive_sets"] = exclusive_sets
    return result


# ── Per-operative data builder ──

def build_operative_data(
    op: dict,
    all_rules: dict,
    abilities: list,
    actions: list,
    selection: list | None = None,
    exclusive_sets: list[list[int]] | None = None,
) -> dict:
    stats = {
        "APL": op["apl"],
        "Move": parse_move(op["movement"]),
        "Save": parse_save(op["save"]),
        "Wounds": op["wounds"],
    }
    keywords = ["Operative"] + [_normalize_text(k) for k in op["keywords"]]
    weapons = []
    weapon_rules = {}
    for w in op["weapons"]:
        wr_text = w.get("special_rules", "")
        prefix = tts_weapon_prefix(w)
        weapons.append({
            "name": f'{prefix} {w["name"]}',
            "plain_name": w["name"],
            "stats": {
                "ATK": w["attacks"],
                "HIT": w["hit"],
                "DMG": w["damage"],
                "WR": wr_text,
            },
        })
        matched = match_weapon_rules(wr_text, all_rules)
        weapon_rules.update(matched)

    # Operative display name: strip team prefix from roster name
    # e.g. "KROOT KILL-BROKER" -> take last meaningful parts
    name_parts = op["name"].split()
    # The card nickname already has the right name, but we need a display name
    # Use title-case of the full name
    display_name = _normalize_text(op["name"].title())

    description = build_description(display_name, stats, keywords, weapons, abilities, actions)

    result = {
        "name": display_name,
        "stats": stats,
        "keywords": keywords,
        "weapons": weapons,
        "abilities": abilities,
        "actions": actions,
        "weapon_rules": weapon_rules,
        "description": description,
    }
    if selection:
        indexed = _build_selection_for_gmnotes(selection, weapons, exclusive_sets)
        if indexed:
            result["selection"] = indexed
    return result


# ── Roster slug to card nickname matching ──

def roster_slug(op_name: str) -> str:
    """Slugify an operative name, stripping non-ASCII chars to match TTS card nicknames."""
    s = op_name.lower().replace(" ", "-")
    # Strip all non-ASCII chars (ô, â, ', ‑, etc.) to match card nickname generation
    s = re.sub(r"[^\x00-\x7f]", "", s)
    return s


def build_roster_lookup(roster: dict) -> dict[str, dict]:
    """Build a lookup from slug to operative data."""
    result = {}
    for op in roster["operatives"]:
        slug = roster_slug(op["name"])
        result[slug] = op
    return result


def match_card_to_roster(card_nickname: str, team: str, roster_lookup: dict) -> dict | None:
    """Match a TTS card nickname to a roster operative.
    
    Card nicknames are like: team-operative-slug (e.g. farstalker-kinband-kroot-stalker)
    Roster slugs are like: kroot-stalker (operative name slugified)
    """
    # Try: card_nickname == roster_slug (kasrkin case)
    if card_nickname in roster_lookup:
        return roster_lookup[card_nickname]
    # Try: strip team prefix
    prefix = team + "-"
    if card_nickname.startswith(prefix):
        suffix = card_nickname[len(prefix):]
        if suffix in roster_lookup:
            return roster_lookup[suffix]
    # Fuzzy: check if any roster slug is a suffix of card nickname
    for slug, op in roster_lookup.items():
        if card_nickname.endswith("-" + slug) or card_nickname.endswith(slug):
            return op
    return None


# ── Main patching logic ──

def find_datacards_in_tts(tts_data: dict) -> list[dict]:
    """Find all datacard objects in a TTS save, traversing decks and bags."""
    datacards = []
    
    def recurse(obj):
        tags = obj.get("Tags", [])
        nickname = obj.get("Nickname", "")
        name = obj.get("Name", "")
        
        if name == "Deck" and nickname == "Datacards":
            for card in obj.get("ContainedObjects", []):
                datacards.append(card)
        elif name == "Card" and any("KTCardsDatacard" in t for t in tags):
            datacards.append(obj)
        
        # Recurse into contained objects (bags, etc.)
        for child in obj.get("ContainedObjects", []):
            recurse(child)
    
    for obj in tts_data.get("ObjectStates", []):
        recurse(obj)
    
    return datacards


def patch_team(
    team: str,
    all_rules: dict,
    lua_script: str,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Patch all datacards for a team. Returns (patched_count, total_count)."""
    
    roster_path = OUTPUT_DIR / team / "statlines" / "roster.json"
    tts_team_dir = TTS_DIR / team
    
    if not roster_path.exists():
        log.warning("%s: no roster.json, skipping", team)
        return 0, 0
    if not tts_team_dir.exists():
        log.warning("%s: no tts_objects dir, skipping", team)
        return 0, 0
    
    # Load roster
    with open(roster_path, "r", encoding="utf-8") as f:
        roster = json.load(f)
    roster_lookup = build_roster_lookup(roster)
    selection_lookup = roster.get("selection", {})
    exclusive_sets_lookup = roster.get("exclusive_sets", {})
    
    # Find TTS card box JSON files
    tts_files = list(tts_team_dir.glob("*.json"))
    
    total_patched = 0
    total_cards = 0
    
    for tts_file in tts_files:
        with open(tts_file, "r", encoding="utf-8") as f:
            tts_data = json.load(f)
        
        datacards = find_datacards_in_tts(tts_data)
        if not datacards:
            continue
        
        modified = False
        for card in datacards:
            nickname = card.get("Nickname", "")
            total_cards += 1
            
            # Match card to roster operative
            op = match_card_to_roster(nickname, team, roster_lookup)
            if op is None:
                log.debug("%s: no roster match for card '%s'", team, nickname)
                continue
            
            # Get abilities from roster
            abilities, actions = _abilities_from_roster(op)
            
            # Build GMNotes data
            op_selection = selection_lookup.get(op["name"], [])
            op_exclusive_sets = exclusive_sets_lookup.get(op["name"])
            data = build_operative_data(op, all_rules, abilities, actions, op_selection, op_exclusive_sets)
            gmnotes_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
            # Normalize any remaining Unicode chars (from weapon names, WR text, etc.)
            for uchar, replacement in _UNICODE_NORMALIZE.items():
                gmnotes_json = gmnotes_json.replace(uchar, replacement)
            
            card["GMNotes"] = gmnotes_json
            final_lua = _inject_operative_counter(lua_script, team)
            final_lua = _inject_faction_rule(final_lua, team, roster)
            card["LuaScript"] = final_lua
            modified = True
            total_patched += 1
        
        if modified and not dry_run:
            # Update the bag-level lastCardUpdate timestamp
            _update_bag_timestamp(tts_data)
            with open(tts_file, "w", encoding="utf-8") as f:
                json.dump(tts_data, f, indent=2, ensure_ascii=False)
            log.info("%s: patched %s", team, tts_file.name)
    
    return total_patched, total_cards


def discover_teams() -> list[str]:
    """Discover all teams that have both roster.json and tts_objects."""
    teams = []
    if not OUTPUT_DIR.exists():
        return teams
    
    # Scan team folders directly (old structure)
    for team_dir in sorted(OUTPUT_DIR.iterdir()):
        if not team_dir.is_dir():
            continue
        team = team_dir.name
        if (team_dir / "statlines" / "roster.json").exists() and (TTS_DIR / team).exists():
            teams.append(team)
    
    return teams


def main():
    parser = argparse.ArgumentParser(description="Embed stats into TTS datacards")
    parser.add_argument("--teams", help="Comma-separated team list (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files")
    args = parser.parse_args()
    
    # Load shared resources
    with open(WEAPON_RULES_PATH, "r", encoding="utf-8") as f:
        all_rules = json.load(f)
    lua_script = LUA_SCRIPT_PATH.read_text(encoding="utf-8")
    
    if args.teams:
        teams = [t.strip() for t in args.teams.split(",")]
    else:
        teams = discover_teams()
    
    log.info("Teams to process: %d", len(teams))
    
    total_patched = 0
    total_cards = 0
    teams_ok = 0
    
    for team in teams:
        patched, cards = patch_team(team, all_rules, lua_script, dry_run=args.dry_run)
        if cards > 0:
            log.info(
                "  %-35s %2d/%2d cards patched",
                team, patched, cards,
            )
            teams_ok += 1
        total_patched += patched
        total_cards += cards
    
    mode = " (DRY RUN)" if args.dry_run else ""
    log.info("")
    log.info("Done%s: %d/%d cards patched across %d teams", mode, total_patched, total_cards, teams_ok)


if __name__ == "__main__":
    main()
