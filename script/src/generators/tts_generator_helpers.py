"""Helper functions for TTS object generation"""

import json
import random
from pathlib import Path


def generate_guid():
    """Generate a 6-character hex GUID like TTS uses"""
    return ''.join(random.choices('0123456789abcdef', k=6))


def create_single_card(card_name, front_url, back_url, team_tag, deck_id="100"):
    """Create a single TTS card object"""
    card_id = int(deck_id + "00")
    return {
        "GUID": generate_guid(),
        "Name": "Card",
        "Transform": {
            "posX": 0.0,
            "posY": 3.0,
            "posZ": 0.0,
            "rotX": 0.0,
            "rotY": 180.0,
            "rotZ": 180.0,
            "scaleX": 1.0,
            "scaleY": 1.0,
            "scaleZ": 1.0
        },
        "Nickname": card_name,
        "Description": "",
        "GMNotes": "",
        "AltLookAngle": {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0
        },
        "ColorDiffuse": {
            "r": 0.713235259,
            "g": 0.713235259,
            "b": 0.713235259
        },
        "Tags": [team_tag],
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
        "HideWhenFaceDown": True,
        "Hands": True,
        "CardID": card_id,
        "SidewaysCard": False,
        "CustomDeck": {
            deck_id: {
                "FaceURL": front_url,
                "BackURL": back_url,
                "NumWidth": 1,
                "NumHeight": 1,
                "BackIsHidden": True,
                "UniqueBack": False,
                "Type": 0
            }
        },
        "LuaScript": "",
        "LuaScriptState": "",
        "XmlUI": ""
    }


def create_deck(deck_nickname, team_tag, cards_data, starting_deck_id=1000):
    """Create a TTS deck object containing multiple cards"""
    # Generate CustomDeck entries
    custom_deck = {}
    deck_ids = []
    contained_objects = []
    
    for idx, card_data in enumerate(cards_data):
        deck_id = str(starting_deck_id + idx)
        card_name = card_data['name']
        front_url = card_data['front']
        back_url = card_data['back']
        
        custom_deck[deck_id] = {
            "FaceURL": front_url,
            "BackURL": back_url,
            "NumWidth": 1,
            "NumHeight": 1,
            "BackIsHidden": True,
            "UniqueBack": False,
            "Type": 0
        }
        
        deck_ids.append(int(deck_id + "00"))
        
        # Card in deck doesn't need full properties
        card_obj = {
            "GUID": generate_guid(),
            "Name": "Card",
            "Transform": {
                "posX": 0.0,
                "posY": 0.0,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 180.0,
                "rotZ": 180.0,
                "scaleX": 1.0,
                "scaleY": 1.0,
                "scaleZ": 1.0
            },
            "Nickname": card_name,
            "Description": "",
            "GMNotes": "",
            "AltLookAngle": {
                "x": 0.0,
                "y": 0.0,
                "z": 0.0
            },
            "ColorDiffuse": {
                "r": 0.713235259,
                "g": 0.713235259,
                "b": 0.713235259
            },
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
            "HideWhenFaceDown": True,
            "Hands": True,
            "CardID": int(deck_id + "00"),
            "SidewaysCard": False
        }
        contained_objects.append(card_obj)
    
    return {
        "GUID": generate_guid(),
        "Name": "Deck",
        "Transform": {
            "posX": 0.0,
            "posY": 3.0,
            "posZ": 0.0,
            "rotX": 0.0,
            "rotY": 180.0,
            "rotZ": 180.0,
            "scaleX": 1.0,
            "scaleY": 1.0,
            "scaleZ": 1.0
        },
        "Nickname": deck_nickname,
        "Description": "",
        "GMNotes": "",
        "AltLookAngle": {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0
        },
        "ColorDiffuse": {
            "r": 0.713235259,
            "g": 0.713235259,
            "b": 0.713235259
        },
        "Tags": [team_tag],
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
        "HideWhenFaceDown": True,
        "Hands": False,
        "SidewaysCard": False,
        "DeckIDs": deck_ids,
        "CustomDeck": custom_deck,
        "LuaScript": "",
        "LuaScriptState": "",
        "XmlUI": "",
        "ContainedObjects": contained_objects
    }


def create_bag(team_name, team_tag, contained_objects, lua_script, texture_url=None, mesh_url=None, faction=None):
    """Create a TTS Custom_Model_Bag containing decks and cards"""
    
    # Get team folder name from tag
    team_folder_name = team_tag.strip('_').lower().replace(' ', '-')
    
    # If mesh_url not provided, construct team-specific GitHub URL
    if not mesh_url:
        # Always use team-specific mesh URL (even if it's a copy of default)
        # This allows backend updates per team
        if faction:
            mesh_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/{faction}/{team_folder_name}/tts/{team_folder_name}-card-box.obj"
        else:
            # Fallback if faction not provided
            mesh_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/config/defaults/box/card-box.obj"
    
    # Texture URL should always come from parameter (GitHub URL from datacards-urls.json)
    if not texture_url:
        # Fallback: construct team-specific texture URL
        if faction:
            texture_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/{faction}/{team_folder_name}/tts/{team_folder_name}-card-box-texture.jpg"
        else:
            texture_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/config/defaults/box/card-box-texture.jpg"
    
    # Create LuaScriptState with positions for each contained object
    memory_list = {}
    
    # Position mapping based on user's manual placement
    position_map = {
        0: {"x": -1.01, "y": -2.486, "z": -4.1},     # Operative Selection - top middle
        1: {"x": -3.02, "y": -2.486, "z": -4.1},     # Faction Rules - top left
        2: {"x": 3.0, "y": -2.486, "z": -7.39},      # Markertokens - bottom far right
        3: {"x": 3.01, "y": -2.426, "z": -4.08},     # Datacards - top right
        4: {"x": 1.05, "y": -2.46, "z": -7.39},      # Equipment - bottom middle-right
        5: {"x": -0.96, "y": -2.46, "z": -7.38},     # Firefight Ploys - bottom middle
        6: {"x": -2.94, "y": -2.46, "z": -7.39},     # Strategy Ploys - bottom left
    }
    
    for idx, obj in enumerate(contained_objects):
        if idx in position_map:
            guid = obj["GUID"]
            memory_list[guid] = {
                "lock": False,
                "pos": position_map[idx],
                "rot": {"x": 0.0169, "y": 179.9995, "z": 0.0799}
            }
    
    lua_script_state = json.dumps({"ml": memory_list, "rr": 270})
    
    return {
        "SaveName": "",
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
        "TabStates": {},
        "LuaScript": "",
        "LuaScriptState": "",
        "XmlUI": "",
        "ObjectStates": [
            {
                "GUID": generate_guid(),
                "Name": "Custom_Model_Bag",
                "Transform": {
                    "posX": 0.0,
                    "posY": 3.5,
                    "posZ": 0.0,
                    "rotX": 0.0,
                    "rotY": 270.0,
                    "rotZ": 0.0,
                    "scaleX": 1.0,
                    "scaleY": 1.0,
                    "scaleZ": 1.0
                },
                "Nickname": team_name,
                "Description": "",
                "GMNotes": team_tag,
                "AltLookAngle": {
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0
                },
                "ColorDiffuse": {
                    "r": 1.0,
                    "g": 1.0,
                    "b": 1.0
                },
                "Tags": ["_Faction_Decks"],
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
                "Hands": True,
                "MaterialIndex": -1,
                "MeshIndex": -1,
                "CustomMesh": {
                    "MeshURL": mesh_url,
                    "DiffuseURL": texture_url,
                    "NormalURL": "",
                    "ColliderURL": "",
                    "Convex": True,
                    "MaterialIndex": 0,
                    "TypeIndex": 6,
                    "CastShadows": True
                },
                "Bag": {
                    "Order": 0
                },
                "LuaScript": lua_script,
                "LuaScriptState": lua_script_state,
                "XmlUI": "",
                "ContainedObjects": contained_objects
            }
        ]
    }
