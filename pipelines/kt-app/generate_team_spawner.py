#!/usr/bin/env python3
"""
Generate the Kill Team Spawner token with embedded Lua script.
"""

import json
from pathlib import Path

def generate_spawner():
    """Generate the spawner token JSON with embedded script."""
    
    # Paths
    script_dir = Path(__file__).parent.parent
    spawner_template_path = script_dir / "tts_objects" / "display-table" / "kt_team_spawner.json"
    spawner_script_path = script_dir / "config" / "defaults" / "tts-spawner" / "team-spawner-script.lua"
    output_path = script_dir / "tts_objects" / "display-table" / "kt_team_spawner.json"
    
    print(f"Loading spawner template from: {spawner_template_path}")
    print(f"Loading spawner script from: {spawner_script_path}")
    
    # Load template
    with open(spawner_template_path, 'r', encoding='utf-8') as f:
        spawner_data = json.load(f)
    
    # Load script
    with open(spawner_script_path, 'r', encoding='utf-8') as f:
        lua_script = f.read()
    
    # Embed script
    spawner_data['ObjectStates'][0]['LuaScript'] = lua_script
    
    # Save
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(spawner_data, f, indent=2)
    
    print(f"✓ Generated spawner: {output_path}")
    print(f"  Script length: {len(lua_script)} characters")
    print(f"  Object: {spawner_data['ObjectStates'][0]['Name']}")
    print(f"  Nickname: {spawner_data['ObjectStates'][0]['Nickname']}")

if __name__ == "__main__":
    generate_spawner()
