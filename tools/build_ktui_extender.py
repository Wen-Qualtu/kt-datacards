"""Package our KTUI extender board (a copy of the base table's "UI Extender + Tools"
board running our script) as a Tabletop Simulator saved object."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from tools.build_command_node import build_save

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "config" / "defaults" / "ktui-extender-board.json"
SCRIPT = ROOT / "config" / "defaults" / "tts-script" / "ktui-extender-board.lua"
DEFAULT_OUTPUT = ROOT / "dev" / "ktui-extender.json"
NAME = "UI Extender + Tools (KT Datacards)"


def build_board(branch: str) -> dict:
    url = (f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/refs/heads/{branch}"
           "/output/_generic-tts-objects/ktui-model-scripts.json")
    board = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    board.update({
        "GUID": "e7e7d0",
        "Nickname": NAME if branch == "main" else f"{NAME} [{branch}]",
        "Description": (
            '- Place scripted miniatures on this board and press "Extend KT UI"\n'
            "- Access movement (Move/Dash or Sprint/Turn/Leap) and targeting lines through "
            "the context menu by right-clicking the extended miniatures"
        ),
        "LuaScript": f"KT_SCRIPTS_URL = {json.dumps(url)}\n\n" + SCRIPT.read_text(encoding="utf-8"),
        "LuaScriptState": "",
    })
    return board


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--branch", default="main")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", args.branch):
        parser.error("branch must contain only letters, numbers, '.', '_', '-' or '/'")
    save = build_save("")
    board = build_board(args.branch)
    save["SaveName"] = board["Nickname"]
    save["ObjectStates"] = [board]
    args.output.write_text(json.dumps(save, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created {args.output} ({board['Nickname']})")


if __name__ == "__main__":
    main()
