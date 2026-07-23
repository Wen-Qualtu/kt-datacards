"""Build a paste-ready TTS loader script for the Sprint movement tool (POC).

Reads dev/sprint-movement-tool.lua and embeds it, verbatim, inside a small
loader script. Paste the generated dev/sprint-loader-card.lua onto any card /
tile in TTS; placing a scripted model on top and choosing the context-menu
item appends the sprint tool to that model's existing Lua script (chained
onLoad/onPickUp, no script_state clobber) so it should not break the model.

It also writes dev/sprint-loader-card.json: a ready-to-load TTS save file
containing a single flat "loader pad" (a locked block) that already carries the
loader script. Load it via TTS -> Games -> Save & Load -> ... -> open the .json,
put a model on the pad, then right-click the pad -> "Load Sprint tool to model".

Re-run this whenever sprint-movement-tool.lua changes to keep both outputs in
sync:

    python dev/build_sprint_loader.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "config" / "defaults" / "tts-script" / "sprint-movement-tool.lua"
OUT = HERE / "sprint-loader-card.lua"
OUT_JSON = HERE / "sprint-loader-card.json"

MARKER = "-- KT_SPRINT_TOOL_V1"

# Fixed so re-runs are idempotent (only the embedded Lua changes when the tool
# does). Unique enough for a standalone loader object.
LOADER_GUID = "5b7a10"


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

    # Embed the tool with the marker as its first line so the guard can detect it.
    embedded = f"{open_b}\n{MARKER}\n{code}\n{close_b}"

    return f"""-- kt-datacards: Sprint Tool Loader (POC)  [GENERATED - do not hand-edit]
-- Source: dev/sprint-movement-tool.lua  |  Regenerate: python dev/build_sprint_loader.py
--
-- Paste this onto any card / tile. Put a scripted model (e.g. a KTUI mini) on
-- top, then right-click the card -> "Load Sprint tool to model". It APPENDS
-- the sprint movement tool to the model's existing Lua script; because the
-- tool chains onLoad/onPickUp and never touches script_state, the model's own
-- scripts and saved state stay intact.

local SPRINT_MARKER = "{MARKER}"

local SPRINT_CODE = {embedded}

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

function addSprintToModel(playerColor)
    local model = findModelOnCard()
    if not model then
        broadcastToColor("Place a model on this card first.", playerColor, {{1, 0.6, 0}})
        return
    end

    local lua = model.getLuaScript() or ""
    if lua:find(SPRINT_MARKER, 1, true) then
        broadcastToColor("Model already has the Sprint tool.", playerColor, {{1, 1, 1}})
        return
    end

    -- Append (never replace). Chained onLoad/onPickUp keep the host intact.
    model.setLuaScript(lua .. "\\n\\n" .. SPRINT_CODE)
    Wait.frames(function() if model ~= nil then model.reload() end end, 10)
    broadcastToColor("Sprint tool added. Right-click the model -> 'Sprint: Begin'.", playerColor, {{0.2, 0.85, 0.3}})
end

function onLoad()
    self.addContextMenuItem("Load Sprint tool to model", addSprintToModel)
end
"""


def build_pad_object(loader_code: str) -> dict:
    """A single flat, locked pad (built-in BlockSquare) carrying the loader.

    BlockSquare is a stock TTS object, so it needs no custom image/asset URL and
    always renders. It's scaled thin and wide so a model sits flat on top and
    the loader's downward cast finds it.
    """
    return {
        "Name": "BlockSquare",
        "Transform": {
            "posX": 0.0, "posY": 1.0, "posZ": 0.0,
            "rotX": 0.0, "rotY": 0.0, "rotZ": 0.0,
            "scaleX": 4.0, "scaleY": 0.3, "scaleZ": 4.0,
        },
        "Nickname": "Sprint Tool Loader",
        "Description": "Put a model on top, then right-click -> 'Load Sprint tool to model'.",
        "GMNotes": "",
        "ColorDiffuse": {"r": 0.10, "g": 0.55, "b": 0.55},
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
        "SaveName": "Sprint Tool Loader",
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
    print("Load in TTS: Games -> Save & Load -> ... -> open sprint-loader-card.json")


if __name__ == "__main__":
    main()
