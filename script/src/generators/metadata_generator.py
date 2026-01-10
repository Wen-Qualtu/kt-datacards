"""Metadata generation for processed output tracking"""
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import yaml
from PIL import Image
import pytesseract


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
            return data.get('teams', {})
    
    def _extract_card_name_from_image(self, image_path: Path) -> Optional[str]:
        """
        Extract card name from image using OCR
        
        Args:
            image_path: Path to card image
            
        Returns:
            Extracted card name or None if extraction fails
        """
        try:
            # Open image
            image = Image.open(image_path)
            
            # For now, use basic OCR on the whole image
            # TODO: Improve by cropping to title area only
            text = pytesseract.image_to_string(image)
            
            # Extract first non-empty line as card name
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if lines:
                # Clean up OCR artifacts
                card_name = lines[0]
                # Remove common OCR artifacts
                card_name = card_name.replace('|', 'I')
                return card_name
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Failed to extract name from {image_path}: {e}")
            return None
    
    def _get_canonical_name(self, team_slug: str) -> str:
        """
        Get canonical team name from slug
        
        Args:
            team_slug: Team folder name (e.g., 'kasrkin')
            
        Returns:
            Canonical team name
        """
        # Check mapping file first
        if team_slug in self.team_mapping:
            return self.team_mapping[team_slug]
        
        # Fallback: convert slug to title case
        return team_slug.replace('-', ' ').title()
    
    def _scan_card_type_folder(self, folder_path: Path) -> Dict[str, Any]:
        """
        Scan a card type folder and extract card information
        
        Args:
            folder_path: Path to card type folder (e.g., output/kasrkin/datacards/)
            
        Returns:
            Dict with count and cards list
        """
        # Find all front images (avoid counting front/back separately)
        front_images = sorted(folder_path.glob('*_front.jpg'))
        
        cards = []
        for front_image in front_images:
            # Extract name from image
            card_name = self._extract_card_name_from_image(front_image)
            
            if card_name:
                cards.append({
                    'name': card_name,
                    'description': '...'  # Placeholder
                })
            else:
                # Fallback to filename if OCR fails
                filename_base = front_image.stem.replace('_front', '')
                fallback_name = filename_base.replace('-', ' ').title()
                self.logger.warning(f"OCR failed for {front_image}, using filename: {fallback_name}")
                cards.append({
                    'name': fallback_name,
                    'description': '...'
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
            'faction': 'Unknown',  # TODO: Add faction detection
            'subfaction': 'Unknown',
            'last_processed': datetime.now().isoformat(),
            'source_pdfs': []  # TODO: Track source PDFs
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
            card_data = self._scan_card_type_folder(card_type_folder)
            total_cards += card_data['count']
            
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
