"""One-shot: build kt_team_spawner_clean.json from the clean Lua script.

Run on demand when team-spawner-clean-script.lua changes:
    python dev/build_spawner_clean.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LUA_PATH = ROOT / "config" / "defaults" / "tts-script" / "team-spawner-clean-script.lua"
OUT_PATH = ROOT / "tts_objects" / "display-table" / "kt_team_spawner_clean.json"

lua = LUA_PATH.read_text(encoding="utf-8").replace("\n", "\r\n")

save = {
    "SaveName": "", "Date": "", "VersionNumber": "", "GameMode": "", "GameType": "",
    "GameComplexity": "", "Tags": [], "Gravity": 0.5, "PlayArea": 0.5,
    "Table": "", "Sky": "", "Note": "", "Rules": "", "XmlUI": "",
    "CustomUIAssets": [], "LuaScript": "", "LuaScriptState": "",
    "ObjectStates": [
        {
            "Name": "Custom_Tile",
            "Transform": {
                "posX": 0.0, "posY": 1.0, "posZ": 0.0,
                "rotX": 0.0, "rotY": 180.0, "rotZ": 0.0,
                "scaleX": 3.5, "scaleY": 1.0, "scaleZ": 2.5,
            },
            "Nickname": "Kill Team Spawner (clean)",
            "Description": "Click button to spawn a Kill Team card box (uses clean per-team JSON).",
            "GMNotes": "",
            "ColorDiffuse": {"r": 0.2, "g": 0.8, "b": 0.3},
            "Locked": False, "Grid": True, "Snap": True, "IgnoreFoW": False,
            "MeasureMovement": False, "DragSelectable": True, "Autoraise": True,
            "Sticky": True, "Tooltip": True, "GridProjection": False,
            "HideWhenFaceDown": False, "Hands": False,
            "CustomImage": {
                "ImageURL": "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/team-spawner-image.png",
                "ImageSecondaryURL": "",
                "ImageScalar": 1.0,
                "WidthScale": 0.0,
                "CustomTile": {
                    "Type": 0, "Thickness": 0.1, "Stackable": False, "Stretch": True,
                },
            },
            "LuaScript": lua,
            "LuaScriptState": "",
            "XmlUI": "",
            "States": {},
            "GUID": "spawnc",
        }
    ],
    "TabStates": {}, "Lighting": {}, "Hands": {}, "ComponentTags": {},
    "Turns": {}, "Grid": {}, "CameraStates": [], "DecalPallet": [], "VectorLines": [],
}

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUT_PATH.write_text(json.dumps(save, indent=2), encoding="utf-8")
print(f"Wrote {OUT_PATH.relative_to(ROOT)} ({OUT_PATH.stat().st_size} bytes, lua={len(lua)} chars)")
