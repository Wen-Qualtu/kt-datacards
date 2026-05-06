"""
Step 7: Generate TTS Objects

Generates Tabletop Simulator (TTS) JSON save files from classified cards.

Prerequisites:
    Step 6: TTS assets (mesh/texture) must be generated

Input:
    layers/kt-app/classified/{team}/structure.json - Card organization
    output_v3/{team}/cards/{card_type}/*.png - Card images
    output_v3/{team}/cardbox/*.obj/*.jpg - 3D assets from step 6
    output_v3/{team}/tokens/ - Token files
    config/team-config.yaml - Team metadata
    
Output:
    output_v3/{team}/tts_object/{Team Name} Cards.json - TTS card box save file
    output_v3/{team}/tts_object/{Team Name} Cards.png - Preview image
"""

import argparse
import json
import logging
import re
import shutil
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
import sys

# Add templates to path
sys.path.insert(0, str(Path(__file__).parent))
from templates.tts_templates import (
    create_single_card, create_deck, create_bag,
    generate_guid
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def generate_urls_json_v3():
    """Generate flat list format for internal use (backwards compatibility)"""
    output_v3 = PROJECT_ROOT / 'output_v3'
    branch = "refactor-kt-app-pipeline"
    base_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{branch}/output_v3"
    
    all_entries = []
    
    # Scan all team directories (flat structure in v3)
    for team_dir in sorted(output_v3.iterdir()):
        if not team_dir.is_dir():
            continue
        
        team = team_dir.name
        cards_dir = team_dir / 'cards'
        cardbox_dir = team_dir / 'cardbox'
        
        if not cards_dir.exists():
            continue
        
        # Add cardbox assets (mesh and texture)
        if cardbox_dir.exists():
            for asset_file in cardbox_dir.glob('*'):
                if asset_file.suffix in ['.obj', '.jpg']:
                    asset_url = f"{base_url}/{team}/cardbox/{asset_file.name}"
                    all_entries.append({
                        'team': team,
                        'type': 'tts',
                        'name': asset_file.stem,
                        'url': asset_url
                    })
        
        # Scan card types
        for card_type_dir in sorted(cards_dir.iterdir()):
            if not card_type_dir.is_dir():
                continue
            
            card_type = card_type_dir.name
            
            # Convert v3 naming (underscores) to v2 naming (dashes)
            type_mappings = {
                'operatives_selection': 'operative-selection',
                'faction_rules': 'faction-rules',
                'firefight_ploys': 'firefight-ploys',
                'strategy_ploys': 'strategy-ploys',
                'token_guide': 'token-guide'
            }
            card_type_v2 = type_mappings.get(card_type, card_type.replace('_', '-'))
            
            # Regular card type
            for card_file in sorted(card_type_dir.glob('*.png')):
                # Convert filename format from "{team}-{card}-front.png" to "{team}-{card}_front"
                name = card_file.stem
                if name.endswith('-front') or name.endswith('-back'):
                    name = name.rsplit('-', 1)
                    name = f"{name[0]}_{name[1]}"
                
                card_url = f"{base_url}/{team}/cards/{card_type}/{card_file.name}"
                all_entries.append({
                    'team': team,
                    'type': card_type_v2,
                    'name': name,
                    'url': card_url
                })
    
    return all_entries


def generate_object_urls_json():
    """
    Generate object-urls.json for TTS update checks.
    
    Structure: Keyed by team for efficient lookup in TTS Lua scripts.
    Each team has:
    - box: The TTS save JSON file with modified timestamp
    - objects: Array of all assets (cards, cardbox, tokens, lua script) with URLs and timestamps
    """
    output_v3 = PROJECT_ROOT / 'output_v3'
    config_dir = PROJECT_ROOT / 'config'
    branch = "refactor-kt-app-pipeline"
    base_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{branch}/output_v3"
    
    teams_data = {}
    
    # Scan all team directories
    for team_dir in sorted(output_v3.iterdir()):
        if not team_dir.is_dir():
            continue
        
        team = team_dir.name
        team_display_name = team.replace('-', ' ').title()
        
        # Initialize team entry
        team_entry = {
            "team": team,
            "box": None,
            "objects": []
        }
        
        # Add TTS box JSON file
        tts_object_dir = team_dir / 'tts_object'
        box_file = tts_object_dir / f"{team_display_name} Cards.json"
        if box_file.exists():
            box_mtime = box_file.stat().st_mtime
            box_modified = datetime.fromtimestamp(box_mtime, tz=timezone.utc).isoformat()
            box_url = f"{base_url}/{team}/tts_object/{box_file.name.replace(' ', '%20')}"
            team_entry["box"] = {
                "url": f"{box_url}?v={int(box_mtime)}",
                "modified": box_modified
            }
        
        # Add Lua script
        lua_script_path = config_dir / "defaults" / "tts-script" / "tts-update-rules-in-box-script.lua"
        if lua_script_path.exists():
            lua_mtime = lua_script_path.stat().st_mtime
            lua_modified = datetime.fromtimestamp(lua_mtime, tz=timezone.utc).isoformat()
            lua_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{branch}/config/defaults/tts-script/tts-update-rules-in-box-script.lua"
            team_entry["objects"].append({
                "type": "lua-script",
                "name": "update-script",
                "url": f"{lua_url}?v={int(lua_mtime)}",
                "modified": lua_modified
            })
        
        # Add cardbox assets (mesh and texture)
        cardbox_dir = team_dir / 'cardbox'
        if cardbox_dir.exists():
            for asset_file in sorted(cardbox_dir.glob('*')):
                if asset_file.suffix == '.obj':
                    obj_type = 'cardbox-mesh'
                elif asset_file.suffix == '.jpg':
                    obj_type = 'cardbox-texture'
                else:
                    continue
                
                mtime = asset_file.stat().st_mtime
                modified = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
                asset_url = f"{base_url}/{team}/cardbox/{asset_file.name}"
                
                team_entry["objects"].append({
                    "type": obj_type,
                    "name": asset_file.stem,
                    "url": f"{asset_url}?v={int(mtime)}",
                    "modified": modified
                })
        
        # Add tokens
        tokens_dir = team_dir / 'tokens'
        if tokens_dir.exists():
            for token_obj in sorted(tokens_dir.glob('*.obj')):
                token_png = token_obj.with_suffix('.png')
                if not token_png.exists():
                    continue
                
                obj_mtime = token_obj.stat().st_mtime
                png_mtime = token_png.stat().st_mtime
                max_mtime = max(obj_mtime, png_mtime)
                modified = datetime.fromtimestamp(max_mtime, tz=timezone.utc).isoformat()
                
                obj_url = f"{base_url}/{team}/tokens/{token_obj.name}"
                png_url = f"{base_url}/{team}/tokens/{token_png.name}"
                
                team_entry["objects"].append({
                    "type": "token",
                    "name": token_obj.stem,
                    "mesh_url": f"{obj_url}?v={int(obj_mtime)}",
                    "texture_url": f"{png_url}?v={int(png_mtime)}",
                    "modified": modified
                })
            
            # Add token bag mesh and icon
            tokenbag_dir = tokens_dir / 'tokenbag'
            if tokenbag_dir.exists():
                bag_mesh = tokenbag_dir / f'{team}-token-bag.obj'
                bag_icon = tokenbag_dir / f'{team}-token-bag-icon.png'
                
                if bag_mesh.exists() and bag_icon.exists():
                    mesh_mtime = bag_mesh.stat().st_mtime
                    icon_mtime = bag_icon.stat().st_mtime
                    max_mtime = max(mesh_mtime, icon_mtime)
                    modified = datetime.fromtimestamp(max_mtime, tz=timezone.utc).isoformat()
                    
                    mesh_url = f"{base_url}/{team}/tokens/tokenbag/{bag_mesh.name}"
                    icon_url = f"{base_url}/{team}/tokens/tokenbag/{bag_icon.name}"
                    
                    team_entry["objects"].append({
                        "type": "token-bag",
                        "name": f"{team}-token-bag",
                        "mesh_url": f"{mesh_url}?v={int(mesh_mtime)}",
                        "icon_url": f"{icon_url}?v={int(icon_mtime)}",
                        "modified": modified
                    })
        
        # Add card images
        cards_dir = team_dir / 'cards'
        if cards_dir.exists():
            for card_type_dir in sorted(cards_dir.iterdir()):
                if not card_type_dir.is_dir():
                    continue
                
                card_type = card_type_dir.name
                
                # Group front/back pairs
                card_pairs = {}
                for card_file in card_type_dir.glob('*.png'):
                    name = card_file.stem
                    if name.endswith('-front'):
                        base_name = name[:-6]
                        if base_name not in card_pairs:
                            card_pairs[base_name] = {}
                        card_pairs[base_name]['front'] = card_file
                    elif name.endswith('-back'):
                        base_name = name[:-5]
                        if base_name not in card_pairs:
                            card_pairs[base_name] = {}
                        card_pairs[base_name]['back'] = card_file
                
                # Add paired cards
                for base_name, files in sorted(card_pairs.items()):
                    front_file = files.get('front')
                    back_file = files.get('back')
                    
                    if not front_file:
                        continue
                    
                    front_mtime = front_file.stat().st_mtime
                    back_mtime = back_file.stat().st_mtime if back_file else front_mtime
                    max_mtime = max(front_mtime, back_mtime)
                    modified = datetime.fromtimestamp(max_mtime, tz=timezone.utc).isoformat()
                    
                    front_url = f"{base_url}/{team}/cards/{card_type}/{front_file.name}"
                    back_url = f"{base_url}/{team}/cards/{card_type}/{back_file.name}" if back_file else front_url
                    
                    team_entry["objects"].append({
                        "type": card_type,
                        "name": base_name,
                        "face_url": f"{front_url}?v={int(front_mtime)}",
                        "back_url": f"{back_url}?v={int(back_mtime)}",
                        "modified": modified
                    })
        
        # Add team to result if it has a box
        if team_entry["box"]:
            teams_data[team] = team_entry
    
    return teams_data


def load_lua_script(config_dir: Path) -> str:
    """Load the Lua script from config defaults folder"""
    script_path = config_dir / "defaults" / "tts-script" / "tts-update-rules-in-box-script.lua"
    try:
        with open(script_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            if content.startswith('\ufeff'):
                content = content[1:]
            content = content.replace('\n', '\r\n')
            return content
    except Exception as e:
        logger.warning(f"Could not load Lua script: {e}")
        return ""


def load_token_bag(team_name: str, faction: str, sample_url: str, config_dir: Path, output_v3_dir: Path) -> tuple:
    """
    Generate token bag from output_v3/{team}/tokens/ files.
    
    Returns:
        Tuple of (token bag object dict, token timestamp) or (None, None) if no tokens exist
    """
    tokens_dir = output_v3_dir / team_name / 'tokens'
    
    if not tokens_dir.exists():
        return None, None
    
    # Find all token .obj files (excluding tokenbag folder)
    token_files = []
    for obj_file in tokens_dir.glob('*.obj'):
        png_file = obj_file.with_suffix('.png')
        if png_file.exists():
            token_files.append((obj_file.stem, obj_file, png_file))
    
    if not token_files:
        return None, None
    
    # Check for token bag mesh and icon
    tokenbag_dir = tokens_dir / 'tokenbag'
    bag_mesh_file = tokenbag_dir / f'{team_name}-token-bag.obj'
    bag_icon_file = tokenbag_dir / f'{team_name}-token-bag-icon.png'
    
    if not bag_mesh_file.exists() or not bag_icon_file.exists():
        logger.warning(f"Token bag mesh or icon not found for {team_name}")
        return None, None
    
    # Extract github base URL from sample card URL
    github_base = ""
    if sample_url and '/output_v3/' in sample_url:
        github_base = sample_url.split('/output_v3/')[0]
    elif sample_url and '/output_v2/' in sample_url:
        github_base = sample_url.split('/output_v2/')[0]
    
    if not github_base:
        logger.warning(f"Could not extract github base URL, using placeholder")
        github_base = "https://github.com/user/repo/raw/main"
    
    # Generate token objects
    token_objects = []
    for token_name, obj_path, png_path in sorted(token_files):
        display_name = token_name.replace(f'{team_name}-', '').replace('-', ' ').title()
        
        mesh_url = f"{github_base}/output_v3/{team_name}/tokens/{obj_path.name}"
        diffuse_url = f"{github_base}/output_v3/{team_name}/tokens/{png_path.name}"
        
        token_obj = {
            "GUID": generate_guid(f"{team_name}:token:{token_name}"),
            "Name": "Custom_Model",
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
            "Nickname": display_name,
            "Description": "",
            "GMNotes": "",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
            "Tags": [f"KTCards{team_name.replace('-', '')}"],
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
            "CustomMesh": {
                "MeshURL": mesh_url,
                "DiffuseURL": diffuse_url,
                "NormalURL": "",
                "ColliderURL": "",
                "Convex": True,
                "MaterialIndex": 3,
                "TypeIndex": 0,
                "CastShadows": True
            },
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        }
        token_objects.append(token_obj)
    
    # Build token bag mesh and icon URLs
    bag_mesh_url = f"{github_base}/output_v3/{team_name}/tokens/tokenbag/{bag_mesh_file.name}"
    bag_icon_url = f"{github_base}/output_v3/{team_name}/tokens/tokenbag/{bag_icon_file.name}"
    
    # Create token bag
    token_timestamp = datetime.now(timezone.utc).isoformat()
    
    # Load token bag Lua script
    lua_script_path = config_dir / 'defaults' / 'tts-token' / 'token-bag-script.lua'
    lua_script = ""
    if lua_script_path.exists():
        with open(lua_script_path, 'r', encoding='utf-8') as f:
            lua_script = f.read()
    
    token_bag = {
        "GUID": generate_guid(f"{team_name}:tokenbag"),
        "Name": "Bag",
        "Transform": {
            "posX": 0.0,
            "posY": 3.0,
            "posZ": 0.0,
            "rotX": 0.0,
            "rotY": 180.0,
            "rotZ": 0.0,
            "scaleX": 0.6,
            "scaleY": 0.6,
            "scaleZ": 0.6
        },
        "Nickname": f"{team_name.replace('-', ' ').title()} Tokens",
        "Description": "",
        "GMNotes": "",
        "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
        "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
        "Tags": [f"KTCards{team_name.replace('-', '')}"],
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
        "Bag": {
            "Order": 0
        },
        "LuaScript": lua_script,
        "LuaScriptState": json.dumps({"lastUpdate": token_timestamp}),
        "XmlUI": "",
        "ContainedObjects": token_objects,
        "CustomMesh": {
            "MeshURL": bag_mesh_url,
            "DiffuseURL": bag_icon_url,
            "NormalURL": "",
            "ColliderURL": "",
            "Convex": True,
            "MaterialIndex": 3,
            "TypeIndex": 6,
            "CastShadows": True
        }
    }
    
    logger.info(f"Generated token bag for {team_name} with {len(token_objects)} tokens from output_v3")
    return token_bag, token_timestamp


def copy_preview_image(team_folder_name: str, team_display_name: str, config_dir: Path, output_dir: Path):
    """Copy preview/icon image for a team"""
    team_icon = config_dir / "teams" / team_folder_name / "tts-image" / f"{team_folder_name}-icon.png"
    team_preview = config_dir / "teams" / team_folder_name / "tts-image" / f"{team_folder_name}-preview.png"
    default_icon = config_dir / "defaults" / "tts-image" / "default-icon.png"
    default_preview = config_dir / "defaults" / "tts-image" / "default-preview.png"
    
    # Priority: team icon > team preview > default icon > default preview
    if team_icon.exists():
        source_preview = team_icon
    elif team_preview.exists():
        source_preview = team_preview
    elif default_icon.exists():
        source_preview = default_icon
    else:
        source_preview = default_preview
    
    if source_preview.exists():
        team_output_dir = output_dir / team_folder_name / 'tts_object'
        team_output_dir.mkdir(parents=True, exist_ok=True)
        dest_preview = team_output_dir / f"{team_display_name} Cards.png"
        shutil.copy2(source_preview, dest_preview)
    else:
        logger.warning(f"No preview/icon image found for {team_folder_name}")


def generate_team_tts_object(team_name: str, cards: list, lua_script: str, texture_url: str, 
                            mesh_url: str, config_dir: Path, output_dir: Path):
    """Generate TTS object for a single team"""
    # Extract faction from first card's URL
    faction = None
    if cards:
        first_url = cards[0].get('url', '')
        if '/output_v3/' in first_url:
            parts = first_url.split('/output_v3/')[1].split('/')
            if len(parts) > 0:
                faction = parts[0]
    
    # Group cards by type
    cards_by_type = defaultdict(list)
    for card in cards:
        cards_by_type[card['type']].append(card)
    
    # Extract markertoken cards from faction-rules
    if 'faction-rules' in cards_by_type:
        markertoken_cards = [c for c in cards_by_type['faction-rules'] if 'markertoken' in c['name'].lower()]
        faction_rules_cards = [c for c in cards_by_type['faction-rules'] if 'markertoken' not in c['name'].lower()]
        
        if markertoken_cards:
            cards_by_type['markertokens'] = markertoken_cards
        cards_by_type['faction-rules'] = faction_rules_cards
    
    # Build contained objects
    contained_objects = []
    deck_id_counter = 1000
    type_order = ['operative-selection', 'faction-rules', 'token-guide', 'markertokens', 'datacards', 'equipment', 'firefight-ploys', 'strategy-ploys']
    
    # Add token bag if tokens exist for this team
    sample_url = cards[0]['url'] if cards else None
    token_bag, token_timestamp = load_token_bag(team_name, faction, sample_url, config_dir, output_dir)
    if token_bag:
        contained_objects.append(token_bag)
        logger.info(f"Added token bag for {team_name}")
    
    for card_type in type_order:
        if card_type not in cards_by_type:
            continue
        
        type_cards = cards_by_type[card_type]
        
        # Group cards by base name (without _front/_back suffix)
        card_groups = defaultdict(lambda: {'front': None, 'back': None})
        
        for card in type_cards:
            name = card['name']
            url = card['url']
            
            if name.endswith('_front'):
                base_name = name[:-6]
                card_groups[base_name]['front'] = url
            elif name.endswith('_back'):
                base_name = name[:-5]
                card_groups[base_name]['back'] = url
        
        # Prepare cards data
        type_cards_data = []
        for card_name, urls in sorted(card_groups.items()):
            front_url = urls['front']
            back_url = urls['back'] or front_url
            
            if not front_url:
                continue
            
            type_cards_data.append({
                'name': card_name,
                'front': front_url,
                'back': back_url
            })
        
        # Create deck or single card
        team_tag = f"_{team_name.replace('-', '_').title().replace('_', ' ')}"
        
        if len(type_cards_data) == 1:
            card_data = type_cards_data[0]
            
            # Transform card name to match production format
            card_name = card_data['name']
            if card_type == 'operative-selection':
                card_name = f"{team_name}-operatives"
            elif card_type == 'token-guide':
                card_name = f"{team_name}-markertoken-guide"
            
            card_obj = create_single_card(
                card_name,
                card_data['front'],
                card_data['back'],
                team_tag,
                str(deck_id_counter),
                card_type
            )
            contained_objects.append(card_obj)
            deck_id_counter += 1
        elif len(type_cards_data) > 1:
            type_nickname = card_type.replace('-', ' ').title()
            deck_obj = create_deck(type_nickname, team_tag, type_cards_data, deck_id_counter, card_type)
            contained_objects.append(deck_obj)
            deck_id_counter += len(type_cards_data)
    
    # Create the bag
    team_display_name = team_name.replace('-', ' ').title()
    team_tag = f"_{team_name.replace('-', '_').title().replace('_', ' ')}"
    
    # Get output file path
    team_output_dir = output_dir / team_name / 'tts_object'
    team_output_dir.mkdir(parents=True, exist_ok=True)
    output_file = team_output_dir / f"{team_display_name} Cards.json"
    
    # Create bag with placeholder timestamp
    import os
    placeholder_timestamp = "2000-01-01T00:00:00"
    placeholder_token_timestamp = ""
    
    bag_obj = create_bag(team_display_name, team_tag, contained_objects, lua_script, texture_url, mesh_url, faction, placeholder_timestamp, placeholder_token_timestamp)
    
    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(bag_obj, f, indent=2)
    
    # Get actual file timestamp and update URLs
    file_mtime = os.path.getmtime(output_file)
    actual_timestamp = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%dT%H:%M:%S')
    cache_bust_param = f"?v={int(file_mtime)}"
    
    # Update all URLs with cache-busting parameter
    def update_urls_in_object(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in ['FaceURL', 'BackURL', 'ImageURL', 'MeshURL'] and isinstance(value, str):
                    obj[key] = re.sub(r'\?v=\d+', cache_bust_param, value)
                    if '?v=' not in obj[key]:
                        obj[key] += cache_bust_param
                else:
                    update_urls_in_object(value)
        elif isinstance(obj, list):
            for item in obj:
                update_urls_in_object(item)
    
    update_urls_in_object(bag_obj)
    
    # Recreate bag with actual timestamp
    bag_obj = create_bag(team_display_name, team_tag, contained_objects, lua_script, texture_url, mesh_url, faction, actual_timestamp, token_timestamp or "")
    
    # Apply URL updates again
    update_urls_in_object(bag_obj)
    
    # Save final version
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(bag_obj, f, indent=2)
    
    # Copy preview image
    copy_preview_image(team_name, team_display_name, config_dir, output_dir)


def generate_all_tts_objects(urls_data: list, config_dir: Path, output_dir: Path, team_filter: list = None) -> int:
    """Generate TTS objects for all teams"""
    # Load Lua script
    lua_script = load_lua_script(config_dir)
    
    # Group cards by team and separate box assets
    teams = defaultdict(list)
    team_textures = {}
    team_meshes = {}
    
    for card in urls_data:
        team_key = card['team']
        if card['type'] == 'tts':
            if 'card-box-texture' in card['name']:
                team_textures[team_key] = card['url']
            elif 'card-box' in card['name'] and card['url'].endswith('.obj'):
                team_meshes[team_key] = card['url']
        else:
            teams[team_key].append(card)
    
    # Generate TTS object for each team
    count = 0
    skipped = 0
    
    for team_name, cards in teams.items():
        # Skip if team filter is active and this team is not in the filter
        if team_filter and team_name not in team_filter:
            logger.debug(f"Skipping {team_name} (not in team filter)")
            skipped += 1
            continue
            
        logger.info(f"Generating TTS object for {team_name}")
        texture_url = team_textures.get(team_name)
        mesh_url = team_meshes.get(team_name)
        
        generate_team_tts_object(team_name, cards, lua_script, texture_url, mesh_url, config_dir, output_dir)
        count += 1
    
    if skipped > 0:
        logger.info(f"Skipped {skipped} team(s) (no changes or filtered out)")
    
    return count


def main():
    parser = argparse.ArgumentParser(description='Generate TTS objects from classified cards')
    parser.add_argument('--teams', nargs='+', help='Specific teams to process (default: all)')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: INFO)')
    
    args = parser.parse_args()
    
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    logger.info("=" * 60)
    logger.info("TTS Object Generation - KT-App Pipeline")
    logger.info("=" * 60)
    
    # Generate URLs JSON from v3 structure (flat format for internal use)
    logger.info("Scanning output_v3 structure...")
    urls_data = generate_urls_json_v3()
    logger.info(f"Found {len(urls_data)} card/asset entries")
    
    # Generate object-urls.json for TTS update checks
    logger.info("Generating object-urls.json for TTS update checks...")
    object_urls_data = generate_object_urls_json()
    object_urls_file = PROJECT_ROOT / 'output_v3' / 'object-urls.json'
    with open(object_urls_file, 'w', encoding='utf-8') as f:
        json.dump(object_urls_data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved object-urls.json with {len(object_urls_data)} teams")
    
    # Generate TTS objects
    config_dir = PROJECT_ROOT / 'config'
    output_dir = PROJECT_ROOT / 'output_v3'
    count = generate_all_tts_objects(urls_data, config_dir, output_dir, args.teams)
    
    logger.info("=" * 60)
    logger.info("Generation Complete")
    logger.info("=" * 60)
    logger.info(f"Teams processed: {count}")
    logger.info(f"Output: {PROJECT_ROOT / 'output_v3' / '{team}' / 'tts_object'}")


if __name__ == '__main__':
    main()
