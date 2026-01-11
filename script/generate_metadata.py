#!/usr/bin/env python3
"""
Generate output metadata YAML file - Simplified Version

This script scans the output directory structure and filenames to generate
metadata. No OCR required - all information comes from the folder/file structure.
"""
import sys
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import logging
import yaml
import re


class OutputMetadataGenerator:
    """Generates metadata YAML file tracking processed output"""
    
    # Card type folder names to YAML keys mapping
    CARD_TYPE_MAPPING = {
        'faction-rules': 'faction-rules',
        'strategy-ploys': ('ploys', 'strategy'),
        'firefight-ploys': ('ploys', 'firefight'),
        'equipment': 'equipment',
        'operatives': 'operative_selection',
        'datacards': 'datacards'
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
    
    def _load_team_mapping(self) -> Dict[str, str]:
        """Load team name mapping from config"""
        mapping_file = self.config_dir / 'team-name-mapping.yaml'
        if not mapping_file.exists():
            self.logger.warning(f"Team mapping file not found: {mapping_file}")
            return {}
        
        with open(mapping_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data.get('team_names', {})
    
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
    
    def _get_canonical_name(self, team_slug: str) -> str:
        """
        Get canonical team name from slug
        
        Args:
            team_slug: Team folder name (e.g., 'kasrkin')
            
        Returns:
            Canonical team name
        """
        # Check if this is a mapped name
        for key, value in self.team_mapping.items():
            if key == team_slug:
                return value.replace('-', ' ').title()
            if value == team_slug:
                return value.replace('-', ' ').title()
        
        # Fallback: convert slug to title case
        return team_slug.replace('-', ' ').title()
    
    def _scan_card_type_folder(self, folder_path: Path, team_slug: str = None) -> Dict[str, Any]:
        """
        Scan a card type folder and extract card information
        
        Args:
            folder_path: Path to card type folder (e.g., output/kasrkin/datacards/)
            team_slug: Team identifier for context
            
        Returns:
            Dict with count and cards list
        """
        # Find all front images (avoid counting front/back separately)
        front_images = sorted(folder_path.glob('*_front.jpg'))
        
        # Extract card type from folder name
        card_type = folder_path.name
        
        # Special handling for operative_selection (simplified - no OCR)
        if card_type == 'operatives':
            card_names = [self._extract_card_name_from_filename(img, team_slug) for img in front_images]
            return {
                'total': 0,  # Would need OCR or manual entry for actual total
                'options': [],  # Would need OCR or manual entry for options
                'notes': f"{len(front_images)} operative selection card(s) - see card files for roster details",
                'card_count': len(front_images)
            }
        
        # Regular card type handling
        cards = []
        for front_image in front_images:
            card_name = self._extract_card_name_from_filename(front_image, team_slug)
            cards.append({
                'name': card_name,
                'description': '...'  # Placeholder - would need OCR for actual descriptions
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
        
        self.logger.info(f"Scanning team: {canonical_name} ({team_slug})")
        
        metadata = {
            'canonical_name': canonical_name,
            'faction': 'Unknown',  # Could be added to config file manually
            'subfaction': 'Unknown',
            'last_processed': datetime.now().isoformat(),
            'source_pdfs': []  # Could be tracked in processing phase
        }
        
        total_cards = 0
        
        # Scan each card type folder
        for card_type_folder in sorted(team_path.iterdir()):
            if not card_type_folder.is_dir():
                continue
            
            folder_name = card_type_folder.name
            if folder_name not in self.CARD_TYPE_MAPPING:
                self.logger.warning(f"Unknown card type folder: {folder_name}")
                continue
            
            # Get card data
            card_data = self._scan_card_type_folder(card_type_folder, team_slug)
            
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
        
        # Scan each team folder
        for team_path in sorted(self.output_dir.iterdir()):
            if not team_path.is_dir():
                continue
            
            team_slug = team_path.name
            metadata['teams'][team_slug] = self._scan_team_folder(team_path)
        
        self.logger.info(f"Generated metadata for {len(metadata['teams'])} teams")
        
        return metadata
    
    def save(self, metadata: Dict[str, Any], output_path: Path = Path('output-metadata.yaml')):
        """
        Save metadata to YAML file
        
        Args:
            metadata: Metadata dict to save
            output_path: Path to output YAML file
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(metadata, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        self.logger.info(f"Saved metadata to: {output_path}")
    
    def generate_and_save(self, output_path: Path = Path('output-metadata.yaml')):
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
    output_file = project_root / 'output-metadata.yaml'
    
    # Generate metadata
    generator = OutputMetadataGenerator(
        output_dir=output_dir,
        config_dir=config_dir
    )
    generator.generate_and_save(output_path=output_file)


if __name__ == '__main__':
    main()
