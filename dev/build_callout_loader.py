"""Build a dev loader card that injects the Weapon Attack Callout POC block onto a
KTUI mini. Two grouped chat call-outs (Ranged / Close combat) + two rebindable
hotkeys. Chat-only (no dice). Injured shows the +1 hit in red with a medical
cross (matches the KTUI wound-bar injured state).

Load a mini's stats first (so state.info.weapons is populated), then put it on
this pad and right-click -> "Load attack callout to model".

Re-run whenever the embedded block changes:

    python dev/build_callout_loader.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "callout-loader-card.lua"
OUT_JSON = HERE / "callout-loader-card.json"

MARKER = "-- KT_ATTACK_CALLOUT_V1"
LOADER_GUID = "5b7a40"

# The injected block. Chains onLoad; never writes script_state. Reads the KTUI
# mini's state.info.weapons + state.wounds/state.stats.Wounds.
CALLOUT_CODE = r"""--[[ Weapon Attack Callout (POC): two grouped chat call-outs + two hotkeys.
Reads state.info.weapons (name/plain_name/stats.ATK/HIT/DMG/WR). Chat-only.
Injured shows the +1 hit in red with a medical cross. Chains onLoad. ]]
do
  local COL_R = "1E87FF"   -- our [R] ranged tag colour
  local COL_M = "F4641D"   -- our [M] melee tag colour

  local function acRanged(w)
    local n = (w and w.name) or ""
    if n:find(COL_R, 1, true) then return true end
    if n:find(COL_M, 1, true) then return false end
    local wr = (w and w.stats and w.stats.WR) or ""
    return wr:find("Range", 1, true) ~= nil
  end

  -- Match the KTUI wound-bar injured state (state.wounds < max/2).
  local function acInjured()
    if not state then return false end
    local cur  = tonumber(state.wounds)
    local maxw = tonumber(state.stats and state.stats.Wounds)
    if not cur or not maxw or maxw <= 0 then return false end
    return cur < maxw / 2
  end

  -- Non-injured -> "3+"; injured -> red "4+ ✚" (medical cross = penalty applied).
  local function acHit(hit, injured)
    hit = tostring(hit or "?")
    if not injured then return hit end
    local base = tonumber(hit:match("%d+"))
    local val  = base and ((base + 1) .. "+") or hit
    return "[FF0000]" .. val .. " ✚[-]"
  end

  local function acLine(w, injured)
    local tag  = acRanged(w) and ("[" .. COL_R .. "]R[-]") or ("[" .. COL_M .. "]M[-]")
    local name = (w and (w.plain_name or w.name)) or "?"
    local s    = (w and w.stats) or {}
    local line = string.format("%s %s   ATK: %s @ %s   DMG: %s",
      tag, name, tostring(s.ATK or "?"), acHit(s.HIT, injured), tostring(s.DMG or "?"))
    local wr = tostring(s.WR or "")
    if wr ~= "" and wr ~= "-" then line = line .. "   WR: " .. wr end
    return line
  end

  function acCallout(ranged)
    local weapons = (state and state.info and state.info.weapons) or {}
    local injured = acInjured()
    local nm = self.getName()
    local opName = (nm ~= nil and nm ~= "" and nm)
      or (state and state.info and state.info.name) or "Operative"
    local title = ranged and "[1E87FF]RANGED[-]" or "[F4641D]MELEE[-]"
    local lines = { title .. " -- " .. opName }
    for _, w in ipairs(weapons) do
      if acRanged(w) == ranged then lines[#lines + 1] = acLine(w, injured) end
    end
    if #lines == 1 then
      lines[#lines + 1] = ranged and "No ranged attacks." or "No melee attacks."
    end
    printToAll(table.concat(lines, "\n"), { 1, 1, 1 })
  end

  function acCalloutRanged(_) acCallout(true) end
  function acCalloutMelee(_)  acCallout(false) end

  local _ac_prev_onLoad = onLoad
  function onLoad(...)
    if _ac_prev_onLoad then pcall(_ac_prev_onLoad, ...) end
    self.addContextMenuItem("Ranged attacks", function(pc) acCallout(true) end)
    self.addContextMenuItem("Close combat attacks", function(pc) acCallout(false) end)
    if Global.getVar("KT_CALLOUT_R_HOTKEY") ~= true then
      Global.setVar("KT_CALLOUT_R_HOTKEY", true)
      addHotkey("KT: Call out ranged attacks", function(color, hovered)
        if hovered ~= nil and hovered.call ~= nil then hovered.call("acCalloutRanged", {}) end
      end, false)
    end
    if Global.getVar("KT_CALLOUT_M_HOTKEY") ~= true then
      Global.setVar("KT_CALLOUT_M_HOTKEY", true)
      addHotkey("KT: Call out melee attacks", function(color, hovered)
        if hovered ~= nil and hovered.call ~= nil then hovered.call("acCalloutMelee", {}) end
      end, false)
    end
  end
end"""


def pick_bracket_level(code: str) -> int:
    """Smallest long-bracket level whose closing token is absent from code."""
    level = 1
    while ("]" + "=" * level + "]") in code:
        level += 1
    return level


def build_loader() -> str:
    level = pick_bracket_level(CALLOUT_CODE)
    eq = "=" * level
    open_b, close_b = f"[{eq}[", f"]{eq}]"
    start_marker = f"-- START {MARKER[3:]}"
    end_marker = f"-- END {MARKER[3:]}"
    embedded = f"{open_b}\n{start_marker}\n{CALLOUT_CODE}\n{end_marker}\n{close_b}"
    return f"""-- kt-datacards: Attack Callout Loader (POC)  [GENERATED by dev/build_callout_loader.py]
-- Put a KTUI mini (stats already loaded) on this pad, then right-click ->
-- "Load attack callout to model". Injects the callout block (START/END markers);
-- loading again UPDATES it in place. Adds context items "Ranged attacks" /
-- "Close combat attacks" and two rebindable Game Keys.

local AC_START = "{start_marker}"
local AC_END   = "{end_marker}"

local AC_CODE = {embedded}

function broadcastToColor(msg, pc, col)
    if pc and Player[pc] then Player[pc].broadcast(msg, col or {{1, 1, 1}}) end
end

function findModelOnCard()
    local pos = self.getPosition()
    local hits = Physics.cast({{
        origin = Vector(pos.x, pos.y + 1.5, pos.z), direction = {{0, -1, 0}},
        type = 2, size = {{2, 2, 2}}, max_distance = 3,
    }})
    for _, hit in ipairs(hits) do
        local obj = hit.hit_object
        if obj and obj ~= self and obj.hasTag("KTUIMini") then return obj end
    end
    for _, hit in ipairs(hits) do
        local obj = hit.hit_object
        if obj and obj ~= self and obj.type == "Custom_Model" then return obj end
    end
    for _, hit in ipairs(hits) do
        local obj = hit.hit_object
        if obj and obj ~= self and obj.type == "Figurine" then return obj end
    end
    return nil
end

function addCalloutToModel(playerColor)
    local model = findModelOnCard()
    if not model then
        broadcastToColor("Place a model on this pad first.", playerColor, {{1, 0.6, 0}})
        return
    end
    local lua = model.getLuaScript() or ""
    local sStart = lua:find(AC_START, 1, true)
    if sStart then
        local _, eEnd = lua:find(AC_END, sStart, true)
        if not eEnd then
            broadcastToColor("Callout block corrupt (no END); left as-is.", playerColor, {{1, 0.6, 0}})
            return
        end
        local before = (lua:sub(1, sStart - 1)):gsub("%s+$", "")
        local after  = lua:sub(eEnd + 1)
        model.setLuaScript(before .. "\\n\\n" .. AC_CODE .. after)
        Wait.frames(function() if model ~= nil then model.reload() end end, 10)
        broadcastToColor("Attack callout updated.", playerColor, {{0.2, 0.85, 0.3}})
        return
    end
    model.setLuaScript(lua .. "\\n\\n" .. AC_CODE)
    Wait.frames(function() if model ~= nil then model.reload() end end, 10)
    broadcastToColor("Attack callout added. Right-click -> Ranged/Close combat attacks.", playerColor, {{0.2, 0.85, 0.3}})
end

function onLoad()
    self.addContextMenuItem("Load attack callout to model", addCalloutToModel)
end
"""


def loader_pad(loader: str) -> dict:
    return {
        "Name": "BlockSquare",
        "Transform": {"posX": 0.0, "posY": 1.0, "posZ": 0.0, "rotX": 0.0, "rotY": 0.0,
                      "rotZ": 0.0, "scaleX": 4.0, "scaleY": 0.3, "scaleZ": 4.0},
        "Nickname": "Attack Callout Loader",
        "Description": "Put a stats-loaded KTUI mini on top, right-click -> 'Load attack callout to model'.",
        "ColorDiffuse": {"r": 0.15, "g": 0.35, "b": 0.55}, "Locked": True, "Grid": True,
        "Snap": True, "Autoraise": True, "Tooltip": True,
        "LuaScript": loader, "LuaScriptState": "", "XmlUI": "", "GUID": LOADER_GUID,
    }


def main() -> None:
    loader = build_loader()
    OUT.write_text(loader, encoding="utf-8")
    save = {
        "SaveName": "Attack Callout Loader", "Date": "", "VersionNumber": "", "GameMode": "",
        "GameType": "", "GameComplexity": "", "Tags": [], "Gravity": 0.5, "PlayArea": 0.5,
        "Table": "", "Sky": "", "Note": "", "TabStates": {}, "LuaScript": "", "LuaScriptState": "",
        "XmlUI": "", "ObjectStates": [loader_pad(loader)],
    }
    with OUT_JSON.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(save, f, indent=2, ensure_ascii=False)
    print("wrote", OUT.name, "and", OUT_JSON.name)


if __name__ == "__main__":
    main()
