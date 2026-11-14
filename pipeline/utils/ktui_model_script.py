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

    # Clear the context menu first: TTS keeps runtime-added items across a script
    # swap/reload, so a re-stamp would otherwise leave stale items (e.g. an old
    # proof button) behind. Runs before the extender re-adds its own items.
    base = "self.clearContextMenu()\n\n" + base

    ext_path = tdir / _EXTENSION
    ext = ext_path.read_text(encoding="utf-8").replace("\r\n", "\n") if ext_path.exists() else ""
    return base.rstrip("\n") + ("\n\n" + ext.rstrip("\n") + "\n" if ext.strip() else "\n")


def compose_command_node_loader(config_dir: Path) -> str:
    from ..steps.tts_impl import _build_operative_counter_lua

    model_script = compose_ktui_model_script(config_dir)
    if not model_script:
        raise ValueError("KTUI model script is not available")
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
    metadata = json.dumps({team: {"name": counter["name"]} for team, counter in counters.items()})
    parts.append(f"\nNODE_COUNTER_SETUP = [====[{metadata}]====]\n")
    parts.append("\nfunction ktCommandNodeAddCounters(params)\n"
                 "    local findModelOnCard = function() return params.model end\n")
    for team, counter in counters.items():
        parts.append(f"    if params.team == {json.dumps(team)} then\n")
        parts.append(_build_operative_counter_lua(team, counter, "main"))
        parts.append("\n        addOperativeCounterToModel(params.playerColor)\n"
                     "        return true\n    end\n")
    parts.append("    return false\nend\n")
    return "".join(parts)
