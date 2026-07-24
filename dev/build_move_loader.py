"""Build a paste-ready TTS loader for the Move tool (POC).

Reads config/defaults/tts-script/move-tool.lua and embeds it, verbatim, inside
a small loader script. Paste the generated dev/move-loader-card.lua onto any
card / tile in TTS; placing a scripted model on top and choosing the context
item appends the move tool to that model's existing Lua script (chained
onLoad/onPickUp, no script_state clobber) so it should not break the model.

It also writes dev/move-loader-card.json: a ready-to-load TTS save file
containing a single flat "loader pad" (a locked black block) that already
carries the loader script. Load it via TTS -> Games -> Save & Load -> ... ->
open the .json, put a model on the pad, then right-click the pad ->
"Add Move Action".

Re-run this whenever move-tool.lua changes:

    python dev/build_move_loader.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "config" / "defaults" / "tts-script" / "move-tool.lua"
OUT = HERE / "move-loader-card.lua"
OUT_JSON = HERE / "move-loader-card.json"

MARKER_START = "-- START KT_MOVE_TOOL_V1"
MARKER_END   = "-- END KT_MOVE_TOOL_V1"

# Fixed so re-runs are idempotent (only the embedded Lua changes when the tool
# does). Unique enough for a standalone loader object.
LOADER_GUID = "5b7a20"


def pick_bracket_level(code: str) -> int:
    """Smallest long-bracket level whose closing token is absent from code."""
    level = 1
    while ("]" + "=" * level + "]") in code:
        level += 1
    return level


def build(code: str) -> str:
    level = pick_bracket_level(code)
    eq = "=" * level
    open_b, close_b = f"[{eq}[", f"]{eq}]"

    # Embed the tool wrapped in START/END markers so it can be safely stripped
    # and re-applied (updated) without cutting unrelated appended scripts.
    embedded = f"{open_b}\n{MARKER_START}\n{code}\n{MARKER_END}\n{close_b}"

    return f"""-- kt-datacards: Add Move Action Loader (POC)  [GENERATED - do not hand-edit]
-- Source: config/defaults/tts-script/move-tool.lua  |  Regenerate: python dev/build_move_loader.py
--
-- Paste this onto any card / tile. Put a scripted model (e.g. a KTUI mini) on
-- top, then right-click the card -> "Add Move Action". It APPENDS the move
-- tool to the model's existing Lua script; because the tool chains
-- onLoad/onPickUp and never touches script_state, the model's own scripts and
-- saved state stay intact.

-- Version-agnostic family prefixes so any prior version's block is stripped.
local MOVE_START = "-- START KT_MOVE_TOOL_"
local MOVE_END   = "-- END KT_MOVE_TOOL_"

local MOVE_CODE = {embedded}

function broadcastToColor(msg, pc, col)
    if pc and Player[pc] then Player[pc].broadcast(msg, col or {{1, 1, 1}}) end
end

-- Find a scripted model resting on top of this card (sphere-cast downward).
function findModelOnCard()
    local pos = self.getPosition()
    local hits = Physics.cast({{
        origin       = Vector(pos.x, pos.y + 1.5, pos.z),
        direction    = {{0, -1, 0}},
        type         = 2,
        size         = {{2, 2, 2}},
        max_distance = 3,
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

function addMoveToModel(playerColor)
    local model = findModelOnCard()
    if not model then
        broadcastToColor("Place a model on this card first.", playerColor, {{1, 0.6, 0}})
        return
    end

    local lua = model.getLuaScript() or ""
    -- Strip any previously injected block (between its START/END markers, any
    -- version) so re-running installs the CURRENT tool - it doubles as an updater.
    local updating = false
    local s = lua:find(MOVE_START, 1, true)
    if s then
        updating = true
        local e = lua:find(MOVE_END, s, true)
        if e then
            local nl = lua:find("\\n", e, true)
            lua = nl and (lua:sub(1, s - 1) .. lua:sub(nl + 1)) or lua:sub(1, s - 1)
        else
            lua = lua:sub(1, s - 1)
        end
    end
    model.setLuaScript(lua .. "\\n\\n" .. MOVE_CODE)
    Wait.frames(function() if model ~= nil then model.reload() end end, 10)
    if updating then
        broadcastToColor("Move action updated to the latest version.", playerColor, {{0.2, 0.85, 0.3}})
    else
        broadcastToColor("Move action added. Right-click the model -> Move.", playerColor, {{0.2, 0.85, 0.3}})
    end
end

function onLoad()
    self.addContextMenuItem("Add Move Action", addMoveToModel)
end
"""


def build_pad_object(loader_code: str) -> dict:
    """A single flat, locked black pad (built-in BlockSquare) carrying the loader."""
    return {
        "Name": "BlockSquare",
        "Transform": {
            "posX": 0.0, "posY": 1.0, "posZ": 0.0,
            "rotX": 0.0, "rotY": 0.0, "rotZ": 0.0,
            "scaleX": 4.0, "scaleY": 0.3, "scaleZ": 4.0,
        },
        "Nickname": "Add Move Action",
        "Description": "Put a model on top, then right-click -> 'Add Move Action'.",
        "GMNotes": "",
        "ColorDiffuse": {"r": 0.02, "g": 0.02, "b": 0.02},
        "Locked": True,
        "Grid": True,
        "Snap": True,
        "IgnoreFoW": False,
        "MeasureMovement": False,
        "DragSelectable": True,
        "Autoraise": True,
        "Sticky": False,
        "Tooltip": True,
        "GridProjection": False,
        "HideWhenFaceDown": False,
        "Hands": False,
        "LuaScript": loader_code,
        "LuaScriptState": "",
        "XmlUI": "",
        "GUID": LOADER_GUID,
    }


def build_save_file(loader_code: str) -> dict:
    """Minimal valid TTS save-file wrapper holding just the loader pad."""
    return {
        "SaveName": "Add Move Action",
        "Date": "",
        "VersionNumber": "",
        "GameMode": "",
        "GameType": "",
        "GameComplexity": "",
        "Tags": [],
        "Gravity": 0.5,
        "PlayArea": 0.5,
        "Table": "",
        "Sky": "",
        "Note": "",
        "TabStates": {},
        "LuaScript": "",
        "LuaScriptState": "",
        "XmlUI": "",
        "ObjectStates": [build_pad_object(loader_code)],
    }


def main() -> None:
    code = SRC.read_text(encoding="utf-8")
    loader = build(code)
    OUT.write_text(loader, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(HERE.parent)} ({OUT.stat().st_size} bytes)")

    with OUT_JSON.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(build_save_file(loader), f, indent=2, ensure_ascii=False)
    print(f"Wrote {OUT_JSON.relative_to(HERE.parent)} ({OUT_JSON.stat().st_size} bytes)")
    print("Load in TTS: Games -> Save & Load -> ... -> open move-loader-card.json")


if __name__ == "__main__":
    main()
