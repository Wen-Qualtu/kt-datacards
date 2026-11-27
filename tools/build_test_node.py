"""Package a TTS test node that installs current model tools (sprint, move, targeting) on models."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from pipeline.utils.ktui_model_script import compose_ktui_model_script
from tools.build_command_node import build_save

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
SCRIPT_DIR = CONFIG_DIR / "defaults" / "tts-script"
NODE_SCRIPT = Path(__file__).with_name("test_node.lua")


def long_string(text: str) -> str:
    level = 0
    while ("]" + "=" * level + "]") in text:
        level += 1
    eq = "=" * level
    return f"[{eq}[\n{text}\n]{eq}]"


def inject_helpers() -> str:
    source = (SCRIPT_DIR / "datacard-load-stats.lua").read_text(encoding="utf-8")
    start = source.index("function healExtenderScript(")
    end = source.index("\nend\n", source.index("function injectBlock(")) + len("\nend\n")
    return source[start:end]


def sprint_code() -> str:
    return (SCRIPT_DIR / "sprint-movement-tool.lua").read_text(encoding="utf-8")


def move_code() -> str:
    return (SCRIPT_DIR / "move-tool.lua").read_text(encoding="utf-8")


def targeting_code() -> str:
    # Redefines agregaCono (called by the model's "Targeting lines" item) with the
    # composed, oval-aware version, so it also upgrades models with an old script.
    composed = compose_ktui_model_script(CONFIG_DIR)
    match = re.search(r"^function agregaCono\(\)\n.*?^end\n(?=\s*function agregaConoR\(\))", composed, re.S | re.M)
    if not match:
        raise RuntimeError("agregaCono not found in the composed KTUI model script")
    cone = (SCRIPT_DIR / "ktui-target-cone.lua").read_text(encoding="utf-8").replace("\r\n", "\n")
    return (
        f"KT_TARGET_CONE_CODE = {long_string(cone)}\n\n"
        "function ktLocalScript(code, callback)\n"
        "    Wait.frames(function() callback({text = code}) end, 1)\n"
        "end\n\n" + match.group(0)
    )


# Each block is (marker, code). Markers match the pipeline's tagged blocks where
# one exists (KT_MOVE_TOOL_ / KT_SPRINT_TOOL_), so the node REPLACES the block a
# card already installed instead of stacking a second copy.
SPRINT_BLOCK = ("KT_SPRINT_TOOL_", sprint_code)
MOVE_BLOCK = ("KT_MOVE_TOOL_", move_code)
TARGETING_BLOCK = ("KT_TARGETING_TEST_", targeting_code)
TARGETING_SOURCES = ["ktui-target-cone.lua", "ktui-extender-modelscript.lua"]

TOOLS = {
    "sprint": {
        "label": "Sprint",
        "blocks": [SPRINT_BLOCK],
        "sources": ["sprint-movement-tool.lua"],
        "hint": "Right-click model -> Sprint / Turn / Leap.",
        "color": {"r": 0.15, "g": 0.35, "b": 0.6},
        "guid": "5b7e57",
    },
    "targeting": {
        "label": "Targeting",
        "blocks": [TARGETING_BLOCK],
        "sources": TARGETING_SOURCES,
        "hint": "Right-click model -> Targeting lines.",
        "color": {"r": 0.6, "g": 0.2, "b": 0.15},
        "guid": "7a6e70",
    },
    "move": {
        "label": "Move",
        "blocks": [MOVE_BLOCK],
        "sources": ["move-tool.lua"],
        "hint": "Right-click model -> Move / Dash.",
        "color": {"r": 0.15, "g": 0.55, "b": 0.25},
        "guid": "30e7c1",
    },
    "move-targeting": {
        "label": "Move + Targeting",
        "blocks": [MOVE_BLOCK, TARGETING_BLOCK],
        "sources": ["move-tool.lua", *TARGETING_SOURCES],
        "hint": "Right-click model -> Move / Dash / Targeting lines.",
        "color": {"r": 0.55, "g": 0.45, "b": 0.1},
        "guid": "3e77a9",
    },
}


def build_label(sources: list[str]) -> str:
    try:
        git = ["git", "-C", str(ROOT)]
        branch = subprocess.check_output([*git, "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
        commit = subprocess.check_output([*git, "rev-parse", "--short", "HEAD"], text=True).strip()
        dirty = subprocess.run([*git, "diff", "--quiet", "HEAD", "--", *(str(SCRIPT_DIR / s) for s in sources)]).returncode
        if not dirty:
            return f"{branch}@{commit}"
        # Distinguishes successive local rebuilds in-game.
        digest = hashlib.sha1(b"".join((SCRIPT_DIR / s).read_bytes() for s in sources)).hexdigest()[:6]
        return f"{branch}@{commit}+local.{digest}"
    except (OSError, subprocess.CalledProcessError):
        return "local"


def build_blocks(tool: dict) -> str:
    entries = []
    for marker, code in tool["blocks"]:
        start, end = f"-- START {marker}", f"-- END {marker}"
        block = f"{start}V1 --\n{code().strip(chr(10))}\n{end}V1 --"
        entries.append(
            f"    {{start = {json.dumps(start)}, finish = {json.dumps(end)},\n"
            f"     code = {long_string(block)}}},"
        )
    return "NODE_BLOCKS = {\n" + "\n".join(entries) + "\n}"


def build_script(tool: dict, label: str) -> str:
    move_debug = MOVE_BLOCK in tool["blocks"]
    return (
        f"NODE_TOOL = {json.dumps(tool['label'])}\n"
        f"NODE_BUILD = {json.dumps(label)}\n"
        f"NODE_HINT = {json.dumps(tool['hint'])}\n"
        f"NODE_MOVE_DEBUG = {'true' if move_debug else 'false'}\n\n"
        f"{build_blocks(tool)}\n\n"
        f"{inject_helpers()}\n"
        f"{NODE_SCRIPT.read_text(encoding='utf-8')}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", choices=sorted(TOOLS), default="sprint")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    tool = TOOLS[args.tool]
    output = args.output or ROOT / "dev" / f"{args.tool}-test-node.json"
    label = build_label(tool["sources"])
    save = build_save(build_script(tool, label))
    obj = save["ObjectStates"][0]
    save["SaveName"] = obj["Nickname"] = f"{tool['label']} Test Node ({label})"
    obj["GUID"] = tool["guid"]
    obj["Description"] = (
        f"Right-click or press Load to install the {tool['label'].lower()} tool(s) "
        "on selected models or models on this node."
    )
    obj["Tags"] = [f"{tool['label']} Test Node"]
    obj["ColorDiffuse"] = tool["color"]
    output.write_text(json.dumps(save, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created {output} ({label})")


if __name__ == "__main__":
    main()
