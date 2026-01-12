#!/usr/bin/env python3
"""
Generate output metadata YAML file - Enhanced Version

This script scans the output directory structure and filenames to generate
metadata. Loads card descriptions from team_data.json files created during extraction.
"""
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import yaml
import re
import json


class OutputMetadataGenerator:
    """Generates metadata YAML file tracking processed output"""
    
    # Card type folder names to YAML keys mapping
    CARD_TYPE_MAPPING = {
        'faction-rules': 'faction-rules',
        'strategy-ploys': ('ploys', 'strategy'),
        'firefight-ploys': ('ploys', 'firefight'),
        'equipment': 'equipment',
        'operatives': 'operative_selection',
        'operative-selection': 'operative_selection',
        'datacards': 'datacards',
        'tts': None,  # Skip TTS folder (internal use only)
        'team_data.json': None  # Skip team data file
    }
    
    def __init__(
        self,
        output_dir: Path = Path('output'),
        config_dir: Path = Path('config')
    ):
        """
        Initialize OutputMetadataGenerator
        
        Args:
            output_dir: Base output directory containing team folders
            config_dir: Config directory with team-name-mapping.yaml
        """
        self.output_dir = Path(output_dir)
        self.config_dir = Path(config_dir)
        self.logger = logging.getLogger(__name__)
        self.team_mapping = self._load_team_mapping()
        self.card_descriptions = {}  # Cache for card descriptions
    
    def _load_team_mapping(self) -> Dict[str, Any]:
        """Load team configuration from config"""
        mapping_file = self.config_dir / 'team-config.yaml'
        if not mapping_file.exists():
            self.logger.warning(f"Team config file not found: {mapping_file}")
            return {'teams': {}}
        
        with open(mapping_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data
    
    def _extract_card_name_from_filename(self, image_path: Path, team_slug: str = None) -> str:
        """
        Extract card name from filename
        
        Args:
            image_path: Path to card image
            team_slug: Team slug for detecting extraction issues
            
        Returns:
            Card name from filename
        """
        # Remove _front or _back suffix and .jpg extension
        filename_base = image_path.stem
        if filename_base.endswith('_front'):
            filename_base = filename_base[:-6]
        elif filename_base.endswith('_back'):
            filename_base = filename_base[:-5]
        
        # Detect problematic generic filenames
        generic_names = ['operatives', 'kill-team', 'faction-rule', 'markertoken-guide']
        
        # Check if filename matches team name (extraction issue)
        if team_slug:
            filename_normalized = filename_base.replace('-', '').replace('_', '').lower()
            team_normalized = team_slug.replace('-', '').replace('_', '').lower()
            
            # Check for exact match or plural variants
            if (filename_normalized == team_normalized or 
                filename_normalized + 's' == team_normalized or
                filename_normalized == team_normalized + 's'):
                self.logger.warning(f"Card name matches team name: {image_path.name}")
                return f"[NEEDS REVIEW] {filename_base.replace('-', ' ').title()}"
        
        # Check for generic names
        if filename_base in generic_names:
            self.logger.warning(f"Generic filename: {image_path.name}")
            return filename_base.replace('-', ' ').title()
        
        # Remove leading page numbers if present (e.g., "7-sharpshooter" -> "sharpshooter")
        filename_base = re.sub(r'^\d+-', '', filename_base)
        
        # Convert to title case
        return filename_base.replace('-', ' ').title()
    
    def _load_card_descriptions(self, team_path: Path) -> Dict[str, str]:
        """
        Load card descriptions from team_data.json file for a team
        
        Args:
            team_path: Path to team folder
            
        Returns:
            Dict mapping card keys (card_type/card_name) to descriptions
        """
        team_slug = team_path.name
        if team_slug in self.card_descriptions:
            return self.card_descriptions[team_slug]
        
        team_data_file = team_path / 'team_data.json'
        
        if not team_data_file.exists():
            self.logger.debug(f"No team_data.json file found for {team_slug}")
            self.card_descriptions[team_slug] = {}
            return {}
        
        try:
            with open(team_data_file, 'r', encoding='utf-8') as f:
                team_data = json.load(f)
                
                # Convert team_data structure to old format for compatibility
                # card_types -> { "datacards": { "card-name": { "content": { "description": "..." } } } }
                descriptions = {}
                for card_type, cards in team_data.get('card_types', {}).items():
                    for card_name, card_data in cards.items():
                        key = f"{card_type}/{card_name}"
                        descriptions[key] = card_data.get('content', {}).get('description', '')
                
                self.card_descriptions[team_slug] = descriptions
                return descriptions
        except Exception as e:
            self.logger.warning(f"Could not load team_data for {team_slug}: {e}")
            self.card_descriptions[team_slug] = {}
            return {}
    
    def _get_canonical_name(self, team_slug: str) -> str:
        """
        Get canonical team name from slug
        
        Args:
            team_slug: Team folder name (e.g., 'kasrkin')
            
        Returns:
            Canonical team name
        """
        # Check teams configuration for canonical name
        teams_config = self.team_mapping.get('teams', {})
        if team_slug in teams_config:
            team_data = teams_config[team_slug]
            if 'canonical_name' in team_data:
                return team_data['canonical_name']
        
        # Fallback: convert slug to title case
        return team_slug.replace('-', ' ').title()
    
    def _get_team_faction_info(self, team_slug: str) -> tuple[str, str]:
        """
        Get faction and army (subfaction) info for a team
        
        Args:
            team_slug: Team folder name
            
        Returns:
            Tuple of (faction, army)
        """
        teams_config = self.team_mapping.get('teams', {})
        if team_slug in teams_config:
            team_data = teams_config[team_slug]
            faction = team_data.get('faction', 'Unknown')
            army = team_data.get('army', 'Unknown')
            return (faction, army)
        
        return ('Unknown', 'Unknown')
    
    def _scan_card_type_folder(self, folder_path: Path, team_path: Path = None) -> Dict[str, Any]:
        """
        Scan a card type folder and extract card information
        
        Args:
            folder_path: Path to card type folder (e.g., output/kasrkin/datacards/)
            team_path: Path to team folder for description lookup
            
        Returns:
            Dict with count and cards list
        """
        # Find all front images (avoid counting front/back separately)
        front_images = sorted(folder_path.glob('*_front.jpg'))
        
        # Extract card type from folder name
        card_type = folder_path.name
        
        # Load card descriptions for this team
        team_slug = team_path.name if team_path else None
        descriptions = self._load_card_descriptions(team_path) if team_path else {}
        
        # Special handling for operative_selection (simplified)
        if card_type == 'operatives':
            card_names = [self._extract_card_name_from_filename(img, team_slug) for img in front_images]
            return {
                'total': 0,  # Would need manual entry for actual total
                'options': [],  # Would need manual entry for options
                'notes': f"{len(front_images)} operative selection card(s) - see card files for roster details",
                'card_count': len(front_images)
            }
        
        # Regular card type handling - load descriptions from JSON
        cards = []
        for front_image in front_images:
            card_name = self._extract_card_name_from_filename(front_image, team_slug)
            
            # Get description from JSON file
            description_key = f"{card_type}/{front_image.stem.replace('_front', '')}"
            description = descriptions.get(description_key, '...')
            
            cards.append({
                'name': card_name,
                'description': description
            })
        
        
        return {
            'count': len(cards),
            'cards': cards
        }
    
    def _scan_team_folder(self, team_path: Path) -> Dict[str, Any]:
        """
        Scan a team folder and generate metadata
        
        Args:
            team_path: Path to team folder (e.g., output/kasrkin/)
            
        Returns:
            Team metadata dict
        """
        team_slug = team_path.name
        canonical_name = self._get_canonical_name(team_slug)
        faction, army = self._get_team_faction_info(team_slug)
        
        self.logger.info(f"Scanning team: {canonical_name} ({team_slug})")
        
        metadata = {
            'canonical_name': canonical_name,
            'faction': faction,
            'subfaction': army,
            'last_processed': datetime.now().isoformat()
        }
        
        total_cards = 0
        
        # Scan each card type folder
        for card_type_folder in sorted(team_path.iterdir()):
            if not card_type_folder.is_dir():
                # Skip non-folder items like team_data.json
                if card_type_folder.name in self.CARD_TYPE_MAPPING:
                    continue  # Silently skip known files
                continue
            
            folder_name = card_type_folder.name
            if folder_name not in self.CARD_TYPE_MAPPING:
                self.logger.warning(f"Unknown card type folder: {folder_name}")
                continue
            
            # Skip folders that map to None (internal use only)
            if self.CARD_TYPE_MAPPING[folder_name] is None:
                continue
            
            # Get card data
            card_data = self._scan_card_type_folder(card_type_folder, team_path)
            
            # Add to total card count
            card_count = card_data.get('count', card_data.get('card_count', 0))
            total_cards += card_count
            
            # Remove internal tracking field
            if 'card_count' in card_data:
                del card_data['card_count']
            
            # Map to YAML structure
            mapping = self.CARD_TYPE_MAPPING[folder_name]
            
            if isinstance(mapping, tuple):
                # Nested structure (e.g., ploys -> strategy/firefight)
                parent_key, child_key = mapping
                if parent_key not in metadata:
                    metadata[parent_key] = {}
                metadata[parent_key][child_key] = card_data
            else:
                # Direct mapping
                metadata[mapping] = card_data
        
        # Add summary
        metadata['total_cards'] = total_cards
        metadata['complete'] = self._check_completeness(metadata)
        
        return metadata
    
    def _check_completeness(self, team_metadata: Dict[str, Any]) -> bool:
        """
        Check if team has all expected card types
        
        Args:
            team_metadata: Team metadata dict
            
        Returns:
            True if all card types present
        """
        # Expected keys in metadata
        expected = ['faction-rules', 'ploys', 'equipment', 'operative_selection', 'datacards']
        
        for key in expected:
            if key not in team_metadata:
                return False
            
            # Check ploys has both strategy and firefight
            if key == 'ploys':
                if 'strategy' not in team_metadata[key] or 'firefight' not in team_metadata[key]:
                    return False
        
        return True
    
    def generate(self) -> Dict[str, Any]:
        """
        Generate metadata for all teams in output directory
        
        Returns:
            Complete metadata dict
        """
        self.logger.info(f"Generating metadata from: {self.output_dir}")
        
        metadata = {
            'generated': datetime.now().isoformat(),
            'teams': {}
        }
        
        # Scan hierarchical structure: faction/army/team/
        for faction_path in sorted(self.output_dir.iterdir()):
            if not faction_path.is_dir():
                continue
            
            # Skip non-faction folders
            if faction_path.name in ['v2', 'metadata.yaml', 'datacards-urls.json']:
                continue
            
            # Iterate through army folders
            for army_path in sorted(faction_path.iterdir()):
                if not army_path.is_dir():
                    continue
                
                # Iterate through team folders
                for team_path in sorted(army_path.iterdir()):
                    if not team_path.is_dir():
                        continue
                    
                    team_slug = team_path.name
                    metadata['teams'][team_slug] = self._scan_team_folder(team_path)
        
        self.logger.info(f"Generated metadata for {len(metadata['teams'])} teams")
        
        return metadata
    
    def save(self, metadata: Dict[str, Any], output_path: Path = Path('output/metadata.yaml')):
        """
        Save metadata to YAML file
        
        Args:
            metadata: Metadata dict to save
            output_path: Path to output YAML file
        """
        # Create parent directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(metadata, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        self.logger.info(f"Saved metadata to: {output_path}")
    
    def generate_and_save(self, output_path: Path = Path('output/metadata.yaml')):
        """
        Generate and save metadata in one step
        
        Args:
            output_path: Path to output YAML file
        """
        metadata = self.generate()
        self.save(metadata, output_path)


def main():
    """Main entry point"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set paths relative to project root
    project_root = Path(__file__).parent.parent
    output_dir = project_root / 'output'
    config_dir = project_root / 'config'
    output_file = project_root / 'output' / 'metadata.yaml'
    
    # Generate metadata
    generator = OutputMetadataGenerator(
        output_dir=output_dir,
        config_dir=config_dir
    )
    generator.generate_and_save(output_path=output_file)


if __name__ == '__main__':
    main()
