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
        config_dir: Path = Path('config'),
        team_filter: list = None
    ):
        """
        Initialize TTSGenerator
        
        Args:
            output_v2_dir: Directory containing datacards-urls.json
            tts_output_dir: Directory to save TTS objects
            config_dir: Configuration directory for assets
            team_filter: Optional list of team names to regenerate (if None, regenerate all)
        """
        self.output_v2_dir = output_v2_dir
        self.tts_output_dir = tts_output_dir
        self.config_dir = config_dir
        self.team_filter = team_filter
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
        skipped = 0
        tts_object_entries = []  # Collect entries for datacards-urls.json
        
        for team_name, cards in teams.items():
            # Skip if team filter is active and this team is not in the filter
            if self.team_filter and team_name not in self.team_filter:
                self.logger.debug(f"Skipping {team_name} (not in team filter)")
                skipped += 1
                continue
                
            self.logger.info(f"Generating TTS object for {team_name}")
            texture_url = team_textures.get(team_name)
            mesh_url = team_meshes.get(team_name)
            
            # Get team display name from config
            team_display_name = self._get_team_display_name(team_name)
            output_filename = f"{team_display_name} Cards.json"
            
            self._generate_team_tts_object(team_name, cards, lua_script, texture_url, mesh_url)
            
            # Add entry for this TTS object
            output_filename = f"{team_display_name} Cards.json"
            
            self._generate_team_tts_object(team_name, cards, lua_script, texture_url, mesh_url)
            
            # Add entry for this TTS object
            tts_object_entries.append({
                'faction': '',  # Not applicable for TTS objects
                'team': team_name,
                'type': 'tts_card_box_object',
                'name': team_display_name,
                'url': f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/tts_objects/{team_name}/{output_filename.replace(' ', '%20')}"
            })
            
            count += 1
        if skipped > 0:
            self.logger.info(f"Skipped {skipped} team(s) (no changes or filtered out)")
        
        
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
        from generators.tts_generator_helpers import (
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
        type_order = ['operative-selection', 'faction-rules', 'token-guide', 'markertokens', 'datacards', 'equipment', 'firefight-ploys', 'strategy-ploys']
        
        # Add token bag if tokens exist for this team
        token_bag, token_timestamp = self._load_token_bag(team_name, faction)
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
                
                # Transform card name to match production format
                card_name = card_data['name']
                if card_type == 'operative-selection':
                    # operative-selection-{team} -> {team}-operatives
                    card_name = f"{team_name}-operatives"
                elif card_type == 'token-guide':
                    # token-guide-{team} -> {team}-markertoken-guide
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
        
        # Create the bag with creation timestamp
        team_display_name = team_name.replace('-', ' ').title()
        team_tag = f"_{team_name.replace('-', '_').title().replace('_', ' ')}"
        
        # Get output file path in team subfolder
        team_output_dir = self.tts_output_dir / team_name
        team_output_dir.mkdir(exist_ok=True)
        output_file = team_output_dir / f"{team_display_name} Cards.json"
        
        # Initially use a placeholder timestamp (will be set after file is written)
        from datetime import datetime
        import os
        import re
        placeholder_timestamp = "2000-01-01T00:00:00"
        placeholder_token_timestamp = ""
        
        bag_obj = create_bag(team_display_name, team_tag, contained_objects, lua_script, texture_url, mesh_url, faction, placeholder_timestamp, placeholder_token_timestamp)
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(bag_obj, f, indent=2)
        
        # NOW read the actual file modification time and update all URLs with this timestamp
        file_mtime = os.path.getmtime(output_file)
        actual_timestamp = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%dT%H:%M:%S')
        cache_bust_param = f"?v={int(file_mtime)}"
        
        # Update all URLs in the bag object to use the box file's timestamp for cache busting
        def update_urls_in_object(obj):
            """Recursively update all URLs with the box file's cache-busting parameter"""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in ['FaceURL', 'BackURL', 'ImageURL', 'MeshURL'] and isinstance(value, str):
                        # Replace existing ?v= parameter with box file's timestamp
                        obj[key] = re.sub(r'\?v=\d+', cache_bust_param, value)
                        if '?v=' not in obj[key]:
                            obj[key] += cache_bust_param
                    else:
                        update_urls_in_object(value)
            elif isinstance(obj, list):
                for item in obj:
                    update_urls_in_object(item)
        
        update_urls_in_object(bag_obj)
        
        # Update the bag object with the actual file timestamp in LuaScriptState
        bag_obj = create_bag(team_display_name, team_tag, contained_objects, lua_script, texture_url, mesh_url, faction, actual_timestamp, token_timestamp or "")
        
        # Apply URL updates again after recreating bag
        update_urls_in_object(bag_obj)
        
        # Re-save with the correct timestamp and updated URLs
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
            team_output_dir = self.tts_output_dir / team_folder_name
            team_output_dir.mkdir(exist_ok=True)
            dest_preview = team_output_dir / f"{team_display_name} Cards.png"
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
        """
        Generate/update tts-card-boxes.json with TTS box data.
        Merges with existing entries to preserve teams that weren't regenerated.
        """
        output_file = self.output_v2_dir / 'tts-card-boxes.json'
        
        # Load existing tts-card-boxes.json if it exists
        existing_boxes = {}
        if output_file.exists():
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    # Convert to dict keyed by team for easy lookup
                    existing_boxes = {entry['team']: entry for entry in existing_data}
            except Exception as e:
                self.logger.warning(f"Could not load existing tts-card-boxes.json: {e}")
        
        # Update with new entries (overwrites existing entries for same teams)
        for entry in tts_entries:
            existing_boxes[entry['team']] = {
                'team': entry['team'],
                'name': entry['name'],
                'url': entry['url']
            }
        
        # Convert back to list, sorted by team name
        tts_boxes = sorted(existing_boxes.values(), key=lambda x: x['team'])

        # Write to tts-card-boxes.json
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(tts_boxes, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Updated tts-card-boxes.json ({len(tts_boxes)} total teams, {len(tts_entries)} updated)")
    
    def _rewrite_token_urls_to_v3(self, obj: dict, team_name: str, branch: str = "refactor-kt-app-pipeline") -> dict:
        """
        Recursively rewrite token URLs from v2 to v3 structure.
        
        Converts:
        output_v2/{faction}/{team}/tts/token/{team}-{name}.obj
        to:
        output_v3/{team}/tokens/{team}-{name}.obj
        
        And token bag:
        output_v2/{faction}/{team}/tts/token/{team}-token-mesh.obj
        to:
        output_v3/{team}/tokens/tokenbag/{team}-token-bag.obj
        """
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and 'output_v2' in value and '/tts/token/' in value:
                    # Rewrite v2 token URL to v3
                    # Pattern: .../output_v2/{faction}/{team}/tts/token/{filename}
                    # New:     .../output_v3/{team}/tokens/{filename}
                    if '/output_v2/' in value:
                        parts = value.split('/output_v2/')
                        if len(parts) == 2:
                            base_url = parts[0]
                            after_v2 = parts[1]
                            # Extract filename from end
                            filename_parts = after_v2.split('/')
                            if len(filename_parts) >= 4:
                                # [..., faction, team, 'tts', 'token', filename]
                                filename = filename_parts[-1]
                                # Remove query params if present
                                filename = filename.split('?')[0]
                                # Construct v3 URL (tokens are now in tokens/ folder)
                                new_url = f"{base_url}/output_v3/{team_name}/tokens/{filename}"
                                # Update branch if not main
                                if '/main/' in new_url:
                                    new_url = new_url.replace('/main/', f'/{branch}/')
                                obj[key] = new_url
                                self.logger.debug(f"  Rewrote token URL: {filename}")
                elif isinstance(value, (dict, list)):
                    self._rewrite_token_urls_to_v3(value, team_name, branch)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    self._rewrite_token_urls_to_v3(item, team_name, branch)
        
        return obj
    
    def _load_token_bag(self, team_name: str, faction: str) -> tuple[dict, str] | tuple[None, None]:
        """
        Load token bag object from the team's tts/token folder if it exists.
        
        Args:
            team_name: Team slug (e.g., 'farstalker-kinband')
            faction: Faction name (e.g., 'xenos', 'imperium')
        
        Returns:
            Tuple of (token bag object dict, token timestamp) or (None, None) if no tokens exist
        """
        # For v3 structure, check old tts_objects location first
        workspace_root = self.output_v2_dir.parent  # Get workspace root
        old_token_bag_path = workspace_root / 'tts_objects' / team_name / 'tokens' / f'{team_name}-tokenbag.json'
        
        if old_token_bag_path.exists():
            try:
                with open(old_token_bag_path, 'r', encoding='utf-8') as f:
                    token_data = json.load(f)
                
                # Extract the token bag object (first ObjectState)
                if 'ObjectStates' in token_data and len(token_data['ObjectStates']) > 0:
                    token_bag = token_data['ObjectStates'][0]
                    
                    # Rewrite v2 URLs to v3
                    token_bag = self._rewrite_token_urls_to_v3(token_bag, team_name)
                    
                    self.logger.info(f"Loaded token bag for {team_name} from tts_objects with {len(token_bag.get('ContainedObjects', []))} tokens")
                    
                    # Extract token timestamp from LuaScriptState
                    token_timestamp = ""
                    lua_script_state = token_bag.get('LuaScriptState', '')
                    if lua_script_state:
                        try:
                            state_data = json.loads(lua_script_state)
                            token_timestamp = state_data.get('lastUpdate', '')
                        except:
                            pass
                    
                    return token_bag, token_timestamp
            except Exception as e:
                self.logger.warning(f"Failed to load token bag from tts_objects for {team_name}: {e}")
        
        # Fallback to v2 structure if faction is provided
        if not faction:
            return None, None
        
        # Check if token JSON exists in v2 location
        token_json_path = self.output_v2_dir / faction / team_name / 'tts' / 'token' / f'{team_name}-tokens.json'
        
        if not token_json_path.exists():
            return None, None
        
        try:
            with open(token_json_path, 'r', encoding='utf-8') as f:
                token_data = json.load(f)
            
            # Extract the token bag object (first ObjectState)
            if 'ObjectStates' in token_data and len(token_data['ObjectStates']) > 0:
                token_bag = token_data['ObjectStates'][0]
                
                # Rewrite v2 URLs to v3
                token_bag = self._rewrite_token_urls_to_v3(token_bag, team_name)
                
                self.logger.info(f"Loaded token bag for {team_name} with {len(token_bag.get('ContainedObjects', []))} tokens")
                
                # Extract token timestamp from LuaScriptState
                token_timestamp = ""
                lua_script_state = token_bag.get('LuaScriptState', '')
                if lua_script_state:
                    try:
                        state_data = json.loads(lua_script_state)
                        token_timestamp = state_data.get('lastUpdate', '')
                    except:
                        pass
                
                return token_bag, token_timestamp
        except Exception as e:
            self.logger.warning(f"Failed to load token bag for {team_name}: {e}")
        
        return None, None
