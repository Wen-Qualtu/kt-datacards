"""
Step 7: Generate TTS Objects (with embedded stats)

Generates Tabletop Simulator (TTS) JSON save files from classified cards.
Embeds operative stats (GMNotes + Lua scripts) directly during generation.

Prerequisites:
    Step 3: Team data extracted (for stat embedding)
    Step 6: TTS assets (mesh/texture) generated

Input:
    layers/kt-app/classified/{team}/structure.json - Card organization
    output_v3/{team}/cards/{card_type}/*.png - Card images
    output_v3/{team}/cardbox/*.obj/*.jpg - 3D assets from step 6
    output_v3/{team}/tokens/ - Token files
    output_v3/{team}/data/{team}-team-data.json - Operative stats (optional)
    config/team-config.yaml - Team metadata
    
Output:
    output_v3/{team}/tts_objects/{Team Name} Box.json - TTS card box save file with embedded stats
    output_v3/{team}/tts_objects/{Team Name} Box.png - Preview image
"""

import argparse
import json
import logging
import re
import shutil
import yaml
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
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
        tts_objects_dir = team_dir / 'tts_objects'
        box_file = tts_objects_dir / f"{team_display_name} Box.json"
        if box_file.exists():
            box_mtime = box_file.stat().st_mtime
            box_modified = datetime.fromtimestamp(box_mtime, tz=timezone.utc).isoformat()
            box_url = f"{base_url}/{team}/tts_objects/{box_file.name.replace(' ', '%20')}"
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
    
    # Save individual token JSONs
    for idx, token_obj in enumerate(token_objects, start=1):
        save_individual_token_json(token_obj, team_name, idx, output_v3_dir)
    
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
        team_output_dir = output_dir / team_folder_name / 'tts_objects'
        team_output_dir.mkdir(parents=True, exist_ok=True)
        dest_preview = team_output_dir / f"{team_display_name} Box.png"
        shutil.copy2(source_preview, dest_preview)
    else:
        logger.warning(f"No preview/icon image found for {team_folder_name}")


def embed_datacard_stats(bag_obj: dict, team_name: str, output_dir: Path, config_dir: Path) -> bool:
    """
    Embed operative stats into datacards within the TTS bag object.
    Returns True if stats were embedded, False if skipped.
    """
    # Load team data
    team_data_path = output_dir / team_name / "data" / f"{team_name}-team-data.json"
    if not team_data_path.exists():
        logger.debug(f"  No team data found for {team_name}, skipping stat embedding")
        return False
    
    logger.debug(f"  Loading team data from {team_data_path}")
    with open(team_data_path, 'r', encoding='utf-8') as f:
        team_data = json.load(f)
    
    # Load weapon rules
    weapon_rules_path = config_dir / "weapon_rules.json"
    with open(weapon_rules_path, 'r', encoding='utf-8') as f:
        weapon_rules = json.load(f)
    
    # Load team config
    team_config_path = config_dir / "team-config.yaml"
    with open(team_config_path, 'r', encoding='utf-8') as f:
        team_config = yaml.safe_load(f)
    
    # Load datacard Lua script
    lua_script_path = config_dir / "defaults" / "tts-script" / "datacard-load-stats.lua"
    with open(lua_script_path, 'r', encoding='utf-8') as f:
        datacard_lua_script = f.read()
    
    # Find all datacard objects in the bag
    datacards = _find_datacards(bag_obj)
    if not datacards:
        logger.debug(f"  No datacards found in TTS object for {team_name}")
        return False
    
    logger.info(f"  Embedding stats for {len(datacards)} datacards")
    
    patched = 0
    for card in datacards:
        nickname = card.get("Nickname", "")
        
        # Match card to operative
        operative = _match_card_to_operative(nickname, team_name, team_data)
        if not operative:
            logger.debug(f"    No match for card '{nickname}'")
            continue
        
        # Build GMNotes
        try:
            gm_notes_data = _build_gm_notes(operative, team_data, weapon_rules)
            gm_notes_json = json.dumps(gm_notes_data, separators=(",", ":"), ensure_ascii=False)
            
            # Get faction rule code if applicable
            operative_name = operative.get('name', '')
            faction_rule_code = _get_faction_rule_code(team_name, team_data, operative_name, config_dir, team_config)
            lua_script = datacard_lua_script + faction_rule_code
            
            # Set GMNotes and Lua script
            card["GMNotes"] = gm_notes_json
            card["LuaScript"] = lua_script
            
            patched += 1
            logger.debug(f"    Embedded stats for '{nickname}'")
        except Exception as e:
            logger.error(f"    Error embedding stats for '{nickname}': {e}")
            import traceback
            logger.error(traceback.format_exc())
            continue
    
    # Update bag timestamp
    _update_bag_timestamp(bag_obj)
    
    logger.info(f"  Embedded stats for {patched}/{len(datacards)} datacards")
    return True


def _find_datacards(tts_data: dict) -> list:
    """Find all datacard objects in TTS JSON."""
    datacards = []
    
    def recurse(obj):
        if isinstance(obj, dict):
            nickname = obj.get("Nickname", "")
            
            if ("CardID" in obj or "CustomDeck" in obj) and nickname:
                excluded_patterns = [
                    "Datacards", "Equipment", "Strategy Ploys", "Firefight Ploys",
                    "OPERATIVE SELECTION", "TOKEN GUIDE", "SKILL AT ARMS", "Faction Rules"
                ]
                
                is_excluded = any(pattern in nickname for pattern in excluded_patterns)
                if not is_excluded:
                    datacards.append(obj)
            
            for key, value in obj.items():
                if key not in ["CustomDeck", "CustomImage"]:
                    recurse(value)
        elif isinstance(obj, list):
            for item in obj:
                recurse(item)
    
    recurse(tts_data)
    return datacards


def _match_card_to_operative(nickname: str, team: str, team_data: dict) -> Optional[dict]:
    """Match a card nickname to an operative in team_data."""
    def normalize(s):
        return s.lower().strip().replace("-", " ").replace("_", " ")
    
    nickname_norm = normalize(nickname)
    team_norm = normalize(team)
    
    datacards = team_data.get('datacards', [])
    for operative in datacards:
        op_name = operative.get('name', '')
        op_name_norm = normalize(op_name)
        
        if op_name_norm == nickname_norm:
            return operative
        
        if op_name_norm.startswith(team_norm):
            op_type = op_name_norm[len(team_norm):].strip()
            if op_type == nickname_norm:
                return operative
    
    return None


def _build_gm_notes(operative: dict, team_data: dict, weapon_rules: dict) -> dict:
    """Build GMNotes JSON structure with operative stats."""
    import re
    
    def parse_move(s: str) -> int:
        m = re.search(r"(\d+)", str(s))
        return int(m.group(1)) if m else 6
    
    def parse_save(s: str) -> int:
        m = re.search(r"(\d+)", str(s))
        return int(m.group(1)) if m else 5
    
    def classify_weapon(weapon: dict) -> str:
        special_rules = weapon.get('special_rules', '').lower()
        if 'range' in special_rules or 'rng' in special_rules:
            return 'ranged'
        return 'melee'
    
    def weapon_prefix(weapon: dict) -> str:
        return '[1E87FF]R[-]' if classify_weapon(weapon) == 'ranged' else '[F4641D]M[-]'
    
    stats = {
        'APL': operative.get('apl', 2),
        'Move': parse_move(operative.get('movement', '6')),
        'Save': parse_save(operative.get('save', '5+')),
        'Wounds': operative.get('wounds', 1)
    }
    
    keywords = ['Operative']
    if 'keywords' in operative:
        keywords.extend(operative.get('keywords', []))
    
    weapons = []
    weapon_rules_found = {}
    for weapon in operative.get('weapons', []):
        weapon_name = weapon.get('name', '')
        special_rules = weapon.get('special_rules', '')
        
        prefix = weapon_prefix(weapon)
        full_name = f'{prefix} {weapon_name}'
        
        weapons.append({
            'name': full_name,
            'plain_name': weapon_name,
            'stats': {
                'ATK': weapon.get('attacks', ''),
                'HIT': weapon.get('hit', ''),
                'DMG': weapon.get('damage', ''),
                'WR': special_rules
            }
        })
        
        if special_rules:
            for rule_name, rule_description in weapon_rules.items():
                if rule_name.lower() in special_rules.lower():
                    weapon_rules_found[rule_name] = rule_description
    
    abilities = []
    for ability in operative.get('passive_abilities', []):
        ability_name = ability.get('name', '')
        ability_desc = ability.get('description', '')
        
        # Filter out malformed entries
        if (ability_desc.isdigit() or 
            (ability_desc and ability_desc[0].isdigit()) or
            (',' in ability_name and len(ability_name.split(',')) > 3) or
            (ability_name.isupper() and len(ability_name) > 20) or
            (not ability_name or not ability_name[0].isupper()) or
            len(ability_name.split()) > 5):
            continue
        
        abilities.append({
            'name': ability_name,
            'text': ability_desc
        })
    
    actions = []
    for action in operative.get('unique_actions', []):
        actions.append({
            'name': action.get('name', ''),
            'text': action.get('description', '')
        })
    
    description_lines = [
        f"[D36B3E][[84E680]APL[-] [ffffff]{stats['APL']}[-]] [[84E680]MOVE[-] [ffffff]{stats['Move']}\"[-]]",
        f"[[84E680]SAVE[-] [ffffff]{stats['Save']}+[-]] [[84E680]WOUNDS[-] [ffffff]{stats['Wounds']}[-]][-]"
    ]
    
    if keywords:
        description_lines.append('[C5C5C5]' + ', '.join(keywords) + '[-]')
    
    description_lines.append('[31B32B]Weapons[-]')
    for w in weapons:
        description_lines.append(w['name'])
        w_stats = w['stats']
        description_lines.append(
            f"[84E680]ATK[-] {w_stats['ATK']} [84E680]HIT[-] {w_stats['HIT']} [84E680]DMG[-] {w_stats['DMG']}"
        )
        if w_stats['WR']:
            description_lines.append(f"[84E680]WR[-]: {w_stats['WR']}")
        description_lines.append('')
    
    if abilities:
        description_lines.append('---')
        description_lines.append('[31B32B]Abilities[-]')
        for ab in abilities:
            description_lines.append(f"- [EF8450]{ab['name']}[-]")
    
    if actions:
        description_lines.append('---')
        description_lines.append('[31B32B]Unique Actions[-]')
        for act in actions:
            description_lines.append(f"- [EF8450]{act['name']}[-]")
    
    description = '\n'.join(description_lines)
    
    gm_notes = {
        'name': operative.get('name', ''),
        'stats': stats,
        'keywords': keywords,
        'weapons': weapons,
        'abilities': abilities,
        'actions': actions,
        'weapon_rules': weapon_rules_found,
        'description': description
    }
    
    return gm_notes


def _get_faction_rule_code(team: str, team_data: dict, operative_name: str, config_dir: Path, team_config: dict) -> str:
    """Generate faction rule Lua code if applicable."""
    team_info = team_config.get('teams', {}).get(team, {})
    if 'faction_rule' not in team_info:
        return ""
    
    faction_rules = team_data.get('faction_rules', [])
    if not faction_rules:
        return ""
    
    if team == "chaos-cult":
        op_lower = operative_name.lower()
        if "mutant" not in op_lower and "torment" not in op_lower and "possessed" not in op_lower:
            return ""
    
    template_path = config_dir / "defaults" / "tts-script" / "faction-rule-chapter-tactics.lua"
    if not template_path.exists():
        return ""
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()
    
    rule_with_options = None
    for rule in faction_rules:
        if 'options' in rule and rule['options']:
            rule_with_options = rule
            break
    
    if not rule_with_options:
        return ""
    
    rule_name = rule_with_options['name']
    options = rule_with_options['options']
    
    lua_options = []
    for opt in options:
        opt_name = opt.get('name', '')
        opt_text = opt.get('text', '')
        opt_name_escaped = opt_name.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        opt_text_escaped = opt_text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        lua_options.append(f'    {{name = "{opt_name_escaped}", text = "{opt_text_escaped}"}}')
    
    options_str = ',\n'.join(lua_options)
    
    lua_code = template.replace('{{FACTION_RULE_NAME}}', rule_name)
    lua_code = lua_code.replace('{{FACTION_RULE_OPTIONS}}', options_str)
    
    return lua_code


def _update_bag_timestamp(tts_data: dict) -> None:
    """Update lastCardUpdate in the top-level bag's LuaScriptState."""
    obj = tts_data.get("ObjectStates", [{}])[0]
    lss = obj.get("LuaScriptState", "")
    try:
        state = json.loads(lss) if lss else {}
    except (json.JSONDecodeError, TypeError):
        state = {}
    
    state["lastCardUpdate"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    obj["LuaScriptState"] = json.dumps(state)


def save_individual_card_json(card_obj: dict, team_name: str, card_type: str, card_index: int, output_dir: Path) -> tuple:
    """
    Save individual card JSON to tts_objects/cards/{card_type}/.
    
    Args:
        card_obj: Single card TTS object
        team_name: Team slug
        card_type: Card type (datacards, equipment, etc.)
        card_index: Card index for filename (fallback)
        output_dir: output_v3 directory
    
    Returns:
        (file_path, modification_timestamp)
    """
    import os
    
    # Create card type subdirectory
    card_type_dir = output_dir / team_name / 'tts_objects' / 'cards' / card_type
    card_type_dir.mkdir(parents=True, exist_ok=True)
    
    # Use card nickname for filename, fallback to index
    card_nickname = card_obj.get('Nickname', f'card-{card_index:03d}')
    # Sanitize filename (lowercase, replace spaces with hyphens)
    safe_name = card_nickname.lower().replace(' ', '-').replace('/', '-').replace('\\', '-')
    filename = f"{safe_name}.json"
    file_path = card_type_dir / filename
    
    # Save JSON
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(card_obj, f, indent=2)
    
    # Get modification time
    file_mtime = os.path.getmtime(file_path)
    timestamp = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%dT%H:%M:%S')
    
    return file_path, timestamp


def save_individual_token_json(token_obj: dict, team_name: str, token_index: int, output_dir: Path) -> tuple:
    """
    Save individual token JSON to tts_objects/tokens/.
    
    Args:
        token_obj: Single token TTS object
        team_name: Team slug
        token_index: Token index for filename (fallback)
        output_dir: output_v3 directory
    
    Returns:
        (file_path, modification_timestamp)
    """
    import os
    
    # Create tokens subdirectory
    tokens_dir = output_dir / team_name / 'tts_objects' / 'tokens'
    tokens_dir.mkdir(parents=True, exist_ok=True)
    
    # Use token nickname for filename, fallback to index
    token_nickname = token_obj.get('Nickname', f'token-{token_index:03d}')
    # Sanitize filename (lowercase, replace spaces with hyphens)
    safe_name = token_nickname.lower().replace(' ', '-').replace('/', '-').replace('\\', '-')
    filename = f"{safe_name}.json"
    file_path = tokens_dir / filename
    
    # Save JSON
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(token_obj, f, indent=2)
    
    # Get modification time
    file_mtime = os.path.getmtime(file_path)
    timestamp = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%dT%H:%M:%S')
    
    return file_path, timestamp


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
            
            # Save individual card JSON
            save_individual_card_json(card_obj, team_name, card_type, 1, output_dir)
            
            contained_objects.append(card_obj)
            deck_id_counter += 1
        elif len(type_cards_data) > 1:
            type_nickname = card_type.replace('-', ' ').title()
            deck_obj = create_deck(type_nickname, team_tag, type_cards_data, deck_id_counter, card_type)
            
            # Save individual card JSONs from deck
            for idx, card_obj in enumerate(deck_obj['ContainedObjects'], start=1):
                save_individual_card_json(card_obj, team_name, card_type, idx, output_dir)
            
            contained_objects.append(deck_obj)
            deck_id_counter += len(type_cards_data)
    
    # Create the bag
    team_display_name = team_name.replace('-', ' ').title()
    team_tag = f"_{team_name.replace('-', '_').title().replace('_', ' ')}"
    
    # Get output file path
    team_output_dir = output_dir / team_name / 'tts_objects'
    team_output_dir.mkdir(parents=True, exist_ok=True)
    output_file = team_output_dir / f"{team_display_name} Box.json"
    
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
    
    # Embed datacard stats (optional - skips if no team data)
    embed_datacard_stats(bag_obj, team_name, output_dir, config_dir)
    
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
    logger.info("TTS Object Generation (with embedded stats) - KT-App Pipeline")
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
    logger.info(f"Output: {PROJECT_ROOT / 'output_v3' / '{team}' / 'tts_objects'}")


if __name__ == '__main__':
    main()
