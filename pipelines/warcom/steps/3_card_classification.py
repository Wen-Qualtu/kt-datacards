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


def apply_rounded_corners(image_path: Path, orientation: str = 'portrait') -> None:
    """
    Apply rounded corners to a card image using template masks.
    Shrinks template by 1% and centers it to prevent white edges.
    
    Args:
        image_path: Path to the PNG image to process
        orientation: 'landscape' for datacards, 'portrait' for other cards
    """
    try:
        # Read image with alpha channel
        img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        if img is None:
            logger.warning(f"Failed to load image for rounding: {image_path}")
            return
        
        # Get image dimensions
        height, width = img.shape[:2]
        
        # Load appropriate template
        template_name = f"template-card-{orientation}-cutter.png"
        template_path = Path('config/pipelines/warcom') / template_name
        
        if not template_path.exists():
            logger.warning(f"Template not found: {template_path}")
            return
        
        # Load template
        template = cv2.imread(str(template_path), cv2.IMREAD_UNCHANGED)
        if template is None:
            logger.warning(f"Failed to load template: {template_path}")
            return
        
        # Shrink template by 1% and center it
        scale = 0.99  # 1% smaller
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        # Resize template to 99% of card dimensions
        template_resized = cv2.resize(template, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        # Create full-size template with the smaller template centered
        template_centered = np.zeros((height, width, 4), dtype=np.uint8)
        
        # Calculate offset to center the template
        offset_y = (height - new_height) // 2
        offset_x = (width - new_width) // 2
        
        # Place resized template in center
        template_centered[offset_y:offset_y+new_height, offset_x:offset_x+new_width] = template_resized
        
        # Convert image to BGRA if needed
        if img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        
        # Apply template's alpha channel to card image
        # Where template is transparent, make card transparent
        img[:, :, 3] = template_centered[:, :, 3]
        
        # Save the image with rounded corners
        cv2.imwrite(str(image_path), img)
        
    except Exception as e:
        logger.warning(f"Failed to apply rounded corners to {image_path.name}: {e}")


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
    ) -> Tuple[Optional[str], Optional[str], str]:
        """
        Classify a single card and extract its name.
        
        Key rules:
        - Skip NOTES cards first (before any processing)
        - Orientation is determined from filename (contains 'landscape' or not)
        - LANDSCAPE cards are ALWAYS datacards
        - PORTRAIT cards are classified by text from line 2 of the card
        
        Args:
            card_path: Path to card PDF
            pdf_text: DEPRECATED - Not used anymore, kept for compatibility
        
        Returns:
            Tuple of (card_type, card_name, orientation)
            - card_type: Type of card or None if should be skipped
            - card_name: Name of card or None if should be skipped
            - orientation: 'landscape' or 'portrait'
        """
        # Extract orientation from filename (from previous step)
        orientation = 'landscape' if 'landscape' in card_path.name.lower() else 'portrait'
        
        # Extract text once and check for NOTES cards first (before any other processing)
        card_text = self.extract_text_from_card_pdf(card_path)
        if self.is_notes_card(card_text):
            return ('notes', None, orientation)
        
        # LANDSCAPE cards are ALWAYS datacards
        if orientation == 'landscape':
            # For datacards, extract text blocks sorted by position
            lines = self.extract_text_blocks_sorted(card_path)
            card_name = self._extract_name_from_card(lines, is_landscape=True)
            return ('datacards', card_name, orientation)
        
        # PORTRAIT cards: classify by header structure
        # Check for operative selection first (special pattern detection)
        # Pattern: Team name with "KILL TEAM" on line 1-2, followed by "ARCHETYPES"
        text_upper = card_text.upper()
        first_part = text_upper[:300]  # Check first ~300 chars for team name
        has_kill = 'KILL' in first_part
        has_team = 'TEAM' in first_part
        has_archetypes = 'ARCHETYPE' in text_upper  # Matches ARCHETYPE or ARCHETYPES
        
        if has_kill and has_team and has_archetypes:
            return ('operative-selection', 'operative-selection', orientation)
        
        # All other portrait cards: extract type from line 2
        lines = self.extract_text_blocks_sorted(card_path)
        card_type = self._extract_card_type_from_header(lines)
        
        if card_type:
            # Extract name from card (handles all types including token-guide)
            card_name = self._extract_name_from_card(lines, is_landscape=False)
            return (card_type, card_name, orientation)
        
        # No recognized type found
        return (None, None, orientation)
    
    def _extract_card_type_from_header(self, lines: List[str]) -> Optional[str]:
        """
        Extract card type from header structure.
        Portrait cards have: line 0 = TEAM, line 1 = TYPE, line 2 = NAME
        
        Args:
            lines: Text lines from the card
        
        Returns:
            Card type folder name or None if not recognized
        """
        # For portrait cards, type is always at line 1 (index 1)
        if len(lines) >= 2:
            type_line = lines[1].upper().strip()
            
            # Map type header text to folder names
            if 'FACTION RULE' in type_line:
                return 'faction-rules'
            elif 'MARKER' in type_line and 'TOKEN' in type_line:
                return 'token-guide'
            elif 'EQUIPMENT' in type_line:
                return 'equipment'
            elif 'FIREFIGHT PLOY' in type_line:
                return 'ploys/firefight'
            elif 'STRATEGY PLOY' in type_line:
                return 'ploys/strategy'
        
        return None
    
    def _extract_name_from_card(self, lines: List[str], is_landscape: bool = False) -> str:
        """
        Extract card name from text lines.
        
        Name extraction depends on card type:
        - Datacards (landscape): Name is the first meaningful text block (line 1)
        - Portrait cards: Name is at line 3 (line 0=TEAM, line 1=TYPE, line 2=NAME)
        - Token-guide: Always returns 'token-guide'
        - Faction rules: May have special multi-option format
        
        Args:
            lines: Text lines from the card
            is_landscape: True if this is a datacard (landscape orientation)
        
        Returns:
            Formatted card name or None if not found
        """
        if is_landscape:
            # DATACARDS: Extract name from first meaningful text block
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
                    
                    # Clean and format (keep full name as it appears on card)
                    name = re.sub(r'[^A-Z0-9\s\-]', '', name)
                    name = name.strip()
                    if name and len(name) > 2:
                        return name.lower().replace(' ', '-')
            
            return None
        else:
            # PORTRAIT CARDS: Name at line 3 (index 2)
            
            # Special case: token-guide cards always have hardcoded name
            if len(lines) >= 2:
                type_line = lines[1].upper().strip()
                if 'MARKER' in type_line and 'TOKEN' in type_line:
                    return 'token-guide'
            
            # Check for multi-option faction rules (ACCURSED GIFTS, SANGUAVITAE)
            first_line = lines[0] if lines else ''
            
            if first_line in ['ACCURSED GIFTS', 'SANGUAVITAE']:
                # Look for option number or name in the next few lines
                for line in lines[1:6]:
                    # Check for numbered option like "1. Deformed Wings"
                    option_match = re.match(r'^(\d+)\.?\s+(.+)', line)
                    if option_match:
                        option_name = option_match.group(2).strip()
                        option_name = re.sub(r'[^A-Z0-9\s\-]', '', option_name)
                        if option_name:
                            return f"{first_line.lower().replace(' ', '-')}-{option_name.lower().replace(' ', '-')}"
                    # Check for non-numbered option name (like "Rejuvenate")
                    elif line and line not in ['WHEN', 'EFFECT', 'GOREMONGER', 'CHAOS CULT']:
                        option_name = re.sub(r'[^A-Z0-9\s\-]', '', line)
                        if option_name:
                            return f"{first_line.lower().replace(' ', '-')}-{option_name.lower().replace(' ', '-')}"
                # Fallback: return base name if no option found
                return first_line.lower().replace(' ', '-')
            
            # Regular portrait card: name is at line 3 (index 2)
            if len(lines) >= 3:
                name = lines[2]
                # Clean and format
                name = re.sub(r'[^A-Z0-9\s\-]', '', name)
                name = name.strip()
                if name:
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


def _has_backside_continue(card_text: str) -> bool:
    """
    Check if a card explicitly states it continues on the other side.
    
    Matches variations:
    - CONTINUE ON THE OTHER SIDE
    - CONTINUE ON OTHER SIDE
    - CONTINUES ON THE OTHER SIDE
    - CONTINUES ON OTHER SIDE
    
    Args:
        card_text: Text content of the card
    
    Returns:
        True if card has a continue statement
    """
    return bool(re.search(r'CONTINUES?\s+ON\s+(?:THE\s+)?OTHER\s+SIDE', card_text.upper()))


def _is_angels_of_death_special_case(card_text: str) -> bool:
    """
    Check if card is part of Angels of Death special ordering.
    
    Angels of Death Chapter Tactics have wrong card order in PDF:
    card3 (front), card4 (front), card1 (back of card4), card2 (back of card3)
    Should be: card3+card2, card4+card1
    
    Args:
        card_text: Text content of the card
    
    Returns:
        True if this is an AoD Chapter Tactics card
    """
    # Remove line breaks for multi-line text matching
    card_text_no_breaks = ' '.join(card_text.upper().split())
    return 'CHAPTER TACTIC OPTIONS ARE PRESENTED ON THEIR OWN CARD' in card_text_no_breaks


def _process_angels_of_death_cards(
    team_name: str,
    card_files: List[Path],
    idx: int,
    card_type: str,
    card_name: str,
    team_output_dir: Path,
    classifier,
    seen_names: Dict,
    log_buffer: List[str]
) -> Tuple[int, int]:
    """
    Process Angels of Death special card ordering.
    
    Handles the misordered Chapter Tactics cards:
    - card at idx (current): front
    - card at idx+3: back of current
    - card at idx+1: another front
    - card at idx+2: back of idx+1
    
    Args:
        team_name: Team slug
        card_files: List of all card files
        idx: Current index in card_files
        card_type: Type of current card
        card_name: Name of current card
        team_output_dir: Output directory for team
        classifier: CardClassifier instance
        seen_names: Dict tracking duplicate names
        log_buffer: List for log messages
    
    Returns:
        Tuple of (classified_count, skip_count) - how many cards processed and how many to skip
    """
    classified_count = 0
    type_output_dir = team_output_dir / card_type
    type_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process current card (idx) with back at idx+3
    if idx + 3 < len(card_files):
        back_card_path = card_files[idx + 3]
        back_final_name = f"{team_name}-{card_name}-back"
        back_output_path = type_output_dir / f"{back_final_name}.png"
        
        try:
            doc = fitz.open(back_card_path)
            if len(doc) > 0:
                page = doc[0]
                mat = fitz.Matrix(300 / 72, 300 / 72)
                pix = page.get_pixmap(matrix=mat)
                pix.save(str(back_output_path))
            doc.close()
            apply_rounded_corners(back_output_path, 'portrait')
            log_buffer.append(f"Processed AoD back card: {back_final_name}.png")
        except Exception as e:
            log_buffer.append(f"WARNING: Failed to process AoD back card: {e}")
        
        # Process next card (idx+1) as front with card at idx+2 as back
        if idx + 2 < len(card_files):
            next_front_path = card_files[idx + 1]
            next_back_path = card_files[idx + 2]
            
            # Classify next front card
            next_card_type, next_card_name, _ = classifier.classify_card(next_front_path, None)
            if next_card_type and next_card_name:
                # Handle duplicate name
                name_key = f"{next_card_type}:{next_card_name}"
                if name_key in seen_names:
                    seen_names[name_key] += 1
                    next_card_name = f"{next_card_name}-{seen_names[name_key]}"
                else:
                    seen_names[name_key] = 1
                
                # Create front
                next_type_output_dir = team_output_dir / next_card_type
                next_type_output_dir.mkdir(parents=True, exist_ok=True)
                next_front_final = f"{team_name}-{next_card_name}-front"
                next_front_output = next_type_output_dir / f"{next_front_final}.png"
                
                try:
                    doc = fitz.open(next_front_path)
                    if len(doc) > 0:
                        page = doc[0]
                        mat = fitz.Matrix(300 / 72, 300 / 72)
                        pix = page.get_pixmap(matrix=mat)
                        pix.save(str(next_front_output))
                    doc.close()
                    apply_rounded_corners(next_front_output, 'portrait')
                    
                    # Create back
                    next_back_final = f"{team_name}-{next_card_name}-back"
                    next_back_output = next_type_output_dir / f"{next_back_final}.png"
                    doc = fitz.open(next_back_path)
                    if len(doc) > 0:
                        page = doc[0]
                        mat = fitz.Matrix(300 / 72, 300 / 72)
                        pix = page.get_pixmap(matrix=mat)
                        pix.save(str(next_back_output))
                    doc.close()
                    apply_rounded_corners(next_back_output, 'portrait')
                    
                    classified_count += 1
                    log_buffer.append(f"Processed AoD card pair: {next_front_final}.png + {next_back_final}.png")
                except Exception as e:
                    log_buffer.append(f"WARNING: Failed to process AoD card pair: {e}")
    
    # Return how many cards were processed and how many to skip (3: idx+1, idx+2, idx+3)
    return classified_count, 3


def _process_card_backside(
    card_path: Path,
    next_card_path: Path,
    team_name: str,
    card_name: str,
    card_type: str,
    orientation: str,
    type_output_dir: Path,
    log_buffer: List[str]
) -> bool:
    """
    Process a card that continues on the other side.
    
    Args:
        card_path: Path to front card
        next_card_path: Path to back card
        team_name: Team slug
        card_name: Card name
        card_type: Card type
        orientation: Card orientation
        type_output_dir: Output directory for this card type
        log_buffer: List for log messages
    
    Returns:
        True if successfully processed backside
    """
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
        
        # Apply rounded corners to back card
        apply_rounded_corners(back_output_path, orientation)
        log_buffer.append(f"Processed back card: {back_final_name}.png")
        return True
    except Exception as e:
        log_buffer.append(f"WARNING: Failed to convert back card {next_card_path.name} to PNG: {e}")
        return False


def _create_default_backside(
    team_name: str,
    card_name: str,
    orientation: str,
    type_output_dir: Path,
    config_dir: Path,
    log_buffer: List[str]
) -> bool:
    """
    Create a default backside for a card.
    
    Args:
        team_name: Team slug
        card_name: Card name
        orientation: Card orientation
        type_output_dir: Output directory for this card type
        config_dir: Path to config directory
        log_buffer: List for log messages
    
    Returns:
        True if successfully created backside
    """
    backside_path = _get_backside_image(team_name, orientation, config_dir)
    
    if backside_path and backside_path.exists():
        back_filename = f"{team_name}-{card_name}-back.png"
        back_output_path = type_output_dir / back_filename
        
        try:
            shutil.copy2(backside_path, back_output_path)
            # Apply rounded corners to default backside
            apply_rounded_corners(back_output_path, orientation)
            log_buffer.append(f"Created default backside: {back_filename}")
            return True
        except Exception as e:
            log_buffer.append(f"WARNING: Failed to create back for {card_name}: {e}")
            return False
    else:
        log_buffer.append(f"WARNING: No backside image found for {team_name} ({orientation})")
        return False


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
        Dict with classification statistics and log messages
    """
    # Buffer log messages to output atomically at the end
    log_buffer = []
    
    team_cards_dir = extracted_dir / team_name / 'cards'
    
    if not team_cards_dir.exists():
        return {
            'team': team_name,
            'status': 'skipped',
            'reason': 'No cards directory found',
            'cards_classified': 0,
            'logs': []
        }
    
    # Clean up old output for this team to avoid confusion with stale files
    team_output_dir = output_dir / team_name / 'cards'
    if team_output_dir.exists():
        shutil.rmtree(team_output_dir)
        log_buffer.append(f"Cleaned old output for {team_name}")
    
    # Find archived PDF for text extraction
    pdf_text = {}
    team_archive = archive_dir / team_name / 'warcom'
    if team_archive.exists():
        pdfs = list(team_archive.glob('*.pdf'))
        if pdfs:
            log_buffer.append(f"Extracting text from PDF: {pdfs[0].name}")
            pdf_text = extract_pdf_text(pdfs[0])
    
    # Get all card PDFs
    card_files = sorted(team_cards_dir.glob('*.pdf'))
    
    if not card_files:
        return {
            'team': team_name,
            'status': 'skipped',
            'reason': 'No card PDFs found',
            'cards_classified': 0,
            'logs': log_buffer
        }
    
    log_buffer.append(f"Cards to classify: {len(card_files)}")
    
    # Classify and organize cards
    team_output_dir = output_dir / team_name / 'cards'
    classified_count = 0
    skipped_count = 0
    type_counts = {}
    
    # Skip tracking for cards already processed as backsides
    skip_next_card = 0  # Counter for how many cards to skip (0 = don't skip)
    
    # Track seen names to handle duplicates (first keeps original name, subsequent get -2, -3, etc.)
    seen_names = {}  # {base_name: count}
    
    for idx, card_path in enumerate(card_files):
        try:
            # Skip if this card was already processed as a back card
            if skip_next_card > 0:
                skip_next_card -= 1
                continue
            
            # Classify the card (returns type, name, and orientation)
            card_type, card_name, orientation = classifier.classify_card(card_path, pdf_text)
            
            # Handle NOTES cards separately (expected, not an error)
            if card_type == 'notes':
                skipped_count += 1
                continue
            
            # Skip if classification failed (this is an error condition)
            if card_type is None:
                failed_dir = Path('layers/warcom/failed') / team_name
                failed_dir.mkdir(parents=True, exist_ok=True)
                failed_card_path = failed_dir / card_path.name
                shutil.copy2(card_path, failed_card_path)
                log_buffer.append(f"ERROR: Card classification failed, copied to failed folder: {card_path.name}")
                skipped_count += 1
                continue
            
            # Check for naming issues - fail the card if name extraction failed
            if card_name is None or (card_name and 'none' in card_name.lower()):
                failed_dir = Path('layers/warcom/failed') / team_name
                failed_dir.mkdir(parents=True, exist_ok=True)
                failed_card_path = failed_dir / card_path.name
                shutil.copy2(card_path, failed_card_path)
                log_buffer.append(f"ERROR: Card naming failed, copied to failed folder: {card_path.name} (type={card_type}, name={card_name})")
                skipped_count += 1
                continue
            
            # Handle duplicate names: first keeps original, subsequent get -2, -3, etc.
            # Create a unique key combining type and name for tracking
            name_key = f"{card_type}:{card_name}"
            if name_key in seen_names:
                # This is a duplicate - increment counter and add suffix
                seen_names[name_key] += 1
                card_name = f"{card_name}-{seen_names[name_key]}"
            else:
                # First occurrence - track it
                seen_names[name_key] = 1
            
            # Build final card name: {team}-{name}-front (backsides are processed separately)
            final_name = f"{team_name}-{card_name}-front"
            
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
                
                # Apply rounded corners using template
                apply_rounded_corners(output_path, orientation)
            except Exception as e:
                log_buffer.append(f"WARNING: Failed to convert {card_path.name} to PNG: {e}")
                continue
            
            classified_count += 1
            type_counts[card_type] = type_counts.get(card_type, 0) + 1
            
            # Extract card text for special case detection
            card_text = classifier.extract_text_from_card_pdf(card_path)
            
            # Special case: Angels of Death Chapter Tactics (misordered cards)
            if _is_angels_of_death_special_case(card_text):
                aod_classified, aod_skip = _process_angels_of_death_cards(
                    team_name, card_files, idx, card_type, card_name,
                    team_output_dir, classifier, seen_names, log_buffer
                )
                classified_count += aod_classified
                skip_next_card = aod_skip
                continue
            
            # Check if this card continues on the other side
            if _has_backside_continue(card_text) and idx + 1 < len(card_files):
                # Next card is the back of this card
                next_card_path = card_files[idx + 1]
                _process_card_backside(
                    card_path, next_card_path, team_name, card_name, card_type,
                    orientation, type_output_dir, log_buffer
                )
                # Skip the next card since we just processed it as the back
                skip_next_card = 1
            else:
                # No continue statement - create default backside
                _create_default_backside(
                    team_name, card_name, orientation,
                    type_output_dir, Path('config'), log_buffer
                )
            
        except Exception as e:
            log_buffer.append(f"ERROR: Error classifying {card_path.name}: {e}")
            continue
    
    log_buffer.append(f"Classified {classified_count} cards:")
    for card_type, count in sorted(type_counts.items()):
        log_buffer.append(f"  {card_type}: {count}")
    if skipped_count > 0:
        log_buffer.append(f"Skipped {skipped_count} NOTES cards")
    
    return {
        'team': team_name,
        'status': 'success',
        'cards_classified': classified_count,
        'cards_skipped': skipped_count,
        'types': type_counts,
        'output_dir': str(team_output_dir),
        'logs': log_buffer
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
            
            # Output team logs atomically
            logger.info("=" * 60)
            logger.info(f"[TEAM: {team_dir.name}]")
            logger.info("=" * 60)
            for log_line in result.get('logs', []):
                logger.info(f"  {log_line}")
            logger.info("")
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
                    
                    # Output team logs atomically
                    logger.info("=" * 60)
                    logger.info(f"[TEAM: {team_name}]")
                    logger.info("=" * 60)
                    for log_line in result.get('logs', []):
                        logger.info(f"  {log_line}")
                    logger.info("")
                    
                except Exception as e:
                    logger.error(f"Error processing {team_name}: {e}")
                    results.append({
                        'team': team_name,
                        'status': 'failed',
                        'reason': str(e),
                        'cards_classified': 0,
                        'logs': []
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
