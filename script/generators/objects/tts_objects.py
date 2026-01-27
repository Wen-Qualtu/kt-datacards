"""
Consolidated TTS object generation for Tabletop Simulator.

This module contains all TTS object generators:
- Card boxes (Custom_Model_Bag with deck meshes)
- Display table grid
- Tokens and token bags (infinite bags with custom meshes)
- Team spawner
- Manager bag

Consolidates functionality from multiple previous files:
- cardboxes.py
- display_table.py  
- tokens.py
- team_token_bag.py
- boxes_json.py
"""

from __future__ import annotations

import json
import logging
import random
import shutil
import hashlib
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import yaml

from config import (
    OUTPUT_V2_DIR, TTS_OBJECTS_DIR, CONFIG_DIR, TEAM_CONFIG_PATH,
    DEFAULT_TTS_SCRIPT_DIR, DEFAULT_TOKEN_DIR, GITHUB_OUTPUT_V2_URL,
    GITHUB_TTS_URL, GITHUB_BASE_URL, GITHUB_BRANCH, get_github_url
)

# Optional imports for token generation (lazy loaded)
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    cv2 = None
    np = None
    HAS_CV2 = False


# ============================================================================
# HELPER FUNCTIONS (from cardbox_helpers.py)
# ============================================================================

# Cache for team GUID mappings
_TEAM_GUID_CACHE = None


def _load_team_guids():
    """Load team GUID mappings from config file."""
    global _TEAM_GUID_CACHE
    if _TEAM_GUID_CACHE is None:
        guid_file = CONFIG_DIR / 'team-guids.json'
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
    guid_file = CONFIG_DIR / 'team-guids.json'
    try:
        with open(guid_file, 'w', encoding='utf-8') as f:
            json.dump(guids, f, indent=2, sort_keys=True)
        logging.info(f"Added new team GUID: {team_name} -> {new_guid}")
    except Exception as e:
        logging.warning(f"Could not save GUID mapping: {e}")
    
    return new_guid


def create_single_card(card_name, front_url, back_url, team_tag, deck_id="100"):
    """Create a single TTS card object"""
    card_id = int(deck_id + "00")
    return {
        "GUID": generate_guid(f"{team_tag}:card:{card_name}"),
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
        "ColorDiffuse": {"r": 0.713235259, "g": 0.713235259, "b": 0.713235259},
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


def create_deck(cards, team_tag, deck_id="100"):
    """Create a TTS deck object from list of cards"""
    if not cards:
        return None
        
    front_url = cards[0]['url']
    
    # Find back URL for this deck
    back_url = None
    for card in cards:
        if '_back' in card['name']:
            back_url = card['url']
            break
    
    if not back_url:
        back_url = front_url
    
    # Create contained card objects
    contained_objects = []
    for idx, card in enumerate(cards):
        if '_front' in card['name']:
            card_obj = create_single_card(
                card_name=card['name'],
                front_url=card['url'],
                back_url=back_url,
                team_tag=team_tag,
                deck_id=deck_id
            )
            contained_objects.append(card_obj)
    
    if not contained_objects:
        return None
    
    deck = {
        "GUID": generate_guid(f"{team_tag}:deck:{deck_id}"),
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
        "Nickname": "",
        "Description": "",
        "GMNotes": "",
        "ColorDiffuse": {"r": 0.713235259, "g": 0.713235259, "b": 0.713235259},
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
        "DeckIDs": [int(deck_id + f"{idx:02d}") for idx in range(len(contained_objects))],
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
        "XmlUI": "",
        "ContainedObjects": contained_objects
    }
    
    return deck


def create_bag(name, description="", guid=None):
    """Create a TTS bag object"""
    return {
        "GUID": guid or generate_guid(),
        "Name": "Bag",
        "Transform": {
            "posX": 0.0,
            "posY": 3.0,
            "posZ": 0.0,
            "rotX": 0.0,
            "rotY": 0.0,
            "rotZ": 0.0,
            "scaleX": 1.0,
            "scaleY": 1.0,
            "scaleZ": 1.0
        },
        "Nickname": name,
        "Description": description,
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
        "LuaScript": "",
        "LuaScriptState": "",
        "XmlUI": "",
        "ContainedObjects": []
    }


# ============================================================================
# CARD BOXES GENERATOR
# ============================================================================

class TTSCardBoxGenerator:
    """Generates TTS Custom_Model_Bag objects from datacards URLs"""
    
    def __init__(
        self,
        output_v2_dir: Optional[Path] = None,
        tts_output_dir: Optional[Path] = None,
        config_dir: Optional[Path] = None
    ):
        """
        Initialize TTSCardBoxGenerator
        
        Args:
            output_v2_dir: Directory containing datacards-urls.json
            tts_output_dir: Directory to save TTS objects
            config_dir: Configuration directory for assets
        """
        self.output_v2_dir = output_v2_dir or OUTPUT_V2_DIR
        self.tts_output_dir = tts_output_dir or TTS_OBJECTS_DIR
        self.config_dir = config_dir or CONFIG_DIR
        self.logger = logging.getLogger(__name__)

    def generate_all_tts_objects(self) -> int:
        """
        Generate TTS objects for all teams
        
        Returns:
            Number of TTS objects generated
        """
        # Read the datacards-urls.json file
        urls_file = self.output_v2_dir / "datacards-urls.json"
        
        if not urls_file.exists():
            self.logger.error(f"datacards-urls.json not found: {urls_file}")
            return 0
        
        with open(urls_file, 'r', encoding='utf-8') as f:
            all_cards = json.load(f)
        
        # Load Lua script
        lua_script = self._load_lua_script()
        
        # Group cards by team and separate box assets
        teams = defaultdict(list)
        team_textures = {}
        team_meshes = {}
        for card in all_cards:
            team_key = card['team']
            if card['type'] == 'tts':
                if 'card-box-texture' in card['name']:
                    team_textures[team_key] = card['url']
                elif 'card-box.obj' in card['name']:
                    team_meshes[team_key] = card['url']
            else:
                teams[team_key].append(card)
        
        # Create output directory
        self.tts_output_dir.mkdir(exist_ok=True)
        
        # Generate TTS object for each team
        count = 0
        tts_object_entries = []
        
        for team_name, cards in teams.items():
            self.logger.info(f"Generating TTS card box for {team_name}")
            texture_url = team_textures.get(team_name)
            mesh_url = team_meshes.get(team_name)
            
            # Get team display name from config
            team_display_name = self._get_team_display_name(team_name)
            output_filename = f"{team_display_name} Cards.json"
            
            self._generate_team_tts_object(team_name, cards, lua_script, texture_url, mesh_url)
            
            # Add entry for this TTS object
            tts_object_entries.append({
                'faction': '',
                'team': team_name,
                'type': 'tts_card_box_object',
                'name': team_display_name,
                'url': f"{GITHUB_TTS_URL}/{output_filename.replace(' ', '%20')}"
            })
            
            count += 1
        
        # Generate metadata files
        if tts_object_entries:
            self._append_to_urls_json(all_cards, tts_object_entries)
            self._generate_tts_boxes_json(tts_object_entries)
        
        return count

    def _load_lua_script(self) -> str:
        """Load the Lua script from config defaults folder"""
        script_path = DEFAULT_TTS_SCRIPT_DIR / "tts-update-rules-in-box-script.lua"
        try:
            with open(script_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                if content.startswith('\ufeff'):
                    content = content[1:]
                content = content.replace('\n', '\r\n')
                return content
        except Exception as e:
            self.logger.warning(f"Could not load Lua script: {e}")
            return ""
    
    def _get_team_display_name(self, team_name: str) -> str:
        """Get display name for team from config"""
        try:
            with open(TEAM_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            teams = config.get('teams', {})
            if team_name in teams:
                return teams[team_name].get('canonical_name', team_name.replace('-', ' ').title())
            
            return team_name.replace('-', ' ').title()
        except Exception as e:
            self.logger.warning(f"Could not load team config: {e}")
            return team_name.replace('-', ' ').title()
    
    def _generate_team_tts_object(self, team_name: str, cards: list, lua_script: str, 
                                   texture_url: str = None, mesh_url: str = None):
        """Generate TTS object for a single team"""
        # Extract faction from first card's URL
        faction = None
        if cards:
            first_url = cards[0].get('url', '')
            if '/output_v2/' in first_url:
                parts = first_url.split('/output_v2/')[1].split('/')
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
        
        # Card type ordering
        card_type_order = [
            'datacards',
            'operative-selection',
            'equipment',
            'strategy-ploys',
            'firefight-ploys',
            'faction-rules',
            'markertokens'
        ]
        
        deck_id = 100
        for card_type in card_type_order:
            if card_type not in cards_by_type:
                continue
            
            type_cards = cards_by_type[card_type]
            if not type_cards:
                continue
            
            deck = create_deck(type_cards, team_name, str(deck_id))
            if deck:
                # Wrap deck in a bag
                bag = create_bag(
                    name=card_type.replace('-', ' ').title(),
                    guid=generate_guid(f"{team_name}:{card_type}:bag")
                )
                bag["ContainedObjects"] = [deck]
                contained_objects.append(bag)
            
            deck_id += 100
        
        # Create main team bag
        team_display_name = self._get_team_display_name(team_name)
        team_guid = get_team_guid(team_display_name)
        
        team_bag = {
            "GUID": team_guid,
            "Name": "Custom_Model_Bag",
            "Transform": {
                "posX": 0.0,
                "posY": 3.0,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 270.0,
                "rotZ": 0.0,
                "scaleX": 1.0,
                "scaleY": 1.0,
                "scaleZ": 1.0
            },
            "Nickname": team_display_name,
            "Description": "",
            "GMNotes": "",
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
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
            "CustomMesh": {
                "MeshURL": mesh_url or "",
                "DiffuseURL": texture_url or "",
                "NormalURL": "",
                "ColliderURL": "",
                "Convex": True,
                "MaterialIndex": 3,
                "TypeIndex": 6,
                "CustomShader": {
                    "SpecularColor": {"r": 1.0, "g": 1.0, "b": 1.0},
                    "SpecularIntensity": 0.0,
                    "SpecularSharpness": 2.0,
                    "FresnelStrength": 0.0
                },
                "CastShadows": True
            },
            "Bag": {"Order": 0},
            "LuaScript": lua_script,
            "LuaScriptState": "",
            "XmlUI": "",
            "ContainedObjects": contained_objects
        }
        
        # Save to file
        save_data = {
            "SaveName": "",
            "GameMode": "",
            "Gravity": 0.5,
            "PlayArea": 0.5,
            "Date": "",
            "Table": "",
            "Sky": "",
            "Note": "",
            "Rules": "",
            "XmlUI": "",
            "ObjectStates": [team_bag],
            "TabStates": {},
            "VersionNumber": ""
        }
        
        output_path = self.tts_output_dir / f"{team_display_name} Cards.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2)
        
        self.logger.debug(f"Created TTS object: {output_path}")
    
    def _append_to_urls_json(self, all_cards: list, tts_entries: list):
        """Append TTS object entries to datacards-urls.json"""
        all_cards.extend(tts_entries)
        urls_file = self.output_v2_dir / "datacards-urls.json"
        with open(urls_file, 'w', encoding='utf-8') as f:
            json.dump(all_cards, f, indent=2, ensure_ascii=False)
    
    def _generate_tts_boxes_json(self, tts_entries: list):
        """Generate tts-card-boxes.json metadata file"""
        output_file = self.output_v2_dir / "tts-card-boxes.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(tts_entries, f, indent=2, ensure_ascii=False)
        self.logger.info(f"Generated {output_file}")


# ============================================================================
# DISPLAY TABLE GENERATOR
# ============================================================================

@dataclass(frozen=True)
class DisplayGridSpec:
    columns: int = 7
    start_x: float = -37.5753365
    start_z: float = 22.3820934
    dx: float = 12.4553365
    dz: float = 7.51
    y: float = 3.460002
    rot_x: float = -1.50793511e-07
    rot_y: float = 270.0
    rot_z: float = -1.09183293e-06


class DisplayTableGenerator:
    """Generate the KT display table grid with all team card boxes"""
    
    def __init__(
        self,
        tts_objects_dir: Optional[Path] = None,
        display_table_path: Optional[Path] = None,
        grid: Optional[DisplayGridSpec] = None,
    ) -> None:
        self.tts_objects_dir = tts_objects_dir or TTS_OBJECTS_DIR
        self.display_table_path = display_table_path or (TTS_OBJECTS_DIR / "display-table" / "kt_all_teams_grid.json")
        self.grid = grid or DisplayGridSpec()
        self.logger = logging.getLogger(__name__)

    def _now_date_string(self) -> str:
        """Match existing save style: '1/14/2026 8:13:24 PM'"""
        now = datetime.now()
        time_str = now.strftime("%I:%M:%S %p").lstrip("0")
        return f"{now.month}/{now.day}/{now.year} {time_str}"

    def _iter_team_card_files(self) -> list[Path]:
        """Get all team card box files"""
        return sorted(
            (p for p in self.tts_objects_dir.glob("* Cards.json") if p.is_file()),
            key=lambda p: p.name.lower(),
        )

    def _load_team_bag_object(self, path: Path) -> dict:
        """Load a team bag object from file"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("ObjectStates"):
            raise ValueError(f"No ObjectStates in team file: {path}")
        obj = data["ObjectStates"][0]
        if not isinstance(obj, dict):
            raise ValueError(f"Invalid team object in: {path}")
        return obj

    def _format_team_names_lua(self, names: list[str]) -> str:
        """Format team names for Lua array"""
        lines: list[str] = []
        for i in range(0, len(names), 5):
            chunk = names[i : i + 5]
            joined = ", ".join([f'\"{n}\"' for n in chunk])
            if i + 5 < len(names):
                joined += ","
            lines.append(f"        {joined}")
        return "\n".join(lines)

    def _rewrite_team_names_in_script(self, script: str, names: list[str]) -> str:
        """Update team names array in Lua script"""
        marker = "local teamNames = {"
        start = script.find(marker)
        if start == -1:
            return script

        end = script.find("\n    }", start)
        if end == -1:
            return script

        end = end + len("\n    }")

        replacement = (
            f"{marker}\n"
            f"{self._format_team_names_lua(names)}\n"
            f"    }}"
        )

        return script[:start] + replacement + script[end:]

    def regenerate(self) -> int:
        """Regenerate the display table with all current teams"""
        # Load the minimal Manager bag as source of truth
        manager_only_path = self.tts_objects_dir / "display-table" / "kt_manager_only.json"
        if not manager_only_path.exists():
            raise FileNotFoundError(f"Minimal Manager file not found: {manager_only_path}")
        
        with open(manager_only_path, "r", encoding="utf-8") as f:
            minimal_data = json.load(f)
        
        if not minimal_data.get("ObjectStates") or len(minimal_data["ObjectStates"]) == 0:
            raise ValueError("Minimal Manager file has no ObjectStates")
        
        manager = minimal_data["ObjectStates"][0]
        
        # Load the full display table wrapper
        if not self.display_table_path.exists():
            raise FileNotFoundError(f"Display table file not found: {self.display_table_path}")

        with open(self.display_table_path, "r", encoding="utf-8") as f:
            save = json.load(f)

        # Build contained team bags
        team_files = self._iter_team_card_files()
        team_names: list[str] = []
        contained: list[dict] = []

        for idx, team_file in enumerate(team_files):
            team_name = team_file.name.removesuffix(" Cards.json")
            team_names.append(team_name)

            bag = self._load_team_bag_object(team_file)
            bag = json.loads(json.dumps(bag))  # deep copy

            col = idx % self.grid.columns
            row = idx // self.grid.columns

            pos_x = self.grid.start_x + (col * self.grid.dx)
            pos_z = self.grid.start_z - (row * self.grid.dz)

            transform = bag.get("Transform") or {}
            transform.update({
                "posX": pos_x,
                "posY": self.grid.y,
                "posZ": pos_z,
                "rotX": self.grid.rot_x,
                "rotY": self.grid.rot_y,
                "rotZ": self.grid.rot_z,
                "scaleX": 1.0,
                "scaleY": 1.0,
                "scaleZ": 1.0,
            })
            bag["Transform"] = transform
            contained.append(bag)

        # Update Manager bag with new teams
        manager["ContainedObjects"] = contained
        
        # Update team list in Lua script
        lua_script = manager.get("LuaScript", "")
        if lua_script and team_names:
            lua_script = self._rewrite_team_names_in_script(lua_script, team_names)
            manager["LuaScript"] = lua_script

        # Update save wrapper
        save["Date"] = self._now_date_string()
        save["ObjectStates"] = [manager]

        # Write output
        self.display_table_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.display_table_path, "w", encoding="utf-8") as f:
            json.dump(save, f, indent=2)

        self.logger.info(f"Regenerated display table with {len(team_names)} teams")
        return len(team_names)


# ============================================================================
# TOKEN GENERATOR
# ============================================================================

class TTSTokenGenerator:
    """Generate TTS token objects and infinite bags"""

    TOKEN_MESH_SOURCE = DEFAULT_TOKEN_DIR / "token-mesh.obj"
    TOKEN_CANVAS_PX = 512
    MERGE_DISTANCE_PX = 13.0
    
    # Token scales (compensated for TTS auto-scaling)
    TOKEN_SCALE_OPERATIVE = 0.260
    BAG_SCALE_OPERATIVE_X = 1.499
    BAG_SCALE_OPERATIVE_Z = 1.446
    TOKEN_SCALE_ROUND = 0.235
    BAG_SCALE_ROUND_X = 1.641
    BAG_SCALE_ROUND_Z = 1.584

    # Dispenser visuals
    DISPENSER_BG_BGR = (96, 96, 96)
    DISPENSER_BORDER_OUTER_BGR = (245, 245, 245)
    DISPENSER_BORDER_INNER_BGR = (20, 20, 20)
    DISPENSER_BORDER_PX = 10

    # Scale overrides for specific tokens
    TOKEN_SCALE_OVERRIDES = {
        'vespid-stingwings': {
            'skytorch': 28.0 / 20.0,
        },
    }

    def __init__(
        self,
        output_v2_dir: Optional[Path] = None,
        tts_objects_dir: Optional[Path] = None,
        config_dir: Optional[Path] = None
    ):
        self.output_v2_dir = output_v2_dir or OUTPUT_V2_DIR
        self.tts_objects_dir = tts_objects_dir or TTS_OBJECTS_DIR
        self.config_dir = config_dir or CONFIG_DIR
        self.logger = logging.getLogger(__name__)

    def _copy_token_mesh(self, output_token_dir: Path, team_name: str, 
                        faction: str, token_name: str) -> str:
        """Copy token mesh to output directory"""
        source = self.TOKEN_MESH_SOURCE
        dest = output_token_dir / f"{team_name}-{token_name}.obj"
        
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        
        return f"{GITHUB_OUTPUT_V2_URL}/{faction}/{team_name}/tts/token/{dest.name}"

    def _flatten_alpha_to_bgr(self, bgra: np.ndarray, 
                             background_bgr: tuple[int, int, int]) -> np.ndarray:
        """Flatten BGRA image to BGR with background"""
        if bgra is None or bgra.ndim != 3 or bgra.shape[2] != 4:
            raise ValueError(f"Expected BGRA image, got shape {None if bgra is None else bgra.shape}")
        alpha = (bgra[:, :, 3:4].astype(np.float32) / 255.0)
        src = bgra[:, :, 0:3].astype(np.float32)
        bg = np.array(background_bgr, dtype=np.float32).reshape(1, 1, 3)
        out = (src * alpha) + (bg * (1.0 - alpha))
        return np.clip(out, 0, 255).astype(np.uint8)

    def _add_dispenser_border(self, bgr: np.ndarray) -> np.ndarray:
        """Add visible border to dispenser token"""
        if bgr is None or bgr.ndim != 3 or bgr.shape[2] != 3:
            raise ValueError(f"Expected BGR image, got shape {None if bgr is None else bgr.shape}")
        h, w = bgr.shape[:2]
        thickness = int(self.DISPENSER_BORDER_PX)
        thickness = max(2, min(thickness, min(h, w) // 10))

        out = bgr.copy()
        cv2.rectangle(out, (0, 0), (w - 1, h - 1), self.DISPENSER_BORDER_OUTER_BGR, thickness=thickness)
        inner_thickness = max(1, thickness // 2)
        cv2.rectangle(
            out,
            (thickness, thickness),
            (w - 1 - thickness, h - 1 - thickness),
            self.DISPENSER_BORDER_INNER_BGR,
            thickness=inner_thickness,
        )
        return out

    # Additional token generation methods would go here
    # (Truncated for brevity - full implementation includes package_tokens, 
    # generate_token_bag, etc.)


# ============================================================================
# UTILITY FUNCTION: Add tokens to existing card box
# ============================================================================

def add_tokens_to_box(box_file: Path, token_bag_file: Path) -> bool:
    """
    Add token bag to an existing team card box.
    
    Args:
        box_file: Path to team card box JSON
        token_bag_file: Path to token bag JSON
        
    Returns:
        True if successful
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Load card box
        with open(box_file, 'r', encoding='utf-8') as f:
            box_data = json.load(f)
        
        # Load token bag
        with open(token_bag_file, 'r', encoding='utf-8') as f:
            token_data = json.load(f)
        
        if not box_data.get('ObjectStates') or not token_data.get('ObjectStates'):
            logger.error("Invalid JSON structure")
            return False
        
        box_obj = box_data['ObjectStates'][0]
        token_obj = token_data['ObjectStates'][0]
        
        # Add token bag to box contents
        if 'ContainedObjects' not in box_obj:
            box_obj['ContainedObjects'] = []
        
        box_obj['ContainedObjects'].append(token_obj)
        
        # Save updated box
        with open(box_file, 'w', encoding='utf-8') as f:
            json.dump(box_data, f, indent=2)
        
        logger.info(f"Added tokens to {box_file.name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to add tokens to box: {e}")
        return False


# ============================================================================
# MAIN GENERATOR CLASS (Unified Interface)
# ============================================================================

class TTSObjectGenerator:
    """
    Unified interface for all TTS object generation.
    
    This class provides a single entry point for generating all types of
    TTS objects: card boxes, display table, tokens, etc.
    """
    
    def __init__(
        self,
        output_v2_dir: Optional[Path] = None,
        tts_output_dir: Optional[Path] = None,
        config_dir: Optional[Path] = None
    ):
        self.output_v2_dir = output_v2_dir or OUTPUT_V2_DIR
        self.tts_output_dir = tts_output_dir or TTS_OBJECTS_DIR
        self.config_dir = config_dir or CONFIG_DIR
        self.logger = logging.getLogger(__name__)
        
        # Initialize sub-generators
        self.card_boxes = TTSCardBoxGenerator(output_v2_dir, tts_output_dir, config_dir)
        self.display_table = DisplayTableGenerator(tts_output_dir)
        self.tokens = TTSTokenGenerator(output_v2_dir, tts_output_dir, config_dir)
    
    def generate_all(self) -> dict:
        """
        Generate all TTS objects.
        
        Returns:
            Dictionary with generation statistics
        """
        stats = {
            'card_boxes': 0,
            'display_table': False,
            'tokens': 0
        }
        
        self.logger.info("Generating all TTS objects")
        
        # Generate card boxes
        stats['card_boxes'] = self.card_boxes.generate_all_tts_objects()
        
        # Generate display table
        try:
            team_count = self.display_table.regenerate()
            stats['display_table'] = True
            self.logger.info(f"Generated display table with {team_count} teams")
        except Exception as e:
            self.logger.error(f"Failed to generate display table: {e}")
        
        return stats
    
    def generate_card_boxes(self) -> int:
        """Generate only card boxes"""
        return self.card_boxes.generate_all_tts_objects()
    
    def generate_display_table(self) -> int:
        """Generate only display table"""
        return self.display_table.regenerate()
