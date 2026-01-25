"""Generate Tabletop Simulator saved object files"""

import json
from pathlib import Path
from collections import defaultdict
import random
import shutil
import logging


class TTSGenerator:
    """Generates TTS Custom_Model_Bag objects from datacards URLs"""
    
    def __init__(
        self,
        output_v2_dir: Path = Path('output_v2'),
        tts_output_dir: Path = Path('tts_objects'),
        config_dir: Path = Path('config')
    ):
        """
        Initialize TTSGenerator
        
        Args:
            output_v2_dir: Directory containing datacards-urls.json
            tts_output_dir: Directory to save TTS objects
            config_dir: Configuration directory for assets
        """
        self.output_v2_dir = output_v2_dir
        self.tts_output_dir = tts_output_dir
        self.config_dir = config_dir
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
                    # Store texture URL for this team
                    team_textures[team_key] = card['url']
                elif 'card-box.obj' in card['name']:
                    # Store mesh URL for this team
                    team_meshes[team_key] = card['url']
            else:
                teams[team_key].append(card)
        
        # Create output directory
        self.tts_output_dir.mkdir(exist_ok=True)
        
        # Generate TTS object for each team
        count = 0
        tts_object_entries = []  # Collect entries for datacards-urls.json
        
        for team_name, cards in teams.items():
            self.logger.info(f"Generating TTS object for {team_name}")
            texture_url = team_textures.get(team_name)
            mesh_url = team_meshes.get(team_name)
            
            # Get team display name from config
            team_display_name = self._get_team_display_name(team_name)
            output_filename = f"{team_display_name} Cards.json"
            
            self._generate_team_tts_object(team_name, cards, lua_script, texture_url, mesh_url)
            
            # Add entry for this TTS object
            tts_object_entries.append({
                'faction': '',  # Not applicable for TTS objects
                'team': team_name,
                'type': 'tts_card_box_object',
                'name': team_display_name,
                'url': f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/tts_objects/{output_filename.replace(' ', '%20')}"
            })
            
            count += 1
        
        # Append TTS object entries to datacards-urls.json
        if tts_object_entries:
            self._append_to_urls_json(all_cards, tts_object_entries)
            self._generate_tts_boxes_json(tts_object_entries)
        
        return count

    def _load_lua_script(self) -> str:
        """Load the Lua script from config defaults folder"""
        script_path = self.config_dir / "defaults" / "tts-script" / "tts-update-rules-in-box-script.lua"
        try:
            with open(script_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                # Remove BOM if present (shouldn't be needed with utf-8-sig, but being safe)
                if content.startswith('\ufeff'):
                    content = content[1:]
                # Convert to Windows line endings for TTS
                content = content.replace('\n', '\r\n')
                return content
        except Exception as e:
            self.logger.warning(f"Could not load Lua script: {e}")
            return ""
    
    def _generate_team_tts_object(self, team_name: str, cards: list, lua_script: str, texture_url: str = None, mesh_url: str = None, last_processed: str = ""):
        """Generate TTS object for a single team"""
        from generators.objects.cardbox_helpers import (
            create_bag, create_deck, create_single_card
        )
        
        # Extract faction from first card's URL (format: output_v2/{faction}/{team}/...)
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
        deck_id_counter = 1000
        type_order = ['operative-selection', 'faction-rules', 'markertokens', 'datacards', 'equipment', 'firefight-ploys', 'strategy-ploys']
        
        # Add token bag if tokens exist for this team
        token_bag = self._load_token_bag(team_name, faction)
        if token_bag:
            contained_objects.append(token_bag)
            self.logger.info(f"Added token bag for {team_name}")
        
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
                card_obj = create_single_card(
                    card_data['name'],
                    card_data['front'],
                    card_data['back'],
                    team_tag,
                    str(deck_id_counter)
                )
                contained_objects.append(card_obj)
                deck_id_counter += 1
            elif len(type_cards_data) > 1:
                type_nickname = card_type.replace('-', ' ').title()
                deck_obj = create_deck(type_nickname, team_tag, type_cards_data, deck_id_counter)
                contained_objects.append(deck_obj)
                deck_id_counter += len(type_cards_data)
        
        # Create the bag with creation timestamp
        team_display_name = team_name.replace('-', ' ').title()
        team_tag = f"_{team_name.replace('-', '_').title().replace('_', ' ')}"
        
        # Get output file path
        output_file = self.tts_output_dir / f"{team_display_name} Cards.json"
        
        # Initially use a placeholder timestamp (will be set after file is written)
        from datetime import datetime
        import os
        placeholder_timestamp = "2000-01-01T00:00:00"
        
        bag_obj = create_bag(team_display_name, team_tag, contained_objects, lua_script, texture_url, mesh_url, faction, placeholder_timestamp)
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(bag_obj, f, indent=2)
        
        # NOW read the actual file modification time and update the embedded timestamp
        file_mtime = os.path.getmtime(output_file)
        actual_timestamp = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%dT%H:%M:%S')
        
        # Update the bag object with the actual file timestamp
        bag_obj = create_bag(team_display_name, team_tag, contained_objects, lua_script, texture_url, mesh_url, faction, actual_timestamp)
        
        # Re-save with the correct timestamp
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(bag_obj, f, indent=2)
        
        # Copy preview image
        self._copy_preview_image(team_name, team_display_name)
    
    def _copy_preview_image(self, team_folder_name: str, team_display_name: str):
        """Copy preview/icon image for a team"""
        # Try icon first (new standard), then preview (legacy)
        team_icon = self.config_dir / "teams" / team_folder_name / "tts-image" / f"{team_folder_name}-icon.png"
        team_preview = self.config_dir / "teams" / team_folder_name / "tts-image" / f"{team_folder_name}-preview.png"
        default_icon = self.config_dir / "defaults" / "tts-image" / "default-icon.png"
        default_preview = self.config_dir / "defaults" / "tts-image" / "default-preview.png"
        
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
            dest_preview = self.tts_output_dir / f"{team_display_name} Cards.png"
            shutil.copy2(source_preview, dest_preview)
        else:
            self.logger.warning(f"No preview/icon image found for {team_folder_name}")
    
    def _get_team_display_name(self, team_name: str) -> str:
        """Convert team slug to display name (e.g., 'farstalker-kinband' -> 'Farstalker Kinband')"""
        return team_name.replace('-', ' ').title()
    
    def _append_to_urls_json(self, existing_cards: list, tts_entries: list):
        """Append TTS object entries to datacards-urls.json"""
        urls_file = self.output_v2_dir / "datacards-urls.json"
        
        # Remove any existing tts_card_box_object entries
        filtered_cards = [card for card in existing_cards if card.get('type') != 'tts_card_box_object']
        
        # Add new TTS entries
        filtered_cards.extend(tts_entries)
        
        # Write back to file
        with open(urls_file, 'w', encoding='utf-8') as f:
            json.dump(filtered_cards, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Added {len(tts_entries)} TTS object entries to datacards-urls.json")
    
    def _generate_tts_boxes_json(self, tts_entries: list):
        """Generate a minimal tts-card-boxes.json with just the TTS box data"""
        tts_boxes = []
        
        for entry in tts_entries:
            tts_boxes.append({
                'team': entry['team'],
                'name': entry['name'],
                'url': entry['url']
            })

        # Write to tts-card-boxes.json
        output_file = self.output_v2_dir / 'tts-card-boxes.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(tts_boxes, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Generated tts-card-boxes.json with {len(tts_boxes)} entries")
    
    def _load_token_bag(self, team_name: str, faction: str) -> dict | None:
        """
        Load token bag object from the team's tts/token folder if it exists.
        
        Args:
            team_name: Team slug (e.g., 'farstalker-kinband')
            faction: Faction name (e.g., 'xenos', 'imperium')
        
        Returns:
            Token bag object dict or None if no tokens exist
        """
        if not faction:
            return None
        
        # Check if token JSON exists
        token_json_path = self.output_v2_dir / faction / team_name / 'tts' / 'token' / f'{team_name}-tokens.json'
        
        if not token_json_path.exists():
            return None
        
        try:
            with open(token_json_path, 'r', encoding='utf-8') as f:
                token_data = json.load(f)
            
            # Extract the token bag object (first ObjectState)
            if 'ObjectStates' in token_data and len(token_data['ObjectStates']) > 0:
                token_bag = token_data['ObjectStates'][0]
                self.logger.info(f"Loaded token bag for {team_name} with {len(token_bag.get('ContainedObjects', []))} tokens")
                return token_bag
        except Exception as e:
            self.logger.warning(f"Failed to load token bag for {team_name}: {e}")
        
        return None


def add_tokens_to_box(box_file: Path, token_bag_file: Path) -> bool:
    """Add token bag to the main box's ContainedObjects and LuaScriptState.
    
    Args:
        box_file: Path to the cardbox JSON file
        token_bag_file: Path to the token bag JSON file
        
    Returns:
        True if successful, False otherwise
    """
    if not box_file.exists():
        print(f"Error: Box file not found: {box_file}")
        return False

    if not token_bag_file.exists():
        print(f"Error: Token bag file not found: {token_bag_file}")
        return False

    # Load box JSON
    print(f"Loading box: {box_file}")
    with open(box_file) as f:
        box_data = json.load(f)

    # Load token bag JSON
    print(f"Loading token bag: {token_bag_file}")
    with open(token_bag_file) as f:
        token_bag_data = json.load(f)

    # Extract the token bag object
    if 'ObjectStates' not in token_bag_data or len(token_bag_data['ObjectStates']) == 0:
        print("Error: Token bag JSON has no ObjectStates")
        return False

    token_bag_obj = token_bag_data['ObjectStates'][0]

    # Get the box object
    if 'ObjectStates' not in box_data or len(box_data['ObjectStates']) == 0:
        print("Error: Box JSON has no ObjectStates")
        return False

    box_obj = box_data['ObjectStates'][0]

    # Check if ContainedObjects exists
    if 'ContainedObjects' not in box_obj:
        box_obj['ContainedObjects'] = []

    # Check if token bag already exists (by name)
    token_bag_name = token_bag_obj.get('Nickname', '')
    existing_idx = None
    for i, obj in enumerate(box_obj['ContainedObjects']):
        if obj.get('Nickname', '') == token_bag_name:
            existing_idx = i
            break

    # Add or replace token bag
    if existing_idx is not None:
        print(f"Replacing existing token bag at index {existing_idx}")
        box_obj['ContainedObjects'][existing_idx] = token_bag_obj
    else:
        print("Adding new token bag to ContainedObjects")
        box_obj['ContainedObjects'].append(token_bag_obj)

    # Add token bag to LuaScriptState
    lua_state = box_obj.get('LuaScriptState', '')
    if lua_state:
        try:
            state_data = json.loads(lua_state)
        except Exception:
            state_data = {"ml": {}, "rr": 270}
    else:
        state_data = {"ml": {}, "rr": 270}

    token_bag_guid = token_bag_obj.get('GUID', 'unknown')
    state_data['ml'][token_bag_guid] = {
        "lock": False,
        "pos": {"x": 5.5, "y": -2.46, "z": -8.5},
        "rot": {"x": 0.0169, "y": 269.9995, "z": 0.0799},
    }

    # Update LuaScriptState
    box_obj['LuaScriptState'] = json.dumps(state_data)
    print("Added token bag to LuaScriptState at position x=5.5, z=-8.5")

    # Save updated box
    with open(box_file, 'w') as f:
        json.dump(box_data, f, indent=2)

    print("✓ Updated box with token bag")
    print(f"  Total objects in box: {len(box_obj['ContainedObjects'])}")

    return True

