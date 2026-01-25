"""Extract just the Manager bag to a separate minimal JSON file.

This should be run BEFORE generate_display_table.py to ensure the minimal
Manager bag is the source of truth.
"""

import json
from pathlib import Path
from datetime import datetime

def main():
    workspace_dir = Path(__file__).parent.parent
    lua_template_path = workspace_dir / "config" / "defaults" / "tts-script" / "display-table-manager-script.lua"
    manager_output_path = workspace_dir / "tts_objects" / "display-table" / "kt_manager_only.json"
    
    # Load the Lua template
    with open(lua_template_path, 'r', encoding='utf-8') as f:
        lua_script = f.read()
    
    # Create a minimal Manager bag with the latest Lua script
    manager = {
        "Name": "Bag",
        "Transform": {
            "posX": 0.0,
            "posY": 32.46,
            "posZ": 30.0,
            "rotX": 0.0,
            "rotY": 270.0,
            "rotZ": 0.0,
            "scaleX": 1.0,
            "scaleY": 1.0,
            "scaleZ": 1.0
        },
        "Nickname": "KT Display Manager",
        "Description": "Manages Kill Team display table. Refresh from GitHub, Place/Recall teams, or Update Manager.",
        "GMNotes": "",
        "ColorDiffuse": {
            "r": 0.7,
            "g": 0.7,
            "b": 0.7
        },
        "Locked": False,
        "Grid": True,
        "Snap": True,
        "IgnoreFoW": False,
        "Autoraise": True,
        "Sticky": True,
        "Tooltip": True,
        "GridProjection": False,
        "HideWhenFaceDown": False,
        "Hands": False,
        "MaterialIndex": -1,
        "MeshIndex": -1,
        "LuaScript": lua_script,
        "LuaScriptState": "{}",
        "ContainedObjects": [],
        "GUID": "abc123"
    }
    
    # Create minimal save file
    minimal_save = {
        "ObjectStates": [manager]
    }
    
    # Save to file
    with open(manager_output_path, 'w', encoding='utf-8') as f:
        json.dump(minimal_save, f, indent=2, ensure_ascii=False)
    
    file_size = manager_output_path.stat().st_size / 1024
    print(f"✓ Created minimal Manager bag: {file_size:.2f} KB")
    print(f"  → {manager_output_path}")

if __name__ == '__main__':
    main()
