"""Package a TTS test node that installs the current sprint movement tool on models."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from tools.build_command_node import build_save

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "config" / "defaults" / "tts-script"
NODE_SCRIPT = Path(__file__).with_name("sprint_test_node.lua")
DEFAULT_OUTPUT = ROOT / "dev" / "sprint-test-node.json"


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


def build_label() -> str:
    try:
        git = ["git", "-C", str(ROOT)]
        branch = subprocess.check_output([*git, "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
        commit = subprocess.check_output([*git, "rev-parse", "--short", "HEAD"], text=True).strip()
        dirty = subprocess.run([*git, "diff", "--quiet", "--", str(SCRIPT_DIR / "sprint-movement-tool.lua")]).returncode
        return f"{branch}@{commit}{'+local' if dirty else ''}"
    except (OSError, subprocess.CalledProcessError):
        return "local"


def build_script(label: str) -> str:
    sprint = (SCRIPT_DIR / "sprint-movement-tool.lua").read_text(encoding="utf-8")
    block = f"-- START KT_SPRINT_TOOL_V1\n{sprint}\n-- END KT_SPRINT_TOOL_V1"
    return (
        f"SPRINT_TEST_BUILD = {json.dumps(label)}\n\n"
        f"SPRINT_TOOL_CODE = {long_string(block)}\n\n"
        f"{inject_helpers()}\n"
        f"{NODE_SCRIPT.read_text(encoding='utf-8')}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    label = build_label()
    save = build_save(build_script(label))
    obj = save["ObjectStates"][0]
    save["SaveName"] = obj["Nickname"] = f"Sprint Test Node ({label})"
    obj["GUID"] = "5b7e57"
    obj["Description"] = "Right-click or press Load Sprint to install the sprint tool on selected models or models on this node."
    obj["Tags"] = ["Sprint Test Node"]
    obj["ColorDiffuse"] = {"r": 0.15, "g": 0.35, "b": 0.6}
    args.output.write_text(json.dumps(save, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created {args.output} ({label})")


if __name__ == "__main__":
    main()
