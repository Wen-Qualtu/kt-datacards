#!/usr/bin/env python3
"""
Unified CLI for generating TTS objects.

Commands:
  display-table    Generate the KT display table grid
  manager-bag      Generate the minimal Manager bag
  spawner          Generate the team spawner token
  spawner-image    Generate the spawner button image
"""

import argparse
import sys
from pathlib import Path

# Add parent to path for imports
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir))


def cmd_display_table(args):
    """Generate the KT display table."""
    from generators.objects.display_table import DisplayTableGenerator
    
    workspace_dir = Path(__file__).parent.parent.parent
    gen = DisplayTableGenerator(
        tts_objects_dir=workspace_dir / "tts_objects",
        display_table_path=workspace_dir / "tts_objects" / "display-table" / "kt_all_teams_grid.json",
    )
    count = gen.regenerate()
    print(f"\n✓ Display table regenerated with {count} teams")


def cmd_manager_bag(args):
    """Generate the minimal Manager bag."""
    import json
    from datetime import datetime
    
    workspace_dir = Path(__file__).parent.parent.parent
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
            "scaleZ": 1.0,
        },
        "Nickname": "KT Display Manager",
        "Description": "Place / Recall all teams\nScript auto-updates on load",
        "GMNotes": "",
        "ColorDiffuse": {"r": 0.7, "g": 0.7, "b": 0.7},
        "LayoutGroupSortIndex": 0,
        "Value": 0,
        "Locked": False,
        "Grid": True,
        "Snap": True,
        "IgnoreFoW": False,
        "MeasureMovement": False,
        "DragSelectable": True,
        "Autoraise": True,
        "Sticky": True,
        "Tooltip": True,
        "GridProjection": False,
        "HideWhenFaceDown": False,
        "Hands": False,
        "MaterialIndex": -1,
        "MeshIndex": -1,
        "Bag": {"Order": 0},
        "LuaScript": lua_script,
        "LuaScriptState": "{}",
        "XmlUI": "",
        "ContainedObjects": [],
        "GUID": "b01a33",
    }
    
    save_data = {
        "SaveName": "KT Manager Only",
        "GameMode": "",
        "Gravity": 0.5,
        "PlayArea": 0.5,
        "Date": datetime.now().strftime("%m/%d/%Y %I:%M:%S %p").lstrip("0"),
        "Table": "",
        "Sky": "",
        "Note": "",
        "Rules": "",
        "XmlUI": "",
        "ObjectStates": [manager],
        "TabStates": {},
        "VersionNumber": "",
    }
    
    manager_output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manager_output_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2)
    
    print(f"✓ Manager bag created: {manager_output_path}")


def cmd_spawner(args):
    """Generate the team spawner token."""
    import json
    
    script_dir = Path(__file__).parent.parent.parent
    spawner_template_path = script_dir / "tts_objects" / "display-table" / "kt_team_spawner.json"
    spawner_script_path = script_dir / "config" / "defaults" / "tts-script" / "team-spawner-script.lua"
    
    # Load the Lua script
    with open(spawner_script_path, 'r', encoding='utf-8') as f:
        lua_script = f.read()
    
    # Load the template
    with open(spawner_template_path, 'r', encoding='utf-8') as f:
        spawner_data = json.load(f)
    
    # Update the Lua script in the spawner
    if 'ObjectStates' in spawner_data and len(spawner_data['ObjectStates']) > 0:
        spawner_data['ObjectStates'][0]['LuaScript'] = lua_script
    
    # Write back
    with open(spawner_template_path, 'w', encoding='utf-8') as f:
        json.dump(spawner_data, f, indent=2)
    
    print(f"✓ Spawner token updated: {spawner_template_path}")


def cmd_spawner_image(args):
    """Generate the spawner button image."""
    from PIL import Image, ImageDraw, ImageFont
    import json
    
    workspace_dir = Path(__file__).parent.parent.parent
    output_path = workspace_dir / "output_v2" / "team-spawner-image.png"
    tts_card_boxes_path = workspace_dir / "output_v2" / "tts-card-boxes.json"
    
    # Load team data
    with open(tts_card_boxes_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    teams = sorted(data.get('teams', []))
    num_teams = len(teams)
    
    # Image dimensions
    num_cols = 4
    teams_per_col = (num_teams + num_cols - 1) // num_cols
    
    title_height = 100
    row_height = 32
    bottom_padding = 110
    
    width = 1400
    height = title_height + (teams_per_col * row_height) + bottom_padding
    
    # Create image
    img = Image.new('RGB', (width, height), color='#2d5016')
    draw = ImageDraw.Draw(img)
    
    # Try to load font
    try:
        title_font = ImageFont.truetype("arial.ttf", 48)
        team_font = ImageFont.truetype("arial.ttf", 20)
    except:
        title_font = ImageFont.load_default()
        team_font = ImageFont.load_default()
    
    # Draw title
    title = f"Kill Team Cardbox spawner ({num_teams} teams)"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = bbox[2] - bbox[0]
    draw.text(((width - title_width) // 2, 30), title, fill='white', font=title_font)
    
    # Draw team names in columns
    col_width = width // num_cols
    y_start = title_height
    
    for col in range(num_cols):
        x = col * col_width + 20
        start_idx = col * teams_per_col
        end_idx = min(start_idx + teams_per_col, num_teams)
        
        for i, team in enumerate(teams[start_idx:end_idx]):
            y = y_start + (i * row_height)
            draw.text((x, y), f"• {team}", fill='white', font=team_font)
    
    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    print(f"✓ Spawner image generated: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate TTS objects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    subparsers.required = True
    
    # Display table command
    parser_display = subparsers.add_parser('display-table', help='Generate KT display table grid')
    parser_display.set_defaults(func=cmd_display_table)
    
    # Manager bag command
    parser_manager = subparsers.add_parser('manager-bag', help='Generate minimal Manager bag')
    parser_manager.set_defaults(func=cmd_manager_bag)
    
    # Spawner command
    parser_spawner = subparsers.add_parser('spawner', help='Generate team spawner token')
    parser_spawner.set_defaults(func=cmd_spawner)
    
    # Spawner image command
    parser_spawner_img = subparsers.add_parser('spawner-image', help='Generate spawner button image')
    parser_spawner_img.set_defaults(func=cmd_spawner_image)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
