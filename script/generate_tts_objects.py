"""
Generate Tabletop Simulator saved object files from datacards-urls.json

This script creates TTS Custom_Model_Bag objects containing cards organized by type.
Each type (datacards, equipment, etc.) becomes a separate deck or card.
"""

import json
from pathlib import Path
from collections import defaultdict
import random

def generate_guid():
    """Generate a 6-character hex GUID like TTS uses"""
    return ''.join(random.choices('0123456789abcdef', k=6))

def load_lua_script():
    """Load the Lua script from the docs folder"""
    script_path = Path(__file__).parent.parent / "docs" / "tts-update-rules-in-box-script.lua"
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Convert to Windows line endings for TTS
        content = content.replace('\n', '\r\n')
        return content

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

def create_bag(team_name, team_tag, contained_objects, lua_script):
    """Create a TTS Custom_Model_Bag containing decks and cards"""
    
    # Get team name from tag (remove leading underscore and convert to lowercase with hyphens)
    team_folder_name = team_tag.strip('_').lower().replace(' ', '-')
    
    # Check for team-specific box files first, then fall back to default
    config_dir = Path(__file__).parent.parent / "config"
    team_box_dir = config_dir / "box" / "team" / team_folder_name
    default_box_dir = config_dir / "box" / "default"
    
    # Check if team-specific box exists
    team_mesh = team_box_dir / "card-box.obj"
    team_texture = team_box_dir / "card-box-texture.jpg"
    
    if team_mesh.exists() and team_texture.exists():
        mesh_path = team_mesh.resolve()
        texture_path = team_texture.resolve()
    else:
        # Fall back to default
        mesh_path = (default_box_dir / "card-box.obj").resolve()
        texture_path = (default_box_dir / "card-box-texture.jpg").resolve()
    
    # Convert to file:// URLs for TTS
    mesh_url = mesh_path.as_uri()
    texture_url = texture_path.as_uri()
    
    # Create LuaScriptState with positions for each contained object
    # This allows the buttons to show up immediately
    # Layout: Top row: Faction Rules, Operative Selection, Datacards (wider)
    #         Bottom row: Strategy Ploys, Firefight Ploys, Equipment, Markertokens
    memory_list = {}
    
    # The order contained_objects are added: operative-selection(0), faction-rules(1), markertokens(2), datacards(3), equipment(4), firefight-ploys(5), strategy-ploys(6)
    # Position mapping based on user's manual placement, aligned precisely
    # Top row: Faction Rules, Operative Selection, Datacards (wide)
    # Bottom row: Strategy Ploys, Firefight Ploys, Equipment, Markertokens
    position_map = {
        0: {"x": -1.01, "y": -2.486, "z": -4.1},     # Operative Selection - top middle (single card)
        1: {"x": -3.02, "y": -2.486, "z": -4.1},     # Faction Rules - top left (single card)
        2: {"x": 3.0, "y": -2.486, "z": -7.39},      # Markertokens - bottom far right (single card)
        3: {"x": 3.01, "y": -2.426, "z": -4.08},     # Datacards - top right (deck, thicker)
        4: {"x": 1.05, "y": -2.46, "z": -7.39},      # Equipment - bottom middle-right (deck)
        5: {"x": -0.96, "y": -2.46, "z": -7.38},     # Firefight Ploys - bottom middle (deck)
        6: {"x": -2.94, "y": -2.46, "z": -7.39},     # Strategy Ploys - bottom left (deck)
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

def main():
    # Read the datacards-urls.json file (V2 structure)
    urls_file = Path(__file__).parent.parent / "output_v2" / "datacards-urls.json"
    
    if not urls_file.exists():
        print(f"Error: {urls_file} not found!")
        return
    
    with open(urls_file, 'r', encoding='utf-8') as f:
        all_cards = json.load(f)
    
    # Load the Lua script
    try:
        lua_script = load_lua_script()
        print(f"Loaded Lua script ({len(lua_script)} characters)")
    except Exception as e:
        print(f"Warning: Could not load Lua script: {e}")
        lua_script = ""
    
    # Group cards by team
    teams = defaultdict(list)
    for card in all_cards:
        teams[card['team']].append(card)
    
    # Create output directory for TTS objects
    output_dir = Path(__file__).parent.parent / "tts_objects"
    output_dir.mkdir(exist_ok=True)
    
    # Process each team
    for team_name, cards in teams.items():
        print(f"\nProcessing {team_name}...")
        
        # Group cards by type first
        cards_by_type = defaultdict(list)
        for card in cards:
            cards_by_type[card['type']].append(card)
        
        # For each type, group by base name (without _front/_back suffix)
        contained_objects = []
        deck_id_counter = 1000
        
        # Define the order of card types (like in the example)
        # Note: markertokens will be extracted from faction-rules
        type_order = ['operative-selection', 'faction-rules', 'markertokens', 'datacards', 'equipment', 'firefight-ploys', 'strategy-ploys']
        
        # Extract markertoken cards from faction-rules
        if 'faction-rules' in cards_by_type:
            markertoken_cards = [c for c in cards_by_type['faction-rules'] if 'markertoken' in c['name'].lower()]
            faction_rules_cards = [c for c in cards_by_type['faction-rules'] if 'markertoken' not in c['name'].lower()]
            
            if markertoken_cards:
                cards_by_type['markertokens'] = markertoken_cards
            cards_by_type['faction-rules'] = faction_rules_cards
        
        for card_type in type_order:
            if card_type not in cards_by_type:
                continue
                
            type_cards = cards_by_type[card_type]
            
            # Group cards by base name (without _front/_back suffix)
            card_groups = defaultdict(lambda: {'front': None, 'back': None})
            
            for card in type_cards:
                name = card['name']
                url = card['url']
                
                # Determine if this is a front or back
                if name.endswith('_front'):
                    base_name = name[:-6]  # Remove '_front'
                    card_groups[base_name]['front'] = url
                elif name.endswith('_back'):
                    base_name = name[:-5]  # Remove '_back'
                    card_groups[base_name]['back'] = url
            
            # Prepare cards data for this type
            type_cards_data = []
            for card_name, urls in sorted(card_groups.items()):
                front_url = urls['front']
                back_url = urls['back']
                
                # Skip if we don't have at least a front URL
                if not front_url:
                    print(f"  Warning: No front URL for {card_name}, skipping")
                    continue
                
                # Use a default back if none provided
                if not back_url:
                    back_url = front_url
                    print(f"  Warning: No back URL for {card_name}, using front URL")
                
                type_cards_data.append({
                    'name': card_name,
                    'front': front_url,
                    'back': back_url
                })
            
            # Create team tag
            team_tag = f"_{team_name.replace('-', '_').title().replace('_', ' ')}"
            
            # Create either a single card or a deck depending on count
            if len(type_cards_data) == 1:
                # Single card
                card_data = type_cards_data[0]
                deck_id = str(deck_id_counter)
                card_obj = create_single_card(
                    card_data['name'],
                    card_data['front'],
                    card_data['back'],
                    team_tag,
                    deck_id
                )
                contained_objects.append(card_obj)
                print(f"  Added single card for {card_type}: {card_data['name']}")
                deck_id_counter += 1
            elif len(type_cards_data) > 1:
                # Create a deck
                type_nickname = card_type.replace('-', ' ').title()
                deck_obj = create_deck(type_nickname, team_tag, type_cards_data, deck_id_counter)
                contained_objects.append(deck_obj)
                print(f"  Added deck for {card_type}: {len(type_cards_data)} cards")
                deck_id_counter += len(type_cards_data)
        
        # Create the bag containing all decks and cards
        team_display_name = team_name.replace('-', ' ').title()
        team_tag = f"_{team_name.replace('-', '_').title().replace('_', ' ')}"
        bag_obj = create_bag(team_display_name, team_tag, contained_objects, lua_script)
        
        # Save to file with format "{Teamname} Cards.json"
        output_file = output_dir / f"{team_display_name} Cards.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(bag_obj, f, indent=2)
        
        total_cards = sum(len(cards_by_type[t]) for t in cards_by_type)
        print(f"  ✓ Created {output_file}")
        print(f"    Total: {len(contained_objects)} decks/cards containing {total_cards // 2} unique cards")
    
    print(f"\n✓ Done! TTS objects saved to {output_dir}")
    print(f"✓ Total teams processed: {len(teams)}")
    print("\nTo use in TTS:")
    print("1. Open Tabletop Simulator")
    print("2. Go to Objects -> Saved Objects -> Import")
    print("3. Select the JSON file for your team")
    print("4. The bag will spawn with all cards organized by type")

if __name__ == "__main__":
    main()
