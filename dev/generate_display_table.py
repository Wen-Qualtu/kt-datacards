"""
Generate TTS Display Table JSON
================================

This script generates the display table JSON file (kt_all_teams_grid.json) that 
contains all team card bags arranged in a grid on a custom table in Tabletop Simulator.

The script:
1. Loads the base grid structure (with HandTriggers and table setup)
2. Finds all team JSON files in tts_objects/
3. Extracts the Custom_Model_Bag object from each team
4. Positions them in a grid based on alphabetical order
5. Updates the EpochTime and Date to current time
6. Outputs the complete display table JSON

Usage:
    python dev/generate_display_table.py
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Constants
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
TTS_OBJECTS_DIR = ROOT_DIR / "tts_objects"
DISPLAY_TABLE_DIR = TTS_OBJECTS_DIR / "display-table"
OUTPUT_FILE = DISPLAY_TABLE_DIR / "kt_all_teams_grid.json"

# Grid layout configuration (positions are relative to table center)
# This is a 7x6 grid layout with spacing between positions
# Based on actual workshop file (3646032507.json)
GRID_COLS = 7
GRID_ROWS = 6
GRID_SPACING_X = 12.4553365  # Horizontal spacing between bags
GRID_SPACING_Z = 7.51        # Vertical spacing between bags
GRID_START_X = -37.5753365   # Starting X position (left side)
GRID_START_Z = 22.3820934    # Starting Z position (top)
GRID_Y = 3.460002            # Y position (height above table)


def load_base_structure() -> Dict[str, Any]:
    """
    Load the base JSON structure that contains HandTriggers and table settings.
    We'll use the existing file as a template and clear out the team bags.
    """
    # Base structure with all the table setup, hand triggers, etc.
    now = datetime.now()
    date_str = f"{now.month}/{now.day}/{now.year} {now.hour % 12 or 12}:{now.minute:02d}:{now.second:02d} {'PM' if now.hour >= 12 else 'AM'}"
    
    base = {
        "SaveName": "KT24 - all team specific cards (Auto-Updating)",
        "EpochTime": int(time.time()),
        "Date": date_str,
        "VersionNumber": "v14.1.8",
        "GameMode": "KT24 - all team specific cards (Auto-Updating)",
        "GameType": "Objects",
        "GameComplexity": "Low Complexity",
        "PlayingTime": [0, 0],
        "PlayerCounts": [0, 0],
        "Tags": [
            "Wargames",
            "Cards",
            "Scripting",
            "Rules",
            "Components",
            "Scripting: Automated",
            "English"
        ],
        "Gravity": 0.5,
        "PlayArea": 0.5,
        "Table": "Table_Custom",
        "TableURL": "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/tts_objects/display-table/tts_grid_background.png",
        "Sky": "Sky_Cathedral",
        "Note": "",
        "TabStates": {
            "0": {
                "title": "Rules",
                "body": "",
                "color": "Grey",
                "visibleColor": {"r": 0.5, "g": 0.5, "b": 0.5},
                "id": 0
            },
            "1": {
                "title": "White",
                "body": "",
                "color": "White",
                "visibleColor": {"r": 1.0, "g": 1.0, "b": 1.0},
                "id": 1
            },
            "2": {
                "title": "Brown",
                "body": "",
                "color": "Brown",
                "visibleColor": {"r": 0.443, "g": 0.231, "b": 0.09},
                "id": 2
            },
            "3": {
                "title": "Red",
                "body": "",
                "color": "Red",
                "visibleColor": {"r": 0.856, "g": 0.1, "b": 0.094},
                "id": 3
            },
            "4": {
                "title": "Orange",
                "body": "",
                "color": "Orange",
                "visibleColor": {"r": 0.956, "g": 0.392, "b": 0.113},
                "id": 4
            },
            "5": {
                "title": "Yellow",
                "body": "",
                "color": "Yellow",
                "visibleColor": {"r": 0.905, "g": 0.898, "b": 0.172},
                "id": 5
            },
            "6": {
                "title": "Green",
                "body": "",
                "color": "Green",
                "visibleColor": {"r": 0.192, "g": 0.701, "b": 0.168},
                "id": 6
            },
            "7": {
                "title": "Blue",
                "body": "",
                "color": "Blue",
                "visibleColor": {"r": 0.118, "g": 0.53, "b": 1.0},
                "id": 7
            },
            "8": {
                "title": "Teal",
                "body": "",
                "color": "Teal",
                "visibleColor": {"r": 0.129, "g": 0.694, "b": 0.607},
                "id": 8
            },
            "9": {
                "title": "Purple",
                "body": "",
                "color": "Purple",
                "visibleColor": {"r": 0.627, "g": 0.125, "b": 0.941},
                "id": 9
            },
            "10": {
                "title": "Pink",
                "body": "",
                "color": "Pink",
                "visibleColor": {"r": 0.96, "g": 0.439, "b": 0.807},
                "id": 10
            },
            "11": {
                "title": "Black",
                "body": "",
                "color": "Black",
                "visibleColor": {"r": 0.25, "g": 0.25, "b": 0.25},
                "id": 11
            }
        },
        "Grid": {
            "Type": 0,
            "Lines": False,
            "Color": {"r": 0.0, "g": 0.0, "b": 0.0},
            "Opacity": 0.75,
            "ThickLines": False,
            "Snapping": False,
            "Offset": False,
            "BothSnapping": False,
            "xSize": 2.0,
            "ySize": 2.0,
            "PosOffset": {"x": 0.0, "y": 1.0, "z": 0.0}
        },
        "Lighting": {
            "LightIntensity": 0.54,
            "LightColor": {"r": 1.0, "g": 0.9804, "b": 0.8902},
            "AmbientIntensity": 1.3,
            "AmbientType": 0,
            "AmbientSkyColor": {"r": 0.5, "g": 0.5, "b": 0.5},
            "AmbientEquatorColor": {"r": 0.5, "g": 0.5, "b": 0.5},
            "AmbientGroundColor": {"r": 0.5, "g": 0.5, "b": 0.5},
            "ReflectionIntensity": 1.0,
            "LutIndex": 0,
            "LutContribution": 1.0
        },
        "Hands": {
            "Enable": True,
            "DisableUnused": False,
            "Hiding": 0
        },
        "ComponentTags": {
            "labels": [
                {"displayed": "_Faction_Decks", "normalized": "_faction_decks"}
            ]
        },
        "Turns": {
            "Enable": False,
            "Type": 0,
            "TurnOrder": [],
            "Reverse": False,
            "SkipEmpty": False,
            "DisableInteractions": False,
            "PassTurns": True,
            "TurnColor": ""
        },
        "DecalPallet": [],
        "LuaScript": "--[[ Lua code. See documentation: https://api.tabletopsimulator.com/ --]]\n\n--[[ The onLoad event is called after the game save finishes loading. --]]\nfunction onLoad()\n    --[[ print('onLoad!') --]]\nend\n\n--[[ The onUpdate event is called once per frame. --]]\nfunction onUpdate()\n    --[[ print('onUpdate loop!') --]]\nend",
        "LuaScriptState": "",
        "XmlUI": "<!-- Xml UI. See documentation: https://api.tabletopsimulator.com/ui/introUI/ -->",
        "ObjectStates": []
    }
    
    return base


def create_hand_triggers() -> List[Dict[str, Any]]:
    """
    Create the HandTrigger objects that define player zones.
    These are colored zones around the table edge.
    """
    hand_triggers = [
        {
            "GUID": "1f9556",
            "Name": "HandTrigger",
            "Transform": {
                "posX": 23.670002,
                "posY": 3.29337835,
                "posZ": 34.4527626,
                "rotX": 0.0,
                "rotY": 179.8,
                "rotZ": 0.0,
                "scaleX": 15.3268814,
                "scaleY": 11.8970528,
                "scaleZ": 6.35014772
            },
            "Nickname": "",
            "Description": "",
            "GMNotes": "",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 0.117999978, "g": 0.53, "b": 1.0, "a": 0.0},
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": True,
            "Grid": False,
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
            "FogColor": "Blue",
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        },
        {
            "GUID": "9b0781",
            "Name": "HandTrigger",
            "Transform": {
                "posX": 0.0,
                "posY": 3.29337835,
                "posZ": -34.42515,
                "rotX": 0.0,
                "rotY": 0.0,
                "rotZ": 0.0,
                "scaleX": 15.3268919,
                "scaleY": 11.8970528,
                "scaleZ": 6.35014534
            },
            "Nickname": "",
            "Description": "",
            "GMNotes": "",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 0.442999959, "g": 0.230999947, "b": 0.0899999961, "a": 0.0},
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": True,
            "Grid": False,
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
            "FogColor": "Brown",
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        },
        {
            "GUID": "368f6d",
            "Name": "HandTrigger",
            "Transform": {
                "posX": -23.670002,
                "posY": 3.29337835,
                "posZ": 34.43159,
                "rotX": 0.0,
                "rotY": 180.0,
                "rotZ": 0.0,
                "scaleX": 15.3268747,
                "scaleY": 11.8970528,
                "scaleZ": 6.35014534
            },
            "Nickname": "",
            "Description": "",
            "GMNotes": "",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 0.191999972, "g": 0.701, "b": 0.167999953, "a": 0.0},
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": True,
            "Grid": False,
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
            "FogColor": "Green",
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        },
        {
            "GUID": "d29254",
            "Name": "HandTrigger",
            "Transform": {
                "posX": -51.6596222,
                "posY": 3.29337835,
                "posZ": -11.7324,
                "rotX": 0.0,
                "rotY": 90.0,
                "rotZ": 0.0,
                "scaleX": 15.1940193,
                "scaleY": 11.8970528,
                "scaleZ": 6.40568066
            },
            "Nickname": "",
            "Description": "",
            "GMNotes": "",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 0.9559999, "g": 0.39199996, "b": 0.112999953, "a": 0.0},
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": True,
            "Grid": False,
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
            "FogColor": "Orange",
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        },
        {
            "GUID": "021dbe",
            "Name": "HandTrigger",
            "Transform": {
                "posX": 51.64263,
                "posY": 3.29337835,
                "posZ": -11.7324,
                "rotX": 0.0,
                "rotY": 270.0,
                "rotZ": 0.0,
                "scaleX": 15.1940022,
                "scaleY": 11.8970528,
                "scaleZ": 6.40568066
            },
            "Nickname": "",
            "Description": "",
            "GMNotes": "",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 0.96, "g": 0.438999981, "b": 0.807, "a": 0.0},
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": True,
            "Grid": False,
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
            "FogColor": "Pink",
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        },
        {
            "GUID": "0176c7",
            "Name": "HandTrigger",
            "Transform": {
                "posX": 51.5785675,
                "posY": 3.29337835,
                "posZ": 11.7324,
                "rotX": 0.0,
                "rotY": 270.0,
                "rotZ": 0.0,
                "scaleX": 15.194006,
                "scaleY": 11.8970528,
                "scaleZ": 6.40568066
            },
            "Nickname": "",
            "Description": "",
            "GMNotes": "",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 0.627, "g": 0.124999978, "b": 0.941, "a": 0.0},
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": True,
            "Grid": False,
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
            "FogColor": "Purple",
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        },
        {
            "GUID": "bec935",
            "Name": "HandTrigger",
            "Transform": {
                "posX": -23.670002,
                "posY": 3.29337835,
                "posZ": -34.42515,
                "rotX": 0.0,
                "rotY": 0.0,
                "rotZ": 0.0,
                "scaleX": 15.3268938,
                "scaleY": 11.8970528,
                "scaleZ": 6.35014534
            },
            "Nickname": "",
            "Description": "",
            "GMNotes": "",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 0.856, "g": 0.09999997, "b": 0.09399996, "a": 0.0},
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": True,
            "Grid": False,
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
            "FogColor": "Red",
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        },
        {
            "GUID": "203ef3",
            "Name": "HandTrigger",
            "Transform": {
                "posX": 0.0,
                "posY": 3.29337835,
                "posZ": 34.4527626,
                "rotX": 0.0,
                "rotY": 179.800049,
                "rotZ": 0.0,
                "scaleX": 15.3268843,
                "scaleY": 11.8970528,
                "scaleZ": 6.35014772
            },
            "Nickname": "",
            "Description": "",
            "GMNotes": "",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 0.128999949, "g": 0.694, "b": 0.606999934, "a": 0.0},
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": True,
            "Grid": False,
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
            "FogColor": "Teal",
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        },
        {
            "GUID": "9877ec",
            "Name": "HandTrigger",
            "Transform": {
                "posX": 23.670002,
                "posY": 3.29337835,
                "posZ": -34.2558136,
                "rotX": 0.0,
                "rotY": 0.0,
                "rotZ": 0.0,
                "scaleX": 15.3268747,
                "scaleY": 11.8970547,
                "scaleZ": 6.705048
            },
            "Nickname": "",
            "Description": "",
            "GMNotes": "",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 0.0},
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": True,
            "Grid": False,
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
            "FogColor": "White",
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        },
        {
            "GUID": "6d4167",
            "Name": "HandTrigger",
            "Transform": {
                "posX": -51.6596222,
                "posY": 3.29337835,
                "posZ": 11.7324,
                "rotX": 0.0,
                "rotY": 90.0,
                "rotZ": 0.0,
                "scaleX": 15.1940155,
                "scaleY": 11.8970528,
                "scaleZ": 6.40568066
            },
            "Nickname": "",
            "Description": "",
            "GMNotes": "",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 0.905, "g": 0.898, "b": 0.171999961, "a": 0.0},
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": True,
            "Grid": False,
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
            "FogColor": "Yellow",
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        }
    ]
    
    return hand_triggers


def get_grid_position(index: int) -> tuple:
    """
    Calculate the X and Z position for a team bag based on its index in alphabetical order.
    Grid is 10 columns x 4 rows.
    """
    row = index // GRID_COLS
    col = index % GRID_COLS
    
    x = GRID_START_X + (col * GRID_SPACING_X)
    z = GRID_START_Z - (row * GRID_SPACING_Z)
    
    return (x, z)


def load_team_bag(team_file: Path) -> Dict[str, Any]:
    """
    Load a team JSON file and extract the Custom_Model_Bag object.
    """
    with open(team_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # The team bag is the first object in ObjectStates
    if data.get("ObjectStates") and len(data["ObjectStates"]) > 0:
        return data["ObjectStates"][0]
    
    return None


def position_team_bag(team_bag: Dict[str, Any], index: int) -> Dict[str, Any]:
    """
    Update the position of a team bag based on its index in the grid.
    """
    x, z = get_grid_position(index)
    
    # Update the Transform position
    team_bag["Transform"]["posX"] = x
    team_bag["Transform"]["posY"] = GRID_Y
    team_bag["Transform"]["posZ"] = z
    team_bag["Transform"]["rotX"] = -1.50793511e-07  # Small float for consistency
    team_bag["Transform"]["rotY"] = 270.0
    team_bag["Transform"]["rotZ"] = -1.09183293e-06  # Small float for consistency
    
    return team_bag


def update_component_tags(base_structure: Dict[str, Any], team_names: List[str]):
    """
    Update the ComponentTags section with all team names.
    """
    labels = [{"displayed": "_Faction_Decks", "normalized": "_faction_decks"}]
    
    for team_name in team_names:
        labels.append({
            "displayed": f"_{team_name}",
            "normalized": f"_{team_name.lower().replace(' ', '_')}"
        })
    
    base_structure["ComponentTags"]["labels"] = labels


def main():
    """
    Main function to generate the display table JSON.
    """
    print("=" * 70)
    print("TTS Display Table Generator")
    print("=" * 70)
    print()
    
    # Find all team JSON files
    team_files = sorted(TTS_OBJECTS_DIR.glob("*Cards.json"))
    print(f"Found {len(team_files)} team JSON files")
    
    # Extract team names and sort alphabetically
    teams = []
    for team_file in team_files:
        team_name = team_file.stem.replace(" Cards", "")
        teams.append((team_name, team_file))
    
    teams.sort(key=lambda x: x[0])  # Sort by team name
    
    print(f"\nTeams in alphabetical order:")
    for i, (team_name, _) in enumerate(teams):
        print(f"  {i+1:2d}. {team_name}")
    
    # Load base structure
    print("\nBuilding display table structure...")
    base_structure = load_base_structure()
    
    # Add hand triggers
    hand_triggers = create_hand_triggers()
    base_structure["ObjectStates"].extend(hand_triggers)
    print(f"  Added {len(hand_triggers)} hand triggers")
    
    # Load and position team bags
    team_bags = []
    team_names = []
    for index, (team_name, team_file) in enumerate(teams):
        team_bag = load_team_bag(team_file)
        if team_bag:
            team_bag = position_team_bag(team_bag, index)
            team_bags.append(team_bag)
            team_names.append(team_name)
            print(f"  Loaded and positioned: {team_name}")
        else:
            print(f"  WARNING: Could not load team bag from {team_file}")
    
    base_structure["ObjectStates"].extend(team_bags)
    print(f"  Added {len(team_bags)} team bags")
    
    # Update component tags
    update_component_tags(base_structure, team_names)
    print(f"  Updated component tags with {len(team_names)} teams")
    
    # Write output file
    print(f"\nWriting output to: {OUTPUT_FILE}")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(base_structure, f, indent=2)
    
    print(f"✓ Successfully generated display table JSON")
    print(f"  File size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"  Total objects: {len(base_structure['ObjectStates'])}")
    print(f"    - Hand triggers: {len(hand_triggers)}")
    print(f"    - Team bags: {len(team_bags)}")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
