"""
Step 4: Extract Card Images

Converts PDF cards to JPEG images based on structure.json classification.
Reads the classified structure and converts each card (front/back) to JPEG at 300 DPI.
Ensures every card has both front and back images (using default backside if needed).

Card images are saved as JPEG (not PNG) for significantly smaller file sizes (~3.5x).
Token images remain PNG elsewhere in the pipeline as they require transparency.

Input:
    layers/kt-app/classified/{team}/structure.json
    
Output:
    output_v3/{team}/cards/{card_type}/{name}-front.jpg
    output_v3/{team}/cards/{card_type}/{name}-back.jpg
    (or with card numbers: {name}-card{N}-front.jpg, {name}-card{N}-back.jpg)
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import fitz  # PyMuPDF
import shutil

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Default backside paths
DEFAULT_BACKSIDE_PORTRAIT = PROJECT_ROOT / "config" / "defaults" / "card-backside" / "default-backside-portrait.jpg"
DEFAULT_BACKSIDE_LANDSCAPE = PROJECT_ROOT / "config" / "defaults" / "card-backside" / "default-backside-landscape.jpg"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


JPEG_QUALITY = 90  # JPEG quality for card images (0-100). 90 gives good quality at ~3.5x smaller than PNG.

class CardImageExtractor:
    """Extracts JPEG images from classified PDF cards."""
    
    def __init__(self, dpi: int = 300):
        """
        Args:
            dpi: Resolution for PNG extraction (default 300)
        """
        self.dpi = dpi
        self.zoom = dpi / 72  # PDF uses 72 DPI base
        self.current_team = None  # Track current team for backside lookup
        
    def process_team(self, team: str) -> bool:
        """
        Process a single team: convert all classified cards to PNG.
        
        Args:
            team: Team slug
            
        Returns:
            True if successful
        """
        self.current_team = team  # Set current team for backside lookup
        structure_path = PROJECT_ROOT / "layers" / "kt-app" / "classified" / team / "structure.json"
        
        if not structure_path.exists():
            logger.error(f"  Structure file not found: {structure_path}")
            return False
        
        # Load structure
        try:
            with open(structure_path, 'r', encoding='utf-8') as f:
                structure = json.load(f)
        except Exception as e:
            logger.error(f"  Failed to load structure: {e}")
            return False
        
        # Process each card type
        total_extracted = 0
        card_types = [
            'datacards',
            'operatives_selection', 
            'faction_rules',
            'equipment',
            'firefight_ploys',
            'strategy_ploys',
            'token_guide'
        ]
        
        for card_type in card_types:
            if card_type not in structure:
                continue
                
            entities = structure[card_type]
            if not entities:
                continue
            
            # Create output directory
            output_dir = PROJECT_ROOT / "output_v3" / team / "cards" / card_type
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract images for each entity
            for entity in entities:
                name = entity.get('name', 'UNKNOWN')
                cards = entity.get('cards', [])
                
                # Check if entity has multiple cards (need card numbers in filenames)
                needs_card_numbers = len(cards) > 1
                
                for card_idx, card in enumerate(cards, 1):
                    # Build base filename
                    sanitized = self._sanitize_filename(name)
                    
                    # Naming rule:
                    # - datacards: Use operative name as-is (no team prefix)
                    #   Example: "VOIDSCARRED FELARCH" -> "voidscarred-felarch"
                    # - All other cards: Add team prefix
                    #   Example: "FOREGRIP" -> "kasrkin-foregrip"
                    #           "OPERATIVE SELECTION KASRKIN" -> "kasrkin-operative-selection"
                    
                    if card_type == 'datacards':
                        # Datacards: use operative name as-is (no prefix)
                        base_name = sanitized
                    else:
                        # All other cards: add team prefix if not present
                        if not sanitized.startswith(f"{team}-"):
                            # Remove team suffix if present (e.g., "operative-selection-kasrkin")
                            if sanitized.endswith(f"-{team}"):
                                sanitized = sanitized[:-len(team)-1]
                            # Add team prefix
                            sanitized = f"{team}-{sanitized}"
                        base_name = sanitized
                    
                    # Add card number if multiple cards
                    if needs_card_numbers:
                        base_name = f"{base_name}-card{card_idx}"
                    
                    # Extract front card
                    front_extracted = False
                    if 'front' in card:
                        front_path = PROJECT_ROOT / card['front']
                        if front_path.exists():
                            output_path = output_dir / f"{base_name}-front.jpg"
                            if self._extract_pdf_to_jpg(front_path, output_path):
                                total_extracted += 1
                                front_extracted = True
                    
                    # Extract or copy back card
                    if 'back' in card:
                        back_path = PROJECT_ROOT / card['back']
                        if back_path.exists():
                            output_path = output_dir / f"{base_name}-back.jpg"
                            if self._extract_pdf_to_jpg(back_path, output_path):
                                total_extracted += 1
                    elif front_extracted:
                        # No back card - copy default backside
                        # Datacards are landscape; all other card types are portrait
                        output_path = output_dir / f"{base_name}-back.jpg"
                        if self._copy_default_backside(output_path, is_portrait=(card_type != 'datacards')):
                            total_extracted += 1
        
        logger.info(f"  Extracted {total_extracted} card images")
        return True
    
    def _extract_pdf_to_jpg(self, pdf_path: Path, output_path: Path) -> bool:
        """
        Convert single-page PDF to JPEG.
        
        Args:
            pdf_path: Path to source PDF
            output_path: Path to output JPEG
            
        Returns:
            True if successful
        """
        try:
            doc = fitz.open(pdf_path)
            page = doc[0]  # Single-page PDF
            
            # Convert to JPEG at specified DPI (no alpha channel needed for cards)
            mat = fitz.Matrix(self.zoom, self.zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Save as JPEG
            pix.save(output_path, jpg_quality=JPEG_QUALITY)
            doc.close()
            
            return True
            
        except Exception as e:
            logger.error(f"  Failed to convert {pdf_path.name}: {e}")
            return False
    
    def _copy_default_backside(self, output_path: Path, is_portrait: bool = True) -> bool:
        """
        Copy default backside image to output location.
        Checks for team-specific backside first, then falls back to default.
        
        Args:
            output_path: Path to output PNG
            is_portrait: True for portrait orientation, False for landscape
            
        Returns:
            True if successful
        """
        try:
            # Check for team-specific backside first
            orientation = "portrait" if is_portrait else "landscape"
            
            # Try multiple team-specific backside patterns:
            # 1. config/teams/{team}/card-backside/{team}-backside-{orientation}.jpg
            # 2. config/teams/{team}/card-backside/default-backside-{orientation}.jpg
            team_backside_patterns = [
                PROJECT_ROOT / "config" / "teams" / self.current_team / "card-backside" / f"{self.current_team}-backside-{orientation}.jpg",
                PROJECT_ROOT / "config" / "teams" / self.current_team / "card-backside" / f"default-backside-{orientation}.jpg",
            ]
            
            backside_path = None
            for pattern in team_backside_patterns:
                if pattern.exists():
                    backside_path = pattern
                    # logger.debug(f"  Using team-specific backside: {pattern.name}")
                    break
            
            if not backside_path:
                # Fall back to global default backside
                backside_path = DEFAULT_BACKSIDE_PORTRAIT if is_portrait else DEFAULT_BACKSIDE_LANDSCAPE
                # logger.debug(f"  Using default backside: {backside_path.name}")
            
            if not backside_path.exists():
                logger.error(f"  Backside not found: {backside_path}")
                return False
            
            # Convert source backside to JPEG at correct DPI
            if backside_path.suffix.lower() in ('.jpg', '.jpeg', '.png'):
                doc = fitz.open(backside_path)
                page = doc[0]
                
                mat = fitz.Matrix(self.zoom, self.zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                pix.save(output_path, jpg_quality=JPEG_QUALITY)
                doc.close()
            else:
                shutil.copy2(backside_path, output_path)
            
            return True
            
        except Exception as e:
            logger.error(f"  Failed to copy backside: {e}")
            return False
    
    def _sanitize_filename(self, name: str) -> str:
        """
        Convert card name to safe filename.
        
        Args:
            name: Card name
            
        Returns:
            Sanitized filename (lowercase, hyphenated)
        """
        # Remove special characters, convert to lowercase
        safe_name = name.lower()
        safe_name = safe_name.replace(' ', '-')
        safe_name = safe_name.replace('/', '-')
        safe_name = safe_name.replace('\\', '-')
        safe_name = safe_name.replace(':', '-')
        safe_name = safe_name.replace('*', '-')
        safe_name = safe_name.replace('?', '-')
        safe_name = safe_name.replace('"', '')
        safe_name = safe_name.replace("'", '')
        safe_name = safe_name.replace('<', '-')
        safe_name = safe_name.replace('>', '-')
        safe_name = safe_name.replace('|', '-')
        
        # Remove multiple consecutive hyphens
        while '--' in safe_name:
            safe_name = safe_name.replace('--', '-')
        
        return safe_name.strip('-')


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Step 4: Extract card images (PDF to PNG)')
    parser.add_argument('--teams', help='Comma-separated list of team slugs to process')
    parser.add_argument('--dpi', type=int, default=300, help='Image resolution (default: 300)')
    parser.add_argument('--force', action='store_true', help='Force re-extraction of all images')
    
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("Step 4: Extract Card Images")
    logger.info("=" * 70)
    
    # Get team list
    if args.teams:
        teams = [t.strip() for t in args.teams.split(',')]
    else:
        # Process all teams with structure files
        classified_dir = PROJECT_ROOT / "layers" / "kt-app" / "classified"
        teams = sorted([d.name for d in classified_dir.iterdir() if d.is_dir() and (d / "structure.json").exists()])
    
    logger.info(f"Teams to process: {len(teams)}")
    logger.info("")
    
    # Process teams
    extractor = CardImageExtractor(dpi=args.dpi)
    processed = 0
    failed = 0
    
    for team in teams:
        logger.info(f"Processing {team}")
        
        if extractor.process_team(team):
            processed += 1
        else:
            failed += 1
    
    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("Step 4 Complete!")
    logger.info(f"  Processed: {processed}")
    logger.info(f"  Failed: {failed}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
