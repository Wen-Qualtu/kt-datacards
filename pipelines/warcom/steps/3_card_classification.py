"""
Step 3: Card Classification and Organization

Analyzes extracted cards and organizes them into the output structure by card type.
Uses text analysis and pattern matching to identify:
- datacards
- equipment  
- faction-rules
- token-guide
- ploys/firefight
- ploys/strategy
- operative-selection

Input:  layers/warcom/extracted/{team}/cards/*.png
Output: output/{team}/cards/{type}/*.png
"""

import argparse
import json
import logging
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import fitz  # PyMuPDF
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not available, OCR will be limited")


class CardClassifier:
    """Classifies Kill Team cards by type using text analysis and pattern matching."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize card classifier.
        
        Args:
            config_path: Optional path to team config for validation
        """
        self.config_path = config_path
        self.team_names = self._load_team_names() if config_path else {}
    
    def _load_team_names(self) -> Dict[str, str]:
        """Load team names from config for validation."""
        import yaml
        
        if not self.config_path or not self.config_path.exists():
            return {}
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                teams = data.get('teams', {})
                return {slug: info.get('name', slug) for slug, info in teams.items()}
        except Exception as e:
            logger.warning(f"Could not load team config: {e}")
            return {}
    
    def is_notes_card(self, text: str) -> bool:
        """Check if card is a NOTES card (should be skipped)."""
        # Notes cards only have "NOTES:" or "NOTES" as content
        text_clean = text.strip().upper().replace(':', '').strip()
        return text_clean == 'NOTES'
    
    def extract_text_from_card_pdf(self, pdf_path: Path) -> str:
        """
        Extract text from a card PDF file.
        
        Args:
            pdf_path: Path to card PDF
        
        Returns:
            Extracted text from the card
        """
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return ""
            
            # Extract text from the single page
            text = doc[0].get_text()
            doc.close()
            
            return text
        except Exception as e:
            logger.warning(f"Text extraction failed for {pdf_path.name}: {e}")
            return ""
    
    def extract_text_blocks_sorted(self, pdf_path: Path) -> List[str]:
        """
        Extract text blocks from PDF sorted by position (top-to-bottom, left-to-right).
        
        Args:
            pdf_path: Path to card PDF
        
        Returns:
            List of text blocks sorted by position
        """
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return []
            
            page = doc[0]
            # Get text blocks with positions: (x0, y0, x1, y1, "text", block_no, block_type)
            blocks = page.get_text("blocks")
            doc.close()
            
            # Sort by Y position (top to bottom), then X position (left to right)
            sorted_blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
            
            # Extract just the text, split into lines and clean
            text_lines = []
            for block in sorted_blocks:
                text = block[4].strip()
                if text:
                    # Split block into lines
                    for line in text.split('\n'):
                        line = line.strip()
                        if line:
                            text_lines.append(line)
            
            return text_lines
        except Exception as e:
            logger.warning(f"Text block extraction failed for {pdf_path.name}: {e}")
            return []
    
    def classify_card(
        self,
        card_path: Path,
        pdf_text: Optional[Dict[int, str]] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Classify a single card and extract its name.
        
        Key rules:
        - LANDSCAPE cards are ALWAYS datacards (unless NOTES)
        - PORTRAIT cards are classified by text extracted from the card PDF
        
        Args:
            card_path: Path to card PDF
            pdf_text: DEPRECATED - Not used anymore, kept for compatibility
        
        Returns:
            Tuple of (card_type, card_name) or (None, None) if should be skipped
        """
        # Extract orientation from filename
        filename = card_path.name
        is_landscape = 'landscape' in filename.lower()
        is_portrait = 'portrait' in filename.lower()
        
        # Extract text from THIS specific card PDF
        card_text = self.extract_text_from_card_pdf(card_path)
        
        # Skip NOTES cards (can be either orientation)
        if self.is_notes_card(card_text):
            return (None, None)
        
        # LANDSCAPE cards are ALWAYS datacards
        if is_landscape:
            # For datacards, extract text blocks sorted by position
            lines = self.extract_text_blocks_sorted(card_path)
            card_name = self._extract_operative_name(lines)
            
            # Check if this card continues on the other side
            # If so, mark it so the next landscape card will be treated as the back
            if 'CONTINU' in card_text.upper():
                # Card continues, so name should not have -back suffix
                # The sequential detection will handle the next card as back
                pass
            
            return ('datacards', card_name)
        
        # PORTRAIT cards: classify by content from PDF text
        if is_portrait:
            text_upper = card_text.upper()
            text_normalized = ' '.join(text_upper.split())
            lines = [l.strip() for l in text_upper.split('\n') if l.strip()]
            
            # Priority order classification for portrait cards
            # 1. Token/Marker Guide
            if any(pattern in text_normalized for pattern in [
                'MARKER/TOKEN GUIDE',
                'MARKERTOKEN GUIDE',
                'MARKER & TOKEN GUIDE'
            ]):
                return ('token-guide', 'token-guide')
            
            # 2. Operative Selection (front/back cards)
            # Front card has: TEAMNAME KILL TEAM, then ARCHETYPES:, then OPERATIVES
            elif 'KILL TEAM' in text_normalized and 'ARCHETYPES' in text_normalized and 'OPERATIVES' in text_normalized:
                card_name = 'operative-selection'
                return ('operative-selection', card_name)
            
            # 3. Equipment (check before ploys as FACTION EQUIPMENT is more specific)
            elif re.search(r'FACTION\s+EQUIPMENT|RARE\s+EQUIPMENT', text_normalized):
                card_name = self._extract_equipment_name(lines)
                return ('equipment', card_name)
            
            # 4. Strategy Ploys
            elif re.search(r'STRATEGY\s+PLOY', text_normalized):
                card_name = self._extract_ploy_name(lines, 'STRATEGY PLOY')
                return ('ploys/strategy', card_name)
            
            # 5. Firefight Ploys
            elif re.search(r'FIREFIGHT\s+PLOY', text_normalized):
                card_name = self._extract_ploy_name(lines, 'FIREFIGHT PLOY')
                return ('ploys/firefight', card_name)
            
            # 6. Faction Rules (front/back cards)
            # Front cards have "CONTINUES ON OTHER SIDE" or "FACTION RULE" header
            elif re.search(r'FACTION\s+RULE|TAC\s+OP|CONTINUES\s+ON\s+OTHER\s+SIDE', text_normalized):
                card_name = self._extract_faction_rule_name(lines)
                # Check if this is a back card (no FACTION RULE header, follows a front card)
                is_back_card = 'CONTINUES' not in text_normalized and 'FACTION RULE' not in text_normalized
                if is_back_card:
                    # Back cards get 'back' suffix
                    return ('faction-rules', f"{card_name}-back" if card_name else None)
                return ('faction-rules', card_name)
            
            # Default for unrecognized portrait cards
            # Return None for card_name so back-card detection can work
            else:
                return ('faction-rules', None)
        
        # Unknown orientation
        return (None, None)
    
    def _looks_like_datacard(self, text: str) -> bool:
        """Check if text looks like a datacard with operative stats."""
        # Datacards have weapon tables with specific headers
        if re.search(r'NAME\s+ATK\s+HIT\s+DMG', text):
            return True
        # Or they have movement/AP stats
        if re.search(r'\d+AP', text) and re.search(r'\d+"?\s+MOVE', text):
            return True
        # Or Group Activation stat
        if re.search(r'GA\s+\d+', text):
            return True
        return False
    
    def _extract_ploy_name(self, lines: List[str], ploy_type: str) -> str:
        """Extract ploy name from text lines."""
        # Ploy name is usually RIGHT AFTER the "PLOY" marker line
        for i, line in enumerate(lines):
            if ploy_type in line:
                # Next line after PLOY marker is the ploy name
                if i + 1 < len(lines):
                    name = lines[i + 1]
                    # Clean up the name
                    name = re.sub(r'[^A-Z0-9\s\-]', '', name)
                    name = name.strip()
                    # Skip if it's too short or looks like a description
                    if name and len(name) > 3 and not any(skip in name for skip in ['DEEPLY', 'USING', 'THE', 'A ', 'AN ']):
                        return name.lower().replace(' ', '-')
        return None  # Return None if no name found
    
    def _extract_equipment_name(self, lines: List[str]) -> str:
        """Extract equipment name from text lines."""
        # Equipment name is usually RIGHT AFTER the "EQUIPMENT" marker line
        for i, line in enumerate(lines):
            if 'EQUIPMENT' in line and 'FACTION' in line:
                # Next line after EQUIPMENT marker is the equipment name
                if i + 1 < len(lines):
                    name = lines[i + 1]
                    name = re.sub(r'[^A-Z0-9\s\-]', '', name)
                    name = name.strip()
                    if name and len(name) > 3:
                        return name.lower().replace(' ', '-')
        return None
    
    def _extract_faction_rule_name(self, lines: List[str]) -> str:
        """Extract faction rule name from text lines."""
        # Faction rule name is usually RIGHT AFTER the "FACTION RULE" marker line
        for i, line in enumerate(lines):
            if 'FACTION RULE' in line or 'TAC OP' in line:
                if i + 1 < len(lines):
                    name = lines[i + 1]
                    name = re.sub(r'[^A-Z0-9\s\-]', '', name)
                    name = name.strip()
                    if name and len(name) > 3:
                        return name.lower().replace(' ', '-')
        return None
    
    def _extract_operative_name(self, lines: List[str]) -> str:
        """
        Extract operative name from datacard text blocks sorted by position.
        
        The operative name is the very first text at the top-left of the card.
        """
        # The first substantial line should be the operative name
        for line in lines[:10]:  # Check first 10 lines
            line_upper = line.upper()
            
            # Skip stat keywords that might appear at top
            if line_upper in ['APL', 'WOUNDS', 'SAVE', 'MOVE', 'GA', 'DF', 'SV']:
                continue
            
            # Skip pure numbers or stat values
            if line_upper.replace('"', '').replace("'", '').replace('+', '').strip().isdigit():
                continue
            if line_upper in ['3+', '4+', '5+', '6"', '7"', '8"', '5"', '4"']:
                continue
            
            # This should be the operative name (first meaningful text)
            if len(line) > 3 and any(c.isalpha() for c in line):
                name = line_upper
                
                # Remove team prefix if present
                for prefix in ['BATTLECLADE', 'KOMMANDOS', 'LEGIONARIES', 'PATHFINDERS', 'KASRKIN', 'BLOODED', 'NOVITIATES', 'WYRMBLADE']:
                    if name.startswith(prefix + ' '):
                        name = name[len(prefix) + 1:].strip()
                        break
                
                # Clean and format
                name = re.sub(r'[^A-Z0-9\s\-]', '', name)
                name = name.strip()
                if name and len(name) > 2:
                    return name.lower().replace(' ', '-')
        
        return None


def extract_pdf_text(pdf_path: Path) -> Dict[int, str]:
    """
    Extract text from all pages of a PDF.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        Dict mapping page numbers to extracted text
    """
    try:
        doc = fitz.open(pdf_path)
        text_by_page = {}
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            text_by_page[page_num] = text
        
        doc.close()
        return text_by_page
    
    except Exception as e:
        logger.warning(f"Error extracting PDF text: {e}")
        return {}


def _get_backside_image(team_name: str, orientation: str, config_dir: Path) -> Optional[Path]:
    """
    Get appropriate backside image for a card.
    
    Priority:
    1. Team-specific backside: config/teams/{team}/card-backside/{team}-backside-{orientation}.jpg
    2. Default backside: config/defaults/card-backside/default-backside-{orientation}.jpg
    
    Args:
        team_name: Team slug name
        orientation: 'landscape' or 'portrait'
        config_dir: Path to config directory
    
    Returns:
        Path to backside image or None if not found
    """
    # Priority 1: Team-specific backside
    team_backside = (
        config_dir / 'teams' / team_name / 'card-backside' / 
        f'{team_name}-backside-{orientation}.jpg'
    )
    if team_backside.exists():
        return team_backside
    
    # Priority 2: Default backside
    default_backside = (
        config_dir / 'defaults' / 'card-backside' / 
        f'default-backside-{orientation}.jpg'
    )
    if default_backside.exists():
        return default_backside
    
    return None


def classify_team_cards(
    team_name: str,
    extracted_dir: Path,
    archive_dir: Path,
    output_dir: Path,
    classifier: CardClassifier
) -> Dict:
    """
    Classify all cards for a single team.
    
    Args:
        team_name: Team slug
        extracted_dir: Base extracted directory (layers/warcom/extracted/)
        archive_dir: Base archive directory (layers/archive/)
        output_dir: Base output directory (output/)
        classifier: CardClassifier instance
    
    Returns:
        Dict with classification statistics
    """
    team_cards_dir = extracted_dir / team_name / 'cards'
    
    if not team_cards_dir.exists():
        return {
            'team': team_name,
            'status': 'skipped',
            'reason': 'No cards directory found',
            'cards_classified': 0
        }
    
    # Find archived PDF for text extraction
    pdf_text = {}
    team_archive = archive_dir / team_name / 'warcom'
    if team_archive.exists():
        pdfs = list(team_archive.glob('*.pdf'))
        if pdfs:
            logger.info(f"Extracting text from PDF: {pdfs[0].name}")
            pdf_text = extract_pdf_text(pdfs[0])
    
    # Get all card PDFs
    card_files = sorted(team_cards_dir.glob('*.pdf'))
    
    if not card_files:
        return {
            'team': team_name,
            'status': 'skipped',
            'reason': 'No card PDFs found',
            'cards_classified': 0
        }
    
    logger.info("=" * 60)
    logger.info(f"Processing: {team_name}")
    logger.info("=" * 60)
    logger.info(f"Cards to classify: {len(card_files)}")
    
    # Classify and organize cards
    team_output_dir = output_dir / team_name / 'cards'
    classified_count = 0
    skipped_count = 0
    type_counts = {}
    
    # Track previous card to detect front/back relationships and create backsides immediately
    prev_card_type = None
    prev_card_name = None
    skip_next_card = False  # Flag to skip next card if we already processed it as a back
    
    for idx, card_path in enumerate(card_files):
        try:
            # Skip if this card was already processed as a back card
            if skip_next_card:
                skip_next_card = False
                continue
            
            # Classify the card
            card_type, card_name = classifier.classify_card(card_path, pdf_text)
            
            # Skip if None (e.g., NOTES cards)
            if card_type is None:
                logger.info(f"Skipping NOTES card: {card_path.name}")
                skipped_count += 1
                continue
            
            # Extract page and card numbers for fallback naming
            page_match = re.search(r'page(\d+)', card_path.name)
            card_match = re.search(r'card(\d+)', card_path.name)
            page_num = page_match.group(1) if page_match else "00"
            card_num = card_match.group(1) if card_match else "0"
            
            # Build final card name with team prefix and -front suffix
            has_back_suffix = card_name and card_name.endswith('-back')
            
            if card_name:
                # If card already has -back suffix, use as-is
                if has_back_suffix:
                    final_name = f"{team_name}-{card_name}"
                else:
                    final_name = f"{team_name}-{card_name}-front"
            else:
                # Check if this might be a back card (follows a front card)
                if prev_card_type and prev_card_name:
                    # Inherit the type from previous card for back cards
                    if card_type == 'faction-rules' or card_type == prev_card_type:
                        card_type = prev_card_type  # Back card gets same type as front
                        final_name = f"{team_name}-{prev_card_name}-back"
                        has_back_suffix = True
                    else:
                        # Fallback to team + page/card identifier
                        final_name = f"{team_name}-p{page_num}c{card_num}-front"
                else:
                    # Fallback to team + page/card identifier
                    final_name = f"{team_name}-p{page_num}c{card_num}-front"
            
            # Create output directory
            type_output_dir = team_output_dir / card_type
            type_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Convert PDF to PNG and save to output location
            output_path = type_output_dir / f"{final_name}.png"
            
            # Render PDF to PNG for front card
            try:
                doc = fitz.open(card_path)
                if len(doc) > 0:
                    page = doc[0]
                    # Render at 300 DPI for high quality
                    mat = fitz.Matrix(300 / 72, 300 / 72)
                    pix = page.get_pixmap(matrix=mat)
                    pix.save(str(output_path))
                doc.close()
            except Exception as e:
                logger.warning(f"Failed to convert {card_path.name} to PNG: {e}")
                continue
            
            classified_count += 1
            type_counts[card_type] = type_counts.get(card_type, 0) + 1
            
            # Check if this card continues on the other side
            # If so, immediately process the next card as its back
            card_text = classifier.extract_text_from_card_pdf(card_path)
            if 'CONTINU' in card_text.upper() and idx + 1 < len(card_files):
                # Next card is the back of this card
                next_card_path = card_files[idx + 1]
                
                # Process back card
                back_final_name = f"{team_name}-{card_name}-back"
                back_output_path = type_output_dir / f"{back_final_name}.png"
                
                try:
                    doc = fitz.open(next_card_path)
                    if len(doc) > 0:
                        page = doc[0]
                        mat = fitz.Matrix(300 / 72, 300 / 72)
                        pix = page.get_pixmap(matrix=mat)
                        pix.save(str(back_output_path))
                    doc.close()
                    logger.debug(f"Processed back card: {back_final_name}.png")
                except Exception as e:
                    logger.warning(f"Failed to convert back card {next_card_path.name} to PNG: {e}")
                
                # Mark to skip the next card since we just processed it
                skip_next_card = True
            elif not has_back_suffix:
                # This is a front card with no continue tag
                # Create default backside immediately
                orientation = 'landscape' if card_type == 'datacards' else 'portrait'
                backside_path = _get_backside_image(team_name, orientation, Path('config'))
                
                if backside_path and backside_path.exists():
                    back_filename = f"{team_name}-{card_name}-back.png"
                    back_output_path = type_output_dir / back_filename
                    
                    try:
                        shutil.copy2(backside_path, back_output_path)
                        logger.debug(f"Created default backside: {back_filename}")
                    except Exception as e:
                        logger.warning(f"Failed to create back for {card_name}: {e}")
                else:
                    logger.warning(f"No backside image found for {team_name} ({orientation})")
            
        except Exception as e:
            logger.error(f"Error classifying {card_path.name}: {e}")
            continue
    
    logger.info(f"Classified {classified_count} cards:")
    for card_type, count in sorted(type_counts.items()):
        logger.info(f"  {card_type}: {count}")
    if skipped_count > 0:
        logger.info(f"Skipped {skipped_count} NOTES cards")
    
    return {
        'team': team_name,
        'status': 'success',
        'cards_classified': classified_count,
        'cards_skipped': skipped_count,
        'types': type_counts,
        'output_dir': str(team_output_dir)
    }


def run(
    extracted_dir: str = 'layers/warcom/extracted',
    archive_dir: str = 'layers/archive',
    output_dir: str = 'output',
    config_path: Optional[str] = 'config/team-config.yaml',
    teams: Optional[List[str]] = None,
    workers: int = 1
) -> Dict:
    """
    Classify and organize cards for all teams.
    
    Args:
        extracted_dir: Directory with extracted cards (layers/warcom/extracted/)
        archive_dir: Directory with archived PDFs (layers/archive/)
        output_dir: Base output directory (output/)
        config_path: Path to team config file
        teams: Optional list of specific teams to process
        workers: Number of concurrent workers (default: 1, sequential)
    
    Returns:
        Dict with classification statistics
    """
    extracted_path = Path(extracted_dir)
    archive_path = Path(archive_dir)
    output_path = Path(output_dir)
    config = Path(config_path) if config_path else None
    
    if not extracted_path.exists():
        logger.error(f"Extracted directory not found: {extracted_path}")
        return {'status': 'failed', 'reason': 'extracted directory not found'}
    
    # Initialize classifier
    classifier = CardClassifier(config_path=config)
    
    # Find teams to process
    if teams:
        team_dirs = [extracted_path / team for team in teams if (extracted_path / team).exists()]
    else:
        team_dirs = [d for d in extracted_path.iterdir() if d.is_dir()]
    
    if not team_dirs:
        logger.error(f"No teams found in {extracted_path}")
        return {'status': 'failed', 'reason': 'no teams found'}
    
    logger.info("=" * 60)
    logger.info("Card Classification (Step 3)")
    logger.info("=" * 60)
    logger.info(f"Extracted dir: {extracted_path}")
    logger.info(f"Archive dir: {archive_path}")
    logger.info(f"Output dir: {output_path}")
    logger.info(f"Teams: {len(team_dirs)}")
    logger.info(f"Workers: {workers}")
    logger.info("=" * 60)
    
    results = []
    
    if workers == 1:
        # Sequential processing
        for team_dir in team_dirs:
            result = classify_team_cards(
                team_dir.name,
                extracted_path,
                archive_path,
                output_path,
                classifier
            )
            results.append(result)
    else:
        # Concurrent processing
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    classify_team_cards,
                    team_dir.name,
                    extracted_path,
                    archive_path,
                    output_path,
                    classifier
                ): team_dir.name
                for team_dir in team_dirs
            }
            
            for future in as_completed(futures):
                team_name = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error processing {team_name}: {e}")
                    results.append({
                        'team': team_name,
                        'status': 'failed',
                        'reason': str(e),
                        'cards_classified': 0
                    })
    
    # Summary
    successful = [r for r in results if r.get('status') == 'success']
    failed = [r for r in results if r.get('status') == 'failed']
    skipped = [r for r in results if r.get('status') == 'skipped']
    total_cards = sum(r.get('cards_classified', 0) for r in results)
    total_skipped = sum(r.get('cards_skipped', 0) for r in results)
    
    # Aggregate type counts
    all_type_counts = {}
    for r in successful:
        for card_type, count in r.get('types', {}).items():
            all_type_counts[card_type] = all_type_counts.get(card_type, 0) + count
    
    logger.info("=" * 60)
    logger.info("Card Classification Complete")
    logger.info("=" * 60)
    logger.info(f"Teams processed: {len(results)}")
    logger.info(f"Successful: {len(successful)}")
    logger.info(f"Failed: {len(failed)}")
    logger.info(f"Skipped teams: {len(skipped)}")
    logger.info(f"Total cards classified: {total_cards}")
    logger.info(f"Total cards skipped: {total_skipped}")
    
    if all_type_counts:
        logger.info("Cards by type:")
        for card_type, count in sorted(all_type_counts.items()):
            logger.info(f"  {card_type}: {count}")
    
    if failed:
        logger.warning("Failed teams:")
        for r in failed:
            logger.warning(f"  - {r['team']}: {r.get('reason', 'unknown error')}")
    
    if skipped:
        logger.info("Skipped teams:")
        for r in skipped:
            logger.info(f"  - {r['team']}: {r.get('reason', 'unknown reason')}")
    
    return {
        'status': 'success',
        'teams_processed': len(results),
        'successful': len(successful),
        'failed': len(failed),
        'skipped': len(skipped),
        'total_cards_classified': total_cards,
        'type_counts': all_type_counts,
        'results': results
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Step 3: Classify and organize cards by type')
    parser.add_argument('--extracted-dir', default='layers/warcom/extracted',
                        help='Directory with extracted cards (default: layers/warcom/extracted)')
    parser.add_argument('--archive-dir', default='layers/archive',
                        help='Directory with archived PDFs (default: layers/archive)')
    parser.add_argument('--output-dir', default='output',
                        help='Base output directory (default: output)')
    parser.add_argument('--config', default='config/team-config.yaml',
                        help='Team config file (default: config/team-config.yaml)')
    parser.add_argument('--teams', nargs='+',
                        help='Specific teams to process (default: all)')
    parser.add_argument('--workers', type=int, default=1,
                        help='Number of concurrent workers (default: 1)')
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level (default: INFO)')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(levelname)s: %(message)s'
    )
    
    result = run(
        extracted_dir=args.extracted_dir,
        archive_dir=args.archive_dir,
        output_dir=args.output_dir,
        config_path=args.config,
        teams=args.teams,
        workers=args.workers
    )
    
    sys.exit(0 if result.get('status') == 'success' else 1)
