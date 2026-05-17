"""Helper functions for TTS object generation"""

import hashlib
import json
import random
from pathlib import Path
from typing import Optional

# Cache for team GUID mappings
_TEAM_GUID_CACHE = None


def _load_team_guids():
    """Load team GUID mappings from config file."""
    global _TEAM_GUID_CACHE
    if _TEAM_GUID_CACHE is None:
        guid_file = Path(__file__).parent.parent.parent.parent / 'config' / 'team-guids.json'
        if guid_file.exists():
            with open(guid_file, 'r', encoding='utf-8') as f:
                _TEAM_GUID_CACHE = json.load(f)
        else:
            _TEAM_GUID_CACHE = {}
    return _TEAM_GUID_CACHE


def generate_guid(seed: Optional[str] = None):
    """Generate a 6-character hex GUID like TTS uses.
    
    Args:
        seed: Optional seed string for deterministic GUID generation.
              If provided, the same seed always produces the same GUID.
              If None, generates a random GUID.
    """
    if seed is None:
        return ''.join(random.choices('0123456789abcdef', k=6))
    
    # Deterministic GUID from seed
    hash_obj = hashlib.md5(seed.encode('utf-8'))
    return hash_obj.hexdigest()[:6]


def get_team_guid(team_name: str) -> str:
    """Get the GUID for a team, using the canonical mapping if available.
    
    Args:
        team_name: Team name (e.g., "Battleclade", "Ratlings")
        
    Returns:
        6-character hex GUID for the team
    """
    global _TEAM_GUID_CACHE
    guids = _load_team_guids()
    
    # Try exact match first
    if team_name in guids:
        return guids[team_name]
    
    # Try case-insensitive match
    team_lower = team_name.lower()
    for name, guid in guids.items():
        if name.lower() == team_lower:
            return guid
    
    # New team - generate and save GUID automatically
    new_guid = generate_guid(f"team_bag:{team_name}")
    guids[team_name] = new_guid
    _TEAM_GUID_CACHE = guids
    
    # Save updated mapping to file
    guid_file = Path(__file__).parent.parent.parent.parent / 'config' / 'team-guids.json'
    try:
        with open(guid_file, 'w', encoding='utf-8') as f:
            json.dump(guids, f, indent=2, sort_keys=True)
        print(f"[INFO] Added new team GUID: {team_name} -> {new_guid}")
    except Exception as e:
        print(f"[WARNING] Could not save GUID mapping: {e}")
    
    return new_guid


def get_card_type_tag(card_type):
    """Get KTCards tag for a given card type"""
    type_tag_map = {
        "strategy-ploys": "KTCardsStrategyPloy",
        "firefight-ploys": "KTCardsFirefightPloy",
        "equipment": "KTCardsEquipment",
        "datacards": "KTCardsDatacard",
        "faction-rules": "KTCardsFactionRule",
        "operative-selection": "KTCardsOperativeSelection",
        "token-guide": "KTCardsTokenGuide",
        "markertokens": "KTCardsMarkertoken"
    }
    return type_tag_map.get(card_type)

def create_single_card(card_name, front_url, back_url, team_tag, deck_id="100", card_type=None):
    """Create a single TTS card object"""
    card_id = int(deck_id + "00")
    
    # Build tags list
    tags = [team_tag]
    if card_type:
        type_tag = get_card_type_tag(card_type)
        if type_tag:
            tags.append(type_tag)
    
    return {
        "GUID": generate_guid(f"{team_tag}:card:{card_name}"),
        "Name": "Card",
        "Transform": {
            "posX": 0.0,
            "posY": 3.0,
            "posZ": 0.0,
            "rotX": 0.0,
            "rotY": 180.0,
            "rotZ": 0.0,
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
        "Tags": tags,
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


def create_deck(deck_nickname, team_tag, cards_data, starting_deck_id=1000, card_type=None):
    """Create a TTS deck object containing multiple cards"""
    # Generate CustomDeck entries
    custom_deck = {}
    deck_ids = []
    contained_objects = []
    
    # Build tags list
    tags = [team_tag]
    if card_type:
        type_tag = get_card_type_tag(card_type)
        if type_tag:
            tags.append(type_tag)
    
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
            "GUID": generate_guid(f"{team_tag}:card:{card_name}:{idx}"),
            "Name": "Card",
            "Transform": {
                "posX": 0.0,
                "posY": 0.0,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 180.0,
                "rotZ": 0.0,
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
    
    # Reverse the order so that when TTS takes cards from the top,
    # they come out in the correct order (first card in list = first taken)
    contained_objects.reverse()
    deck_ids.reverse()
    
    return {
        "GUID": generate_guid(f"{team_tag}:deck:{deck_nickname}"),
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
        "Tags": tags,
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


def create_custom_dice(nickname: str, texture_url: str, team_tag: str, variant: str = "team") -> dict:
    """Create a TTS Custom_Dice (D6) object with a custom texture."""
    return {
        "GUID": generate_guid(f"{team_tag}:dice:{variant}"),
        "Name": "Custom_Dice",
        "Transform": {
            "posX": 0.0, "posY": 3.0, "posZ": 0.0,
            "rotX": 0.0, "rotY": 0.0, "rotZ": 0.0,
            "scaleX": 1.0, "scaleY": 1.0, "scaleZ": 1.0,
        },
        "Nickname": nickname,
        "Description": "",
        "GMNotes": "",
        "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
        "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
        "Tags": [team_tag, f"KTDice_{variant.capitalize()}"],
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
        "CustomImage": {
            "ImageURL": texture_url,
            "ImageSecondaryURL": "",
            "WidthScale": 0.0,
        },
        "CustomDice": {"Type": 1},  # Type 1 = D6
        "LuaScript": "",
        "LuaScriptState": "",
        "XmlUI": "",
    }


def create_bag(team_name, team_tag, contained_objects, lua_script, texture_url=None, mesh_url=None, faction=None, last_modified=None, last_token_modified=None):
    """Create a TTS Custom_Model_Bag containing decks and cards"""
    
    # Get team folder name from tag
    team_folder_name = team_tag.strip('_').lower().replace(' ', '-')
    
    # IMPORTANT: URLs should ALWAYS point to output_v3/{team}/cardbox/
    # NO fallback logic here - that's handled in step 6 which copies the actual files
    # If team-specific texture doesn't exist, step 6 copies default to this location
    # This allows backend updates per team without regenerating TTS objects
    
    branch = "main"
    
    if not mesh_url:
        # Always point to output_v3 cardbox location
        mesh_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{branch}/output_v3/{team_folder_name}/cardbox/{team_folder_name}-card-box.obj"
    
    if not texture_url:
        # Always point to output_v3 cardbox location
        texture_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{branch}/output_v3/{team_folder_name}/cardbox/{team_folder_name}-card-box-texture.jpg"
    
    # Create LuaScriptState with positions for each contained object.
    # IMPORTANT: Placement must be stable across teams.
    # We map by object *type* (nickname), not by list index, because teams
    # may or may not include optional objects (e.g. tokens).
    memory_list = {}

    position_by_type = {
        # Card decks - Row 1 (z = -4.0)
        "faction-rules": {"x": -4.0, "y": -2.50, "z": -4.0, "rot_y": 180.0},
        "operative-selection": {"x": -2.0, "y": -2.50, "z": -4.0, "rot_y": 180.0},
        "datacards": {"x": 2.0, "y": -2.50, "z": -4.0, "rot_y": 180.0},
        # Card decks - Row 2 (z = -7.40)
        "strategy-ploys": {"x": -4.0, "y": -2.50, "z": -7.40, "rot_y": 180.0},
        "firefight-ploys": {"x": -2.0, "y": -2.50, "z": -7.40, "rot_y": 180.0},
        "equipment": {"x": 0.0, "y": -2.50, "z": -7.40, "rot_y": 180.0},
        "markertokens": {"x": 2.0, "y": -2.50, "z": -7.40, "rot_y": 180.0},
        # Optional token bag (added by token pipeline)
        "tokens":     {"x": 4.0,  "y": -2.50, "z": -8.0,  "rot_y": 270.0, "rot_x": 0.0169, "rot_z": 0.0799},
        # Dice: dark + light stacked vertically (always present), team to the right (optional)
        #    L
        # B  D  T
        # rot_x=270 puts face 6 on top; rot_x/rot_z chosen so they sit flat (no card tilt)
        "dice-dark":  {"x": 6.0,  "y": -2.50, "z": -8.0,  "rot_y": 0.0,   "rot_x": 270.0, "rot_z": 0.0},
        "dice-team":  {"x": 7.5,  "y": -2.50, "z": -8.0,  "rot_y": 0.0,   "rot_x": 270.0, "rot_z": 0.0},
        "dice-light": {"x": 6.0,  "y": -2.50, "z": -6.5,  "rot_y": 0.0,   "rot_x": 270.0, "rot_z": 0.0},
    }

    nickname_to_type = {
        "operative selection": "operative-selection",
        "faction rules": "faction-rules",
        "markertokens": "markertokens",
        "marker tokens": "markertokens",
        "datacards": "datacards",
        "equipment": "equipment",
        "firefight ploys": "firefight-ploys",
        "strategy ploys": "strategy-ploys",
    }

    def _infer_type_from_face_url(face_url: str) -> Optional[str]:
        if not face_url:
            return None
        
        # Support v2, v3 and current output structures
        if "/output_v2/" in face_url:
            after = face_url.split("/output_v2/", 1)[1]
            # URL format: .../output_v2/{faction}/{team}/{card_type}/...
            parts = after.split("/")
            if len(parts) < 3:
                return None
            folder = parts[2].strip().lower()
        elif "/output_v3/" in face_url:
            after = face_url.split("/output_v3/", 1)[1]
            # URL format: .../output_v3/{team}/cards/{card_type}/...
            parts = after.split("/")
            if len(parts) < 3:
                return None
            folder = parts[2].strip().lower()
        elif "/output/" in face_url:
            after = face_url.split("/output/", 1)[1]
            # URL format: .../output/{team}/cards/{card_type}/...
            parts = after.split("/")
            if len(parts) < 3:
                return None
            folder = parts[2].strip().lower()
        else:
            return None

        # Normalize folder names to card types
        if folder in {"operative-selection", "operatives", "operatives_selection"}:
            return "operative-selection"
        if folder in {"token-guide", "token_guide", "markertoken-guide"}:
            return "markertokens"
        if folder in {"datacards", "equipment", "firefight-ploys", "strategy-ploys"}:
            return folder
        if folder == "firefight_ploys":
            return "firefight-ploys"
        if folder == "strategy_ploys":
            return "strategy-ploys"

        if folder == "faction-rules" or folder == "faction_rules":
            # Markertokens are stored under faction-rules, but should have their own slot.
            # Detect by URL content.
            if "markertoken" in face_url.lower() or "token-guide" in face_url.lower():
                return "markertokens"
            return "faction-rules"

        return None

    def _infer_object_type(obj: dict):
        name = str(obj.get("Name") or "").strip()
        nickname = str(obj.get("Nickname") or "").strip()
        nickname_norm = " ".join(nickname.lower().replace("_", " ").replace("-", " ").split())

        if name == "Custom_Model_Bag" and "tokens" in nickname_norm:
            return "tokens"

        if name == "Custom_Dice":
            if "dark" in nickname_norm:
                return "dice-dark"
            if "light" in nickname_norm:
                return "dice-light"
            return "dice-team"

        by_nickname = nickname_to_type.get(nickname_norm)
        if by_nickname:
            return by_nickname

        # Fallback: infer from card art URLs so single-card objects still get a stable slot.
        custom_deck = obj.get("CustomDeck")
        if isinstance(custom_deck, dict):
            for entry in custom_deck.values():
                if not isinstance(entry, dict):
                    continue
                face_url = str(entry.get("FaceURL") or "")
                inferred = _infer_type_from_face_url(face_url)
                if inferred == "faction-rules" and "markertoken" in nickname_norm:
                    inferred = "markertokens"
                if inferred:
                    return inferred

        return None

    for obj in contained_objects:
        obj_type = _infer_object_type(obj)
        if not obj_type:
            continue

        pos = position_by_type.get(obj_type)
        if not pos:
            continue

        guid = obj.get("GUID")
        if not guid:
            continue

        memory_list[guid] = {
            "lock": False,
            "pos": {"x": pos["x"], "y": pos["y"], "z": pos["z"]},
            "rot": {"x": pos.get("rot_x", 0.0169), "y": pos["rot_y"], "z": pos.get("rot_z", 0.0799)},
        }

    # Include creation timestamp in state if provided
    state_data = {"ml": memory_list, "rr": 270, "teamSlug": team_folder_name}
    if last_modified:
        state_data["lastCardUpdate"] = last_modified
    if last_token_modified:
        state_data["lastTokenUpdate"] = last_token_modified
    lua_script_state = json.dumps(state_data)

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
                "GUID": get_team_guid(team_name),
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
                    "ColliderURL": mesh_url,
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
