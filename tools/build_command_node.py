"""Package the command node Lua as a Tabletop Simulator saved object."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "config" / "defaults" / "tts-script" / "command-node.lua"
DEFAULT_OUTPUT = ROOT / "dev" / "command-node.json"
def build_save(script: str) -> dict:
    return {
        "SaveName": "Kill Team Command Node",
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
        "Rules": "",
        "XmlUI": "",
        "CustomUIAssets": [],
        "LuaScript": "",
        "LuaScriptState": "",
        "ObjectStates": [{
            "GUID": "c0de01",
            "Name": "BlockSquare",
            "Transform": {
                "posX": 0.0, "posY": 1.0, "posZ": 0.0,
                "rotX": 0.0, "rotY": 0.0, "rotZ": 0.0,
                "scaleX": 2.0, "scaleY": 0.2, "scaleZ": 2.0,
            },
            "Nickname": "Kill Team Command Node",
            "Description": "Select operatives and apply their stats and loadouts to models.",
            "GMNotes": "",
            "ColorDiffuse": {"r": 0.18, "g": 0.38, "b": 0.32},
            "Locked": False,
            "LuaScript": script,
            "LuaScriptState": "",
            "XmlUI": "",
        }],
        "TabStates": {},
        "Lighting": {},
        "Hands": {},
        "ComponentTags": {},
        "Turns": {},
        "Grid": {},
        "CameraStates": [],
        "DecalPallet": [],
        "VectorLines": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--branch", default="main")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", args.branch):
        parser.error("branch must contain only letters, numbers, '.', '_', '-' or '/'")
    base_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/refs/heads/{args.branch}"
    script = f"NODE_REPO_BASE_URL = {json.dumps(base_url)}\n\n" + SCRIPT.read_text(encoding="utf-8")
    save = build_save(script)
    with args.output.open("w" if args.overwrite else "x", encoding="utf-8") as output:
        json.dump(save, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(f"Created {args.output}")


if __name__ == "__main__":
    main()