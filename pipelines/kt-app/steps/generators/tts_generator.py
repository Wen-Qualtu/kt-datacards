"""Generate Tabletop Simulator saved object files"""

from __future__ import annotations
import json
from pathlib import Path
from collections import defaultdict
import random
import shutil
import logging
from datetime import datetime, timezone


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
                elif 'card-box' in card['name'] and card['url'].endswith('.obj'):
                    # Store mesh URL for this team
                    team_meshes[team_key] = card['url']
            else:
                teams[team_key].append(card)
        
        # Create output directory
        self.tts_output_dir.mkdir(exist_ok=True)
        
        # Generate TTS object for each team
        count = 0
        skipped = 0
        
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
            
            self._generate_team_tts_object(team_name, cards, lua_script, texture_url, mesh_url)
            
            count += 1
        if skipped > 0:
            self.logger.info(f"Skipped {skipped} team(s) (no changes or filtered out)")
        
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
        # Pass first card URL to extract github base
        sample_url = cards[0]['url'] if cards else None
        token_bag, token_timestamp = self._load_token_bag(team_name, faction, sample_url)
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
        
        # Get output file path in team subfolder under output_v3/{team}/tts_object/
        team_output_dir = self.tts_output_dir / team_name / 'tts_object'
        team_output_dir.mkdir(parents=True, exist_ok=True)
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
            team_output_dir = self.tts_output_dir / team_folder_name / 'tts_object'
            team_output_dir.mkdir(parents=True, exist_ok=True)
            dest_preview = team_output_dir / f"{team_display_name} Cards.png"
            shutil.copy2(source_preview, dest_preview)
        else:
            self.logger.warning(f"No preview/icon image found for {team_folder_name}")
    
    def _get_team_display_name(self, team_name: str) -> str:
        """Convert team slug to display name (e.g., 'farstalker-kinband' -> 'Farstalker Kinband')"""
        return team_name.replace('-', ' ').title()
    
    def _rewrite_token_urls_to_v3(self, obj, team_name: str, branch: str = 'main'):
        """
        Recursively rewrite token URLs from v2 to v3 structure.
        
        Converts:
        output_v2/{faction}/{team}/tts/token/{team}-{name}.obj
        to:
        output_v3/{team}/tokens/{team}-{name}.obj
        
        And token bag:
        output_v2/{faction}/{team}/tts/{team}-token-bag.obj
        to:
        output_v3/{team}/tokens/tokenbag/{team}-token-bag.obj
        
        Also adds DiffuseURL for token bag icon.
        """
        if isinstance(obj, dict):
            # Check if this is a token bag object (has CustomMesh with token-bag.obj)
            if 'CustomMesh' in obj and 'MeshURL' in obj['CustomMesh']:
                mesh_url = obj['CustomMesh']['MeshURL']
                if isinstance(mesh_url, str) and 'token-bag.obj' in mesh_url:
                    # This is a token bag - rewrite mesh URL and add icon
                    if '/output_v2/' in mesh_url:
                        parts = mesh_url.split('/output_v2/')
                        if len(parts) == 2:
                            base_url = parts[0]
                            # Construct new v3 URL for token bag
                            new_mesh_url = f"{base_url}/output_v3/{team_name}/tokens/tokenbag/{team_name}-token-bag.obj"
                            if '/main/' in new_mesh_url:
                                new_mesh_url = new_mesh_url.replace('/main/', f'/{branch}/')
                            obj['CustomMesh']['MeshURL'] = new_mesh_url
                            
                            # Add DiffuseURL for token bag icon
                            icon_url = f"{base_url}/output_v3/{team_name}/tokens/tokenbag/{team_name}-token-bag-icon.png"
                            if '/main/' in icon_url:
                                icon_url = icon_url.replace('/main/', f'/{branch}/')
                            obj['CustomMesh']['DiffuseURL'] = icon_url
                            
                            self.logger.debug(f"  Rewrote token bag mesh and added icon")
            
            # Recursively process all string values
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
    
    def _load_token_bag(self, team_name: str, faction: str, sample_url: str = None) -> tuple[dict, str] | tuple[None, None]:
        """
        Generate token bag from output_v3/{team}/tokens/ files.
        
        Scans the tokens directory for .obj/.png token files and generates
        a TTS token bag object containing them.
        
        Args:
            team_name: Team slug (e.g., 'farstalker-kinband')
            faction: Faction name (e.g., 'xenos', 'imperium')
            sample_url: Optional sample card URL to extract github base from
        
        Returns:
            Tuple of (token bag object dict, token timestamp) or (None, None) if no tokens exist
        """
        from generators.tts_generator_helpers import generate_guid
        
        workspace_root = self.output_v2_dir.parent
        tokens_dir = workspace_root / 'output_v3' / team_name / 'tokens'
        
        if not tokens_dir.exists():
            return None, None
        
        # Find all token .obj files (excluding tokenbag folder)
        token_files = []
        for obj_file in tokens_dir.glob('*.obj'):
            # Get corresponding .png file
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
            self.logger.warning(f"Token bag mesh or icon not found for {team_name}")
            return None, None
        
        # Extract github base URL from sample card URL if available
        github_base = ""
        if sample_url and '/output_v3/' in sample_url:
            # Format: https://github.com/user/repo/raw/branch/output_v3/...
            github_base = sample_url.split('/output_v3/')[0]
        elif sample_url and '/output_v2/' in sample_url:
            # Format: https://github.com/user/repo/raw/branch/output_v2/...
            github_base = sample_url.split('/output_v2/')[0]
        
        if not github_base:
            self.logger.warning(f"Could not extract github base URL, using placeholder")
            github_base = "https://github.com/user/repo/raw/main"
        
        # Generate token objects
        token_objects = []
        for token_name, obj_path, png_path in sorted(token_files):
            # Create token display name (remove team prefix)
            display_name = token_name.replace(f'{team_name}-', '').replace('-', ' ').title()
            
            # Build URLs
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
        lua_script_path = self.config_dir / 'defaults' / 'tts-token' / 'token-bag-script.lua'
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
        
        self.logger.info(f"Generated token bag for {team_name} with {len(token_objects)} tokens from output_v3")
        return token_bag, token_timestamp
