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
        
        # Group cards by team and separate box textures
        teams = defaultdict(list)
        team_textures = {}
        for card in all_cards:
            team_key = card['team']
            if card['type'] == 'tts' and 'card-box-texture' in card['name']:
                # Store texture URL for this team
                team_textures[team_key] = card['url']
            else:
                teams[team_key].append(card)
        
        # Create output directory
        self.tts_output_dir.mkdir(exist_ok=True)
        
        # Generate TTS object for each team
        count = 0
        for team_name, cards in teams.items():
            self.logger.info(f"Generating TTS object for {team_name}")
            texture_url = team_textures.get(team_name)
            self._generate_team_tts_object(team_name, cards, lua_script, texture_url)
            count += 1
        
        return count
    
    def _load_lua_script(self) -> str:
        """Load the Lua script from docs folder"""
        script_path = self.config_dir.parent / "docs" / "tts-update-rules-in-box-script.lua"
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Convert to Windows line endings for TTS
                content = content.replace('\n', '\r\n')
                return content
        except Exception as e:
            self.logger.warning(f"Could not load Lua script: {e}")
            return ""
    
    def _generate_team_tts_object(self, team_name: str, cards: list, lua_script: str, texture_url: str = None):
        """Generate TTS object for a single team"""
        from ..generators.tts_generator_helpers import (
            create_bag, create_deck, create_single_card
        )
        
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
        
        # Create the bag
        team_display_name = team_name.replace('-', ' ').title()
        team_tag = f"_{team_name.replace('-', '_').title().replace('_', ' ')}"
        bag_obj = create_bag(team_display_name, team_tag, contained_objects, lua_script, texture_url)
        
        # Save to file
        output_file = self.tts_output_dir / f"{team_display_name} Cards.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(bag_obj, f, indent=2)
        
        # Copy preview image
        self._copy_preview_image(team_name, team_display_name)
    
    def _copy_preview_image(self, team_folder_name: str, team_display_name: str):
        """Copy preview image for a team"""
        team_preview = self.config_dir / "teams" / team_folder_name / "tts-image" / f"{team_folder_name}-preview.png"
        default_preview = self.config_dir / "defaults" / "tts-image" / "default-preview.png"
        
        source_preview = team_preview if team_preview.exists() else default_preview
        
        if source_preview.exists():
            dest_preview = self.tts_output_dir / f"{team_display_name} Cards.png"
            shutil.copy2(source_preview, dest_preview)
        else:
            self.logger.warning(f"No preview image found for {team_folder_name}")
