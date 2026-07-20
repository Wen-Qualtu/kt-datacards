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
    output/{team}/cards/{card_type}/{name}-front.jpg
    output/{team}/cards/{card_type}/{name}-back.jpg
    (or with card numbers: {name}-card{N}-front.jpg, {name}-card{N}-back.jpg)
"""

import argparse
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone
import fitz  # PyMuPDF
import shutil

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Default backside paths
DEFAULT_BACKSIDE_PORTRAIT = PROJECT_ROOT / "config" / "defaults" / "card-backside" / "default-backside-portrait.jpg"
DEFAULT_BACKSIDE_LANDSCAPE = PROJECT_ROOT / "config" / "defaults" / "card-backside" / "default-backside-landscape.jpg"

PIPELINE_METADATA_FILE = PROJECT_ROOT / "layers" / "kt-app" / "metadata.json"
OUTPUT_METADATA_FILE = PROJECT_ROOT / "output" / "metadata.json"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ===================================================================
# METADATA MANAGEMENT
# ===================================================================

class MetadataManager:
    """Manages pipeline metadata with hash-based change detection"""

    def __init__(self, metadata_file: Path):
        self.metadata_file = metadata_file
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict:
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"pipeline_version": "2.0", "last_full_run": None, "teams": {}}

    def save_metadata(self):
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)

    def compute_hash(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def update_file(self, team: str, step: str, file_key: str, file_path: Path):
        if team not in self.metadata["teams"]:
            self.metadata["teams"][team] = {"steps": {}}
        if "steps" not in self.metadata["teams"][team]:
            self.metadata["teams"][team]["steps"] = {}
        if step not in self.metadata["teams"][team]["steps"]:
            self.metadata["teams"][team]["steps"][step] = {"outputs": {}}
        if "outputs" not in self.metadata["teams"][team]["steps"][step]:
            self.metadata["teams"][team]["steps"][step]["outputs"] = {}
        file_hash = self.compute_hash(file_path)
        timestamp = datetime.now(timezone.utc).isoformat()
        self.metadata["teams"][team]["steps"][step]["outputs"][file_key] = {
            "path": str(file_path), "hash": file_hash, "modified": timestamp
        }

    def mark_step_complete(self, team: str, step: str):
        if team not in self.metadata["teams"]:
            self.metadata["teams"][team] = {"steps": {}}
        if "steps" not in self.metadata["teams"][team]:
            self.metadata["teams"][team]["steps"] = {}
        if step not in self.metadata["teams"][team]["steps"]:
            self.metadata["teams"][team]["steps"][step] = {}
        self.metadata["teams"][team]["steps"][step]["completed"] = datetime.now(timezone.utc).isoformat()


class OutputMetadataManager:
    """Manages shared output metadata across pipelines"""

    def __init__(self, metadata_file: Path):
        self.metadata_file = metadata_file
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict:
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"version": "1.0", "last_updated": None, "files": {}}

    def save_metadata(self):
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        self.metadata["last_updated"] = datetime.now(timezone.utc).isoformat()
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)

    def compute_hash(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def update_file(self, rel_path: str, file_path: Path, pipeline: str, step: str):
        file_hash = self.compute_hash(file_path)
        timestamp = datetime.now(timezone.utc).isoformat()
        self.metadata.setdefault("files", {})[rel_path] = {
            "hash": file_hash, "modified": timestamp, "pipeline": pipeline, "step": step
        }


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
            output_dir = PROJECT_ROOT / "output" / team / "cards" / card_type
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

        Priority:
          1. config/teams/{team}/card-backside/{team}-backside-{orientation}.jpg  (manual override)
          2. config/teams/{team}/card-backside/default-backside-{orientation}.jpg (manual override)
          3. layers/kt-app/extracted/{team}/card-backside/default-backside-{orientation}.jpg (auto-generated by step 5d)
          4. config/defaults/card-backside/default-backside-{orientation}.jpg     (global fallback)

        JPEG/PNG sources are copied directly (already at the correct pixel dimensions).
        PDF sources are rendered through fitz at the pipeline DPI.
        """
        try:
            orientation = "portrait" if is_portrait else "landscape"

            candidates = [
                # 1 & 2: manual overrides in config/teams/
                PROJECT_ROOT / "config" / "teams" / self.current_team / "card-backside" / f"{self.current_team}-backside-{orientation}.jpg",
                PROJECT_ROOT / "config" / "teams" / self.current_team / "card-backside" / f"default-backside-{orientation}.jpg",
                # 3: auto-generated by step 5d
                PROJECT_ROOT / "layers" / "kt-app" / "extracted" / self.current_team / "card-backside" / f"{self.current_team}-backside-{orientation}.jpg",
                # 4: global fallback
                DEFAULT_BACKSIDE_PORTRAIT if is_portrait else DEFAULT_BACKSIDE_LANDSCAPE,
            ]

            backside_path = next((p for p in candidates if p.exists()), None)

            if not backside_path:
                logger.error(f"  Backside not found for {self.current_team} ({orientation})")
                return False

            # JPEG/PNG: already at the correct pixel dimensions — copy directly.
            # PDF: render at pipeline DPI via fitz.
            if backside_path.suffix.lower() in ('.jpg', '.jpeg', '.png'):
                shutil.copy2(backside_path, output_path)
            else:
                doc = fitz.open(backside_path)
                page = doc[0]
                mat = fitz.Matrix(self.zoom, self.zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                pix.save(output_path, jpg_quality=JPEG_QUALITY)
                doc.close()

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

    # Initialize metadata managers
    pipeline_meta = MetadataManager(PIPELINE_METADATA_FILE)
    output_meta = OutputMetadataManager(OUTPUT_METADATA_FILE)

    # Process teams
    extractor = CardImageExtractor(dpi=args.dpi)
    processed = 0
    failed = 0

    for team in teams:
        logger.info(f"Processing {team}")

        if extractor.process_team(team):
            processed += 1
            # Track metadata for all card images written
            team_cards_dir = PROJECT_ROOT / "output" / team / "cards"
            if team_cards_dir.exists():
                for f in team_cards_dir.rglob("*.jpg"):
                    rel = str(f.relative_to(PROJECT_ROOT / "output")).replace("\\", "/")
                    pipeline_meta.update_file(team, "4_extract_card_images", rel, f)
                    output_meta.update_file(rel, f, "kt-app", "4_extract_card_images")
            pipeline_meta.mark_step_complete(team, "4_extract_card_images")
        else:
            failed += 1

    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("Step 4 Complete!")
    logger.info(f"  Processed: {processed}")
    logger.info(f"  Failed: {failed}")
    logger.info("=" * 70)

    # Save metadata
    pipeline_meta.metadata["last_full_run"] = datetime.now(timezone.utc).isoformat()
    pipeline_meta.save_metadata()
    output_meta.save_metadata()


if __name__ == "__main__":
    main()
