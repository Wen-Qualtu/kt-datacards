#!/usr/bin/env python3
"""
Unified CLI for all generation tasks.

Commands:
  objects       Generate TTS objects (display-table, spawner, tokens)
  metadata      Generate metadata files (urls, tts-metadata, extract-tokens)
"""

import argparse
import sys
from pathlib import Path

# Add script directory to path
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir))


def main():
    parser = argparse.ArgumentParser(
        description="Generate TTS objects and metadata",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest='category', help='Generation category')
    subparsers.required = True
    
    # Objects category
    parser_objects = subparsers.add_parser('objects', help='Generate TTS objects')
    objects_sub = parser_objects.add_subparsers(dest='command', help='Object type')
    objects_sub.required = True
    
    # Objects: display-table
    obj_display = objects_sub.add_parser('display-table', help='Generate KT display table grid')
    obj_display.set_defaults(func=cmd_display_table)
    
    # Objects: manager-bag
    obj_manager = objects_sub.add_parser('manager-bag', help='Generate minimal Manager bag')
    obj_manager.set_defaults(func=cmd_manager_bag)
    
    # Objects: spawner
    obj_spawner = objects_sub.add_parser('spawner', help='Generate team spawner token')
    obj_spawner.set_defaults(func=cmd_spawner)
    
    # Objects: spawner-image
    obj_spawner_img = objects_sub.add_parser('spawner-image', help='Generate spawner button image')
    obj_spawner_img.set_defaults(func=cmd_spawner_image)
    
    # Metadata category
    parser_metadata = subparsers.add_parser('metadata', help='Generate metadata files')
    metadata_sub = parser_metadata.add_subparsers(dest='command', help='Metadata type')
    metadata_sub.required = True
    
    # Metadata: urls
    meta_urls = metadata_sub.add_parser('urls', help='Generate URLs')
    meta_urls.set_defaults(func=cmd_metadata_urls)
    
    # Metadata: tts
    meta_tts = metadata_sub.add_parser('tts', help='Generate TTS metadata')
    meta_tts.set_defaults(func=cmd_metadata_tts)
    
    # Metadata: tts-objects
    meta_tts_obj = metadata_sub.add_parser('tts-objects', help='Generate TTS objects metadata')
    meta_tts_obj.set_defaults(func=cmd_metadata_tts_objects)
    
    # Metadata: extract-tokens
    meta_tokens = metadata_sub.add_parser('extract-tokens', help='Extract token bags')
    meta_tokens.set_defaults(func=cmd_extract_tokens)
    
    args = parser.parse_args()
    args.func(args)


# ============================================================================
# OBJECTS COMMANDS
# ============================================================================

def cmd_display_table(args):
    """Generate the KT display table."""
    from generators.objects.tts_objects import DisplayTableGenerator
    from config import PROJECT_ROOT, TTS_OBJECTS_DIR
    
    gen = DisplayTableGenerator(
        tts_objects_dir=TTS_OBJECTS_DIR,
        display_table_path=TTS_OBJECTS_DIR / "display-table" / "kt_all_teams_grid.json",
    )
    count = gen.regenerate()
    print(f"\n✓ Display table regenerated with {count} teams")


def cmd_manager_bag(args):
    """Generate the minimal Manager bag."""
    import json
    from datetime import datetime
    from config import CONFIG_DIR, TTS_OBJECTS_DIR
    
    lua_template_path = CONFIG_DIR / "defaults" / "tts-script" / "display-table-manager-script.lua"
    manager_output_path = TTS_OBJECTS_DIR / "display-table" / "kt_manager_only.json"
    
    with open(lua_template_path, 'r', encoding='utf-8') as f:
        lua_script = f.read()
    
    manager = {
        "Name": "Bag",
        "Transform": {
            "posX": 0.0, "posY": 32.46, "posZ": 30.0,
            "rotX": 0.0, "rotY": 270.0, "rotZ": 0.0,
            "scaleX": 1.0, "scaleY": 1.0, "scaleZ": 1.0,
        },
        "Nickname": "KT Display Manager",
        "Description": "Place / Recall all teams\nScript auto-updates on load",
        "GMNotes": "", "ColorDiffuse": {"r": 0.7, "g": 0.7, "b": 0.7},
        "LayoutGroupSortIndex": 0, "Value": 0, "Locked": False,
        "Grid": True, "Snap": True, "IgnoreFoW": False,
        "MeasureMovement": False, "DragSelectable": True,
        "Autoraise": True, "Sticky": True, "Tooltip": True,
        "GridProjection": False, "HideWhenFaceDown": False,
        "Hands": False, "MaterialIndex": -1, "MeshIndex": -1,
        "Bag": {"Order": 0},
        "LuaScript": lua_script,
        "LuaScriptState": "{}",
        "XmlUI": "",
        "ContainedObjects": [],
        "GUID": "b01a33",
    }
    
    save_data = {
        "SaveName": "KT Manager Only", "GameMode": "", "Gravity": 0.5,
        "PlayArea": 0.5,
        "Date": datetime.now().strftime("%m/%d/%Y %I:%M:%S %p").lstrip("0"),
        "Table": "", "Sky": "", "Note": "", "Rules": "", "XmlUI": "",
        "ObjectStates": [manager], "TabStates": {}, "VersionNumber": "",
    }
    
    manager_output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manager_output_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2)
    
    print(f"✓ Manager bag created: {manager_output_path}")


def cmd_spawner(args):
    """Generate the team spawner token."""
    import json
    from config import CONFIG_DIR, TTS_OBJECTS_DIR
    
    spawner_template_path = TTS_OBJECTS_DIR / "display-table" / "kt_team_spawner.json"
    spawner_script_path = CONFIG_DIR / "defaults" / "tts-script" / "team-spawner-script.lua"
    
    with open(spawner_script_path, 'r', encoding='utf-8') as f:
        lua_script = f.read()
    
    with open(spawner_template_path, 'r', encoding='utf-8') as f:
        spawner_data = json.load(f)
    
    if 'ObjectStates' in spawner_data and len(spawner_data['ObjectStates']) > 0:
        spawner_data['ObjectStates'][0]['LuaScript'] = lua_script
    
    with open(spawner_template_path, 'w', encoding='utf-8') as f:
        json.dump(spawner_data, f, indent=2)
    
    print(f"✓ Spawner token updated: {spawner_template_path}")


def cmd_spawner_image(args):
    """Generate the spawner button image."""
    from PIL import Image, ImageDraw, ImageFont
    import json
    from config import OUTPUT_V2_DIR
    
    output_path = OUTPUT_V2_DIR / "team-spawner-image.png"
    tts_card_boxes_path = OUTPUT_V2_DIR / "tts-card-boxes.json"
    
    with open(tts_card_boxes_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract team names from list of box objects
    teams = sorted([box.get('team', box.get('name', 'unknown')) for box in data])
    num_teams = len(teams)
    
    num_cols = 4
    teams_per_col = (num_teams + num_cols - 1) // num_cols
    
    title_height = 100
    row_height = 32
    bottom_padding = 110
    
    width = 1400
    height = title_height + (teams_per_col * row_height) + bottom_padding
    
    img = Image.new('RGB', (width, height), color='#2d5016')
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype("arial.ttf", 48)
        team_font = ImageFont.truetype("arial.ttf", 20)
    except:
        title_font = ImageFont.load_default()
        team_font = ImageFont.load_default()
    
    title = f"Kill Team Cardbox spawner ({num_teams} teams)"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = bbox[2] - bbox[0]
    draw.text(((width - title_width) // 2, 30), title, fill='white', font=title_font)
    
    col_width = width // num_cols
    y_start = title_height
    
    for col in range(num_cols):
        x = col * col_width + 20
        start_idx = col * teams_per_col
        end_idx = min(start_idx + teams_per_col, num_teams)
        
        for i, team in enumerate(teams[start_idx:end_idx]):
            y = y_start + (i * row_height)
            draw.text((x, y), f"• {team}", fill='white', font=team_font)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    print(f"✓ Spawner image generated: {output_path}")


# ============================================================================
# METADATA COMMANDS
# ============================================================================

def cmd_metadata_urls(args):
    """Generate URLs."""
    from generators.metadata.urls import main as urls_main
    urls_main()


def cmd_metadata_tts(args):
    """Generate TTS metadata."""
    from generators.metadata.tts_metadata import main as tts_main
    tts_main()


def cmd_metadata_tts_objects(args):
    """Generate TTS objects metadata."""
    from generators.metadata.tts_objects import main as tts_obj_main
    tts_obj_main()


def cmd_extract_tokens(args):
    """Extract token bags."""
    from generators.metadata.token_bags import main as tokens_main
    tokens_main()


if __name__ == "__main__":
    main()
