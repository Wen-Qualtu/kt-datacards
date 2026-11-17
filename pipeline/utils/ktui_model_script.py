"""Compose the KTUI model-load script embedded into datacards.

    composed = patch( vendored real extender ) + our extension

The composed script turns a plain model into the real KTUI mini (dynamic health
bar, order tokens, table Save/Load + Ready hooks) on "Load stats". Composed at
build time from two tracked sources so re-vendoring the extender (via
tools/extract_ktui_extender.py) stays a clean, one-file swap.

Patch layer (deterministic, anchor-based, each verified -- raises on drift):
  1. heal getWoundPanelWidth (bare `if` -> `elseif`)  -- append-safety, bar-neutral
  2. remove the "Movement" context item                -- we load our own movement
  3. guard the unguarded game-log call                 -- bare-table safety
  4. targeting cone uses our embedded oval-aware script (ktui-target-cone.lua)

Owner assignment is card-side (baked into script_state in datacard-load-stats.lua).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml

_EXTENDER = "ktui-extender-modelscript.lua"
_EXTENSION = "ktui-extension.lua"
_TARGET_CONE = "ktui-target-cone.lua"

_COMMAND_NODE_OVAL_RENDERER = r'''
local nodeGetCircleVectorPoints = getCircleVectorPoints

function getCircleVectorPoints(...)
    local points = nodeGetCircleVectorPoints(...)
    if not state.kt_node_ui or not state.base or state.base.x == state.base.z then return points end
    local scale = self.getScale()
    local angle = math.rad(tonumber(state.kt_front) or 0)
    local cosine, sine = math.cos(angle), math.sin(angle)
    for _, point in ipairs(points) do
        local horizontal, depth = point.x * scale.x, point.z * scale.z
        point.x = (horizontal * cosine + depth * sine) / scale.x
        point.z = (-horizontal * sine + depth * cosine) / scale.z
    end
    return points
end
'''


def _strip_header(text: str) -> str:
    lines = text.splitlines()
    i = 0
    while i < len(lines) and lines[i].startswith("--"):
        i += 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    return "\n".join(lines[i:])


def _sub_once(text: str, name: str, pattern: str, repl: str) -> str:
    new, n = re.subn(pattern, repl, text)
    if n != 1:
        raise RuntimeError(
            f"KTUI composer patch [{name}] applied {n} times (expected 1); "
            "upstream extender shape changed -- re-check the anchors."
        )
    return new


def compose_ktui_model_script(config_dir: Path) -> str:
    """Return the composed KTUI model script, or "" if the extender source is absent."""
    tdir = config_dir / "defaults" / "tts-script"
    extender_path = tdir / _EXTENDER
    if not extender_path.exists():
        return ""

    base = _strip_header(extender_path.read_text(encoding="utf-8")).replace("\r\n", "\n")

    # 1) heal getWoundPanelWidth (two bare `if` after a `return N`).
    base = _sub_once(base, "heal-getWoundPanelWidth-60",
                     r"(return\s+60\s*\n\s*)if(\s+wounds\s*<=\s*10\s+then)", r"\1elseif\2")
    base = _sub_once(base, "heal-getWoundPanelWidth-80",
                     r"(return\s+80\s*\n\s*)if(\s+wounds\s*<=\s*14\s+then)", r"\1elseif\2")
    # 2) remove the Movement context item (we load our own movement tools).
    base = _sub_once(
        base, "remove-Movement-context-item",
        r'[ \t]*self\.addContextMenuItem\(\s*"Movement"\s*,\s*function\(pc\)\s*agregaRuta\(\)\s*end\)\s*\n',
        "-- [KT] Movement context item removed (we load our own movement).\n")
    # 3) guard the unguarded game-log call.
    base = _sub_once(
        base, "guard-gameLogAppendOperativeChangedState",
        r'getObjectFromGUID\(gamelogGuid\)\.call\("gameLogAppendOperativeChangedState",\s*event\)',
        'local _kt_gl = getObjectFromGUID(gamelogGuid)\n'
        '    if _kt_gl then _kt_gl.call("gameLogAppendOperativeChangedState", event) end')

    # 4) install our oval-aware targeting cone instead of fetching the upstream
    #    circle-only "KTMT Target Cone.lua" (callback shape kept, so the rest of
    #    agregaCono is untouched).
    base = _sub_once(
        base, "local-target-cone-script",
        r'WebRequest\.get\("https://raw\.githubusercontent\.com/xSpaghettyx/KT24-Table-The-Killzone-Mod/'
        r'refs/heads/main/KTMT%20Target%20Cone\.lua",\s*function\(req\)',
        "ktLocalScript(KT_TARGET_CONE_CODE, function(req)")
    cone = (tdir / _TARGET_CONE).read_text(encoding="utf-8").replace("\r\n", "\n")
    equals = "="
    while "]" + equals + "]" in cone:
        equals += "="
    targeting = (
        f"KT_TARGET_CONE_CODE = [{equals}[\n{cone}]{equals}]\n\n"
        "function ktLocalScript(code, callback)\n"
        "    Wait.frames(function() callback({text = code}) end, 1)\n"
        "end"
    )

    # Clear the context menu first: TTS keeps runtime-added items across a script
    # swap/reload, so a re-stamp would otherwise leave stale items (e.g. an old
    # proof button) behind. Runs before the extender re-adds its own items.
    base = "self.clearContextMenu()\n\n" + base

    # Every part sits in its own START/END block so each can be found and
    # replaced in place later (movement blocks are appended by the loaders).
    parts = [_tagged("KT_MODELSCRIPT_V1", base), _tagged("KT_TARGETING_V1", targeting)]
    ext_path = tdir / _EXTENSION
    ext = ext_path.read_text(encoding="utf-8").replace("\r\n", "\n") if ext_path.exists() else ""
    if ext.strip():
        parts.append(ext.strip("\n"))
    return "\n\n".join(parts) + "\n"


def _tagged(tag: str, body: str) -> str:
    return f"-- START {tag} --\n{body.strip(chr(10))}\n-- END {tag} --"


def compose_self_selecting_model_script(config_dir: Path) -> str:
    """The KTUI model script with BOTH movement tools inside one KT_MOVEMENT
    block; at load the model runs only the one its keywords call for. One file
    that works the same wherever it is stamped (prototype)."""
    model = compose_ktui_model_script(config_dir)
    if not model:
        raise ValueError("KTUI model script is not available")
    tdir = config_dir / "defaults" / "tts-script"
    read = lambda name: (tdir / name).read_text(encoding="utf-8").replace("\r\n", "\n")
    movement = (
        f"local function ktMoveTool()\n{read('move-tool.lua')}\nend\n\n"
        f"local function ktSprintTool()\n{read('sprint-movement-tool.lua')}\nend\n\n"
        + read("ktui-movement-select.lua")
    )
    return model + "\n" + _tagged("KT_MOVEMENT_V1", movement) + "\n"


def compose_model_scripts_bundle(config_dir: Path) -> dict:
    """Scripts our KTUI extender stamps onto models: the versioned model script
    (same version as the cards' KTUI_MODELSCRIPT) plus one tagged movement block
    per kind, chosen per model by the MOUNTED keyword."""
    model = compose_ktui_model_script(config_dir)
    if not model:
        raise ValueError("KTUI model script is not available")
    version = hashlib.sha1(model.encode("utf-8")).hexdigest()[:12]
    tdir = config_dir / "defaults" / "tts-script"
    return {
        "version": version,
        "model": f'KT_MODELSCRIPT_VERSION = "{version}"\n\n' + model,
        "move": _tagged("KT_MOVE_TOOL_V1", (tdir / "move-tool.lua").read_text(encoding="utf-8")),
        "sprint": _tagged("KT_SPRINT_TOOL_V1", (tdir / "sprint-movement-tool.lua").read_text(encoding="utf-8")),
    }


def compose_command_node_loader(config_dir: Path) -> str:
    from ..steps.tts_impl import (
        _apply_generated_counter_states, _build_operative_counter_lua, _build_operative_counters_lua,
    )

    model_script = compose_ktui_model_script(config_dir)
    if not model_script:
        raise ValueError("KTUI model script is not available")
    model_script += "\n" + _tagged("KT_NODE_OVAL_V1", _COMMAND_NODE_OVAL_RENDERER) + "\n"
    version = hashlib.sha1(model_script.encode("utf-8")).hexdigest()[:12]
    model_script = f'KT_MODELSCRIPT_VERSION = "{version}"\n\n' + model_script
    script_dir = config_dir / "defaults" / "tts-script"
    scripts = {
        "KTUI_MODELSCRIPT": model_script,
        "MOVE_TOOL_CODE": (script_dir / "move-tool.lua").read_text(encoding="utf-8"),
        "SPRINT_TOOL_CODE": (script_dir / "sprint-movement-tool.lua").read_text(encoding="utf-8"),
    }
    parts = [f'KTUI_MODELSCRIPT_VERSION = "{version}"\n\n']
    for name, script in scripts.items():
        equals = ""
        while "]" + equals + "]" in script:
            equals += "="
        parts.append(f"{name} = [{equals}[{script}]{equals}]\n\n")
    parts.append((script_dir / "datacard-load-stats.lua").read_text(encoding="utf-8"))
    config = yaml.safe_load((config_dir / "team-config.yaml").read_text(encoding="utf-8"))
    counters = {
        team: info["operative_counter"] for team, info in config.get("teams", {}).items()
        if info.get("operative_counter")
    }
    setups = {team: {"name": counter["name"], "kind": "counter"} for team, counter in counters.items()}
    multi_counters = {
        team: info for team, info in config.get("teams", {}).items() if info.get("operative_counters")
    }
    for team, info in multi_counters.items():
        label = info.get("operative_counters_menu", "Add Counters").removeprefix("Add ")
        setups[team] = {"name": label, "kind": "counter"}
    for team, info in config.get("teams", {}).items():
        rule = info.get("faction_rule")
        if team not in setups and rule and rule.get("options"):
            setups[team] = {**rule, "kind": "choice"}
    metadata = json.dumps(setups)
    parts.append(f"\nNODE_COUNTER_SETUP = [====[{metadata}]====]\n")
    parts.append("\nfunction ktCommandNodeAddCounters(params)\n"
                 "    local findModelOnCard = function() return params.model end\n")
    for team, counter in counters.items():
        parts.append(f"    if params.team == {json.dumps(team)} then\n")
        parts.append(_build_operative_counter_lua(team, counter, "main"))
        parts.append("\n        addOperativeCounterToModel(params.playerColor)\n"
                     "        return true\n    end\n")
    for team, info in multi_counters.items():
        parts.append(f"    if params.team == {json.dumps(team)} then\n")
        prepared = [_apply_generated_counter_states(counter) for counter in info["operative_counters"]]
        parts.append(_build_operative_counters_lua(
            team, prepared, "main", info.get("operative_counters_menu", "Add Counters"), filter_keywords=True,
        ))
        parts.append("\n        addOperativeCountersToModel(params.playerColor)\n"
                     "        return true\n    end\n")
    parts.append("    return false\nend\n")
    return "".join(parts)
