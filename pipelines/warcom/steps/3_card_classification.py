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
import os
import re
import shutil
import stat
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import fitz  # PyMuPDF
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)


def _handle_remove_readonly(func, path, exc_info):
    """Retry removal after making a file writable."""
    try:
        os.chmod(path, stat.S_IWRITE)
    except OSError:
        pass
    try:
        func(path)
    except OSError as exc:
        logger.warning("Failed to remove %s: %s", path, exc)


def _safe_unlink(path: Path, retries: int = 3, delay: float = 0.2) -> None:
    """Remove a file if it exists, retrying on access errors."""
    if not path.exists():
        return
    for attempt in range(retries):
        try:
            os.chmod(path, stat.S_IWRITE)
        except OSError:
            pass
        try:
            path.unlink()
            return
        except PermissionError as exc:
            if attempt == retries - 1:
                raise exc
            time.sleep(delay)

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not available, OCR will be limited")


def _inpaint_card_corners(image_path: Path, orientation: str = 'portrait', card_type: Optional[str] = None) -> None:
    """
    Use inpainting to fill corner regions and eliminate white edges.
    
    Corner radius varies by card type:
    - Landscape cards: 40 pixels
    - Portrait operative-selection: 25 pixels
    - Portrait other types: 40 pixels
    
    Args:
        image_path: Path to the JPG image to process
        orientation: 'landscape' or 'portrait'
        card_type: Optional card type for special handling (e.g., 'operative-selection')
    """
    try:
        # Determine corner radius based on card type
        if card_type == 'operative-selection':
            corner_radius = 33
        elif card_type == 'datacards':
            corner_radius = 45
        else:
            corner_radius = 40
        
        # Load image
        img = cv2.imread(str(image_path))
        if img is None:
            logger.warning(f"Failed to load image for corner inpainting: {image_path}")
            return
        
        height, width = img.shape[:2]
        
        # Create mask for corner regions (white = inpaint these areas)
        mask = np.zeros((height, width), dtype=np.uint8)
        
        # Define corner regions (circles in each corner)
        corners = [
            (0, 0),                    # Top-left
            (width - 1, 0),            # Top-right
            (0, height - 1),           # Bottom-left
            (width - 1, height - 1)    # Bottom-right
        ]
        
        # Draw circles at corners to mark regions for inpainting
        for corner_x, corner_y in corners:
            cv2.circle(mask, (corner_x, corner_y), corner_radius, 255, -1)
        
        # Perform inpainting
        result = cv2.inpaint(img, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
        
        # Save result
        cv2.imwrite(str(image_path), result, [cv2.IMWRITE_JPEG_QUALITY, 95])
        
    except Exception as e:
        logger.warning(f"Failed to inpaint corners for {image_path.name}: {e}")


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
            # Check token-guide FIRST before faction-rules (more specific pattern)
            if 'MARKER/TOKEN GUIDE' in type_line:
                return 'token-guide'
            elif 'FACTION RULE' in type_line:
                return 'faction-rules'
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


def _get_backside_image(team_name: str, orientation: str, config_dir: Path, extracted_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Get appropriate backside image for a card.
    
    Priority:
    1. Extracted icon: layers/warcom/extracted/{team}/icons/{team}-icon-{orientation}.jpg
    2. Team-specific backside: config/teams/{team}/card-backside/{team}-backside-{orientation}.jpg
    3. Default backside: config/defaults/card-backside/default-backside-{orientation}.jpg
    
    Args:
        team_name: Team slug name
        orientation: 'landscape' or 'portrait'
        config_dir: Path to config directory
        extracted_dir: Path to extracted directory (defaults to layers/warcom/extracted)
    
    Returns:
        Path to backside image or None if not found
    """
    # Priority 1: Extracted icon from step 2
    if extracted_dir is None:
        extracted_dir = Path('layers/warcom/extracted')
    
    extracted_icon = (
        extracted_dir / team_name / 'icons' / 
        f'{team_name}-icon-{orientation}.jpg'
    )
    if extracted_icon.exists():
        return extracted_icon
    
    # Priority 2: Team-specific backside
    team_backside = (
        config_dir / 'teams' / team_name / 'card-backside' / 
        f'{team_name}-backside-{orientation}.jpg'
    )
    if team_backside.exists():
        return team_backside
    
    # Priority 3: Default backside
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


def _is_three_card_special_case(team_name: str, card_text: str, card_type: str) -> bool:
    """
    Check if card is part of a 3-card special case.
    
    Several teams have 3-card groups that need special handling:
    - Elucidian Starstriders: WARRANT OF TRADE faction rule (3 cards)
    - Gellerpox: TECHNO-CURSE faction rule (3 cards)
    - Hunter Clade: Operative Selection (3 cards)
    - Hunter Clade: DOCTRINA IMPERATIVES faction rule (3 cards)
    - Pathfinders: MARKERLIGHTS faction rule (3 cards)
    
    Args:
        team_name: Team slug
        card_text: Text content of the card
        card_type: Type of the card
    
    Returns:
        True if this is a 3-card special case
    """
    card_text_upper = card_text.upper()
    
    # Elucidian Starstriders - WARRANT OF TRADE
    if team_name == 'elucidian-starstriders' and 'WARRANT OF TRADE' in card_text_upper:
        return True
    
    # Gellerpox - TECHNO-CURSE
    if team_name == 'gellerpox-infected' and 'TECHNO-CURSE' in card_text_upper:
        return True
    
    # Hunter Clade - Operative Selection
    if team_name == 'hunter-clade' and card_type == 'operative-selection':
        return True
    
    # Hunter Clade - DOCTRINA IMPERATIVES
    if team_name == 'hunter-clade' and 'DOCTRINA IMPERATIVES' in card_text_upper:
        return True
    
    # Pathfinders - MARKERLIGHTS
    if team_name == 'pathfinders' and 'MARKERLIGHTS' in card_text_upper:
        return True
    
    return False


def _is_four_card_special_case(team_name: str, card_text: str) -> bool:
    """
    Check if card is part of a 4-card special case.
    
    Two teams have 4-card groups:
    - Angels of Death: CHAPTER TACTICS faction rule (4 cards)
    - Warpcoven: BOONS OF TZEENTCH faction rule (4 cards)
    
    Args:
        team_name: Team slug
        card_text: Text content of the card
    
    Returns:
        True if this is a 4-card special case
    """
    card_text_upper = card_text.upper()
    
    # Angels of Death - CHAPTER TACTICS
    if team_name == 'angels-of-death' and 'CHAPTER TACTICS' in card_text_upper:
        return True
    
    # Warpcoven - BOONS OF TZEENTCH
    if team_name == 'warpcoven' and 'BOONS OF TZEENTCH' in card_text_upper:
        return True
    
    return False


def _is_inquisitorial_requisition_case(team_name: str, card_text: str) -> bool:
    """
    Check if card is the Inquisitorial Agents special 11-card case.
    
    This team has INQUISITORIAL REQUISITION faction rule that spans 11 cards:
    - 1 front card with continue tag
    - 1 back card
    - 4 double-sided cards (8 cards total)
    - 3 single-sided cards
    
    Args:
        team_name: Team slug
        card_text: Text content of the card
    
    Returns:
        True if this is the Inquisitorial Requisition special case
    """
    return (team_name == 'inquisitorial-agents' and 
            'INQUISITORIAL REQUISITION' in card_text.upper())


def _combine_front_and_back(
    front_path: Path,
    back_path: Path,
    team_name: str,
    card_name: str,
    card_type: str,
    orientation: str,
    output_dir: Path,
    log_buffer: List[str]
) -> bool:
    """
    Combine two cards as front and back pair.
    
    Args:
        front_path: Path to front card PDF
        back_path: Path to back card PDF
        team_name: Team slug
        card_name: Card name
        card_type: Card type
        orientation: Card orientation
        output_dir: Output directory for this card type
        log_buffer: List for log messages
    
    Returns:
        True if successfully created pair
    """
    try:
        # Hardcoded dimensions to match output_v2
        if orientation == 'landscape':
            target_width, target_height = 1430, 827
        else:  # portrait
            target_width, target_height = 827, 1430
        
        # Create front
        front_final_name = f"{team_name}-{card_name}-front"
        front_output_path = output_dir / f"{front_final_name}.jpg"
        _safe_unlink(front_output_path)
        
        doc = fitz.open(front_path)
        if len(doc) > 0:
            page = doc[0]
            # Calculate matrix to achieve target dimensions
            page_rect = page.rect
            zoom_x = target_width / page_rect.width
            zoom_y = target_height / page_rect.height
            mat = fitz.Matrix(zoom_x, zoom_y)
            pix = page.get_pixmap(matrix=mat)
            pix.pil_save(str(front_output_path), format="JPEG", optimize=True, quality=95)
        doc.close()
        _inpaint_card_corners(front_output_path, orientation, card_type)
        
        # Create back
        back_final_name = f"{team_name}-{card_name}-back"
        back_output_path = output_dir / f"{back_final_name}.jpg"
        _safe_unlink(back_output_path)
        
        doc = fitz.open(back_path)
        if len(doc) > 0:
            page = doc[0]
            page_rect = page.rect
            zoom_x = target_width / page_rect.width
            zoom_y = target_height / page_rect.height
            mat = fitz.Matrix(zoom_x, zoom_y)
            pix = page.get_pixmap(matrix=mat)
            pix.pil_save(str(back_output_path), format="JPEG", optimize=True, quality=95)
        doc.close()
        # Skip corner inpainting on backside (it's a clean icon or default)
        
        return True
    except Exception as e:
        log_buffer.append(f"WARNING: Failed to combine front/back pair: {e}")
        return False


def _process_single_card(
    card_path: Path,
    team_name: str,
    card_name: str,
    orientation: str,
    output_dir: Path,
    config_dir: Path,
    log_buffer: List[str]
) -> bool:
    """
    Process a single card with default backside.
    
    Args:
        card_path: Path to card PDF
        team_name: Team slug
        card_name: Card name
        orientation: Card orientation
        output_dir: Output directory for this card type
        config_dir: Path to config directory
        log_buffer: List for log messages
    
    Returns:
        True if successfully processed
    """
    try:
        # Hardcoded dimensions to match output_v2
        if orientation == 'landscape':
            target_width, target_height = 1430, 827
        else:  # portrait
            target_width, target_height = 827, 1430
        
        # Create front
        front_final_name = f"{team_name}-{card_name}-front"
        front_output_path = output_dir / f"{front_final_name}.jpg"
        _safe_unlink(front_output_path)
        
        doc = fitz.open(card_path)
        if len(doc) > 0:
            page = doc[0]
            # Calculate matrix to achieve target dimensions
            page_rect = page.rect
            zoom_x = target_width / page_rect.width
            zoom_y = target_height / page_rect.height
            mat = fitz.Matrix(zoom_x, zoom_y)
            pix = page.get_pixmap(matrix=mat)
            pix.pil_save(str(front_output_path), format="JPEG", optimize=True, quality=95)
        doc.close()
        _inpaint_card_corners(front_output_path, orientation)
        
        # Create default back
        _create_default_backside(
            team_name, card_name, orientation,
            output_dir, config_dir, log_buffer
        )
        
        return True
    except Exception as e:
        log_buffer.append(f"WARNING: Failed to process single card: {e}")
        return False


def _process_card_group(
    team_name: str,
    card_files: List[Path],
    idx: int,
    card_count: int,
    first_card_type: str,
    first_card_name: str,
    first_orientation: str,
    team_output_dir: Path,
    classifier,
    seen_names: Dict,
    config_dir: Path,
    log_buffer: List[str]
) -> Tuple[int, int]:
    """
    Process N-card groups generically.
    
    For 3 cards: Creates two versions with different backs: (1,2) and (1,3)
    For even numbers (4, 6, 8, etc.): Pairs cards sequentially (1,2), (3,4), (5,6), etc.
    For odd numbers > 3 (5, 7, 9, etc.): Pairs even portion, then processes last card as single with default back
    
    Args:
        team_name: Team slug
        card_files: List of all card files
        idx: Current index in card_files (first card already classified)
        card_count: Total number of cards in group (including first)
        first_card_type: Type of first card
        first_card_name: Name of first card
        first_orientation: Orientation of first card
        team_output_dir: Output directory for team
        classifier: CardClassifier instance
        seen_names: Dict tracking duplicate names
        config_dir: Path to config directory
        log_buffer: List for log messages
    
    Returns:
        Tuple of (classified_count, skip_count)
    """
    classified_count = 0
    
    if card_count == 3:
        # Special case: 3 cards = front with 2 different backs
        type_output_dir = team_output_dir / first_card_type
        type_output_dir.mkdir(parents=True, exist_ok=True)
        
        # First pair: card 1 + card 2
        if idx + 1 < len(card_files):
            if _combine_front_and_back(
                card_files[idx], card_files[idx + 1], team_name, first_card_name,
                first_card_type, first_orientation, type_output_dir, log_buffer
            ):
                classified_count += 1
        
        # Second pair: card 1 + card 3 (with -2 suffix)
        if idx + 2 < len(card_files):
            second_name = f"{first_card_name}-2"
            if _combine_front_and_back(
                card_files[idx], card_files[idx + 2], team_name, second_name,
                first_card_type, first_orientation, type_output_dir, log_buffer
            ):
                classified_count += 1
        
        return classified_count, 2  # Skip next 2 cards
    
    else:
        # Process pairs for even portion: (1,2), (3,4), (5,6), etc.
        pairs = card_count // 2
        
        for pair_idx in range(pairs):
            front_idx = idx + (pair_idx * 2)
            back_idx = front_idx + 1
            
            if back_idx >= len(card_files):
                break
            
            front_path = card_files[front_idx]
            back_path = card_files[back_idx]
            
            # For first pair, use already-classified first card info
            if pair_idx == 0:
                card_type = first_card_type
                card_name = first_card_name
                orientation = first_orientation
            else:
                # Classify subsequent cards
                card_type, card_name, orientation = classifier.classify_card(front_path, None)
                if not card_type or not card_name:
                    continue
                
                # Handle duplicate names
                name_key = f"{card_type}:{card_name}"
                if name_key in seen_names:
                    seen_names[name_key] += 1
                    card_name = f"{card_name}-{seen_names[name_key]}"
                else:
                    seen_names[name_key] = 1
            
            # Create output directory
            type_output_dir = team_output_dir / card_type
            type_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Combine front and back
            if _combine_front_and_back(
                front_path, back_path, team_name, card_name,
                card_type, orientation, type_output_dir, log_buffer
            ):
                classified_count += 1
        
        # Handle odd card count: process last card as single with default back
        if card_count % 2 == 1:
            last_idx = idx + (pairs * 2)
            if last_idx < len(card_files):
                last_path = card_files[last_idx]
                
                # Classify last card
                last_type, last_name, last_orientation = classifier.classify_card(last_path, None)
                if last_type and last_name:
                    # Handle duplicate names
                    name_key = f"{last_type}:{last_name}"
                    if name_key in seen_names:
                        seen_names[name_key] += 1
                        last_name = f"{last_name}-{seen_names[name_key]}"
                    else:
                        seen_names[name_key] = 1
                    
                    # Create output directory
                    last_output_dir = team_output_dir / last_type
                    last_output_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Process as single card with default back
                    if _process_single_card(
                        last_path, team_name, last_name, last_orientation,
                        last_output_dir, config_dir, log_buffer
                    ):
                        classified_count += 1
        
        return classified_count, card_count - 1  # Skip all but first card


def _process_inquisitorial_requisition(
    team_name: str,
    card_files: List[Path],
    idx: int,
    card_type: str,
    card_name: str,
    orientation: str,
    team_output_dir: Path,
    classifier,
    seen_names: Dict,
    config_dir: Path,
    log_buffer: List[str]
) -> Tuple[int, int]:
    """
    Process Inquisitorial Agents special 11-card INQUISITORIAL REQUISITION.
    
    Structure:
    - idx+0: Front with continue tag (page7card3)
    - idx+1: Back of idx+0 (page7card4)
    - idx+2/idx+3: Requisitioned operative pair 1 (page8card1-2)
    - idx+4/idx+5: Requisitioned operative pair 2 (page8card3-4)
    - idx+6/idx+7: Requisitioned operative pair 3 (page9card1-2)
    - idx+8: Single operative 1 (page9card3)
    - idx+9: Single operative 2 (page9card4)
    - idx+10: Single operative 3 (page10card1)
    
    Cards idx+11 (page10card2 = token-guide) and idx+12 (page10card3 = denounce) 
    are NOT part of this group and should be processed normally.
    
    Args:
        team_name: Team slug
        card_files: List of all card files
        idx: Current index in card_files (the main requisition card)
        card_type: Type of current card
        card_name: Name of current card
        orientation: Card orientation
        team_output_dir: Output directory for team
        classifier: CardClassifier instance
        seen_names: Dict tracking duplicate names
        config_dir: Path to config directory
        log_buffer: List for log messages
    
    Returns:
        Tuple of (classified_count, skip_count)
    """
    classified_count = 0
    type_output_dir = team_output_dir / card_type
    type_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process first 8 cards as 4 pairs: main faction rule (idx, idx+1) + 3 operative pairs (idx+2 through idx+7)
    group_classified, _ = _process_card_group(
        team_name, card_files, idx, 8,
        card_type, card_name, orientation,
        team_output_dir, classifier, seen_names, config_dir, log_buffer
    )
    classified_count += group_classified
    
    # Process 3 single operative cards (idx+8, idx+9, idx+10) with default backs
    # All cards in the group use the SAME type as the first card (card_type)
    for single_idx in range(3):
        card_idx = idx + 8 + single_idx
        
        if card_idx >= len(card_files):
            break
        
        single_path = card_files[card_idx]
        
        # Extract name from card, but use the group's card_type (not individual classification)
        _, single_name, single_orientation = classifier.classify_card(single_path, None)
        if single_name:
            # Handle duplicate name
            name_key = f"{card_type}:{single_name}"
            if name_key in seen_names:
                seen_names[name_key] += 1
                single_name = f"{single_name}-{seen_names[name_key]}"
            else:
                seen_names[name_key] = 1
            
            # Use the group's type_output_dir (all cards share same type)
            # Process single card with default back
            if _process_single_card(
                single_path, team_name, single_name, single_orientation,
                type_output_dir, config_dir, log_buffer
            ):
                classified_count += 1
    
    # Skip next 10 cards (idx+1 through idx+10)
    return classified_count, 10


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
    # Hardcoded dimensions to match output_v2
    if orientation == 'landscape':
        target_width, target_height = 1430, 827
    else:  # portrait
        target_width, target_height = 827, 1430
    
    back_final_name = f"{team_name}-{card_name}-back"
    back_output_path = type_output_dir / f"{back_final_name}.jpg"
    _safe_unlink(back_output_path)
    
    try:
        doc = fitz.open(next_card_path)
        if len(doc) > 0:
            page = doc[0]
            # Calculate matrix to achieve target dimensions
            page_rect = page.rect
            zoom_x = target_width / page_rect.width
            zoom_y = target_height / page_rect.height
            mat = fitz.Matrix(zoom_x, zoom_y)
            pix = page.get_pixmap(matrix=mat)
            pix.pil_save(str(back_output_path), format="JPEG", optimize=True, quality=95)
        doc.close()
        _inpaint_card_corners(back_output_path, orientation)
        
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
        back_filename = f"{team_name}-{card_name}-back.jpg"
        back_output_path = type_output_dir / back_filename
        _safe_unlink(back_output_path)
        
        try:
            shutil.copy2(backside_path, back_output_path)
            # Inpaint corners on default backside
            _inpaint_card_corners(back_output_path, orientation)
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
    # Buffer only ERROR/WARNING messages for final reporting
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
        shutil.rmtree(team_output_dir, onerror=_handle_remove_readonly)
    
    # Find archived PDF for text extraction
    pdf_text = {}
    team_archive = archive_dir / team_name / 'warcom'
    if team_archive.exists():
        pdfs = list(team_archive.glob('*.pdf'))
        if pdfs:
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
            
            # Extract card text for special case detection BEFORE processing
            card_text = classifier.extract_text_from_card_pdf(card_path)
            
            # Special case: Inquisitorial Agents 13-card INQUISITORIAL REQUISITION
            # Must be checked BEFORE rendering to avoid double-processing
            if _is_inquisitorial_requisition_case(team_name, card_text):
                inq_classified, inq_skip = _process_inquisitorial_requisition(
                    team_name, card_files, idx, card_type, card_name, orientation,
                    team_output_dir, classifier, seen_names, Path('config'), log_buffer
                )
                classified_count += inq_classified
                # Update type counts for all cards processed by special function
                for _ in range(inq_classified):
                    type_counts[card_type] = type_counts.get(card_type, 0) + 1
                skip_next_card = inq_skip
                continue
            
            # Special case: 4-card groups (Angels of Death, Warpcoven)
            if _is_four_card_special_case(team_name, card_text):
                group_classified, group_skip = _process_card_group(
                    team_name, card_files, idx, 4,
                    card_type, card_name, orientation,
                    team_output_dir, classifier, seen_names, Path('config'), log_buffer
                )
                classified_count += group_classified
                for _ in range(group_classified):
                    type_counts[card_type] = type_counts.get(card_type, 0) + 1
                skip_next_card = group_skip
                continue
            
            # Special case: 3-card groups (multiple teams)
            if _is_three_card_special_case(team_name, card_text, card_type):
                group_classified, group_skip = _process_card_group(
                    team_name, card_files, idx, 3,
                    card_type, card_name, orientation,
                    team_output_dir, classifier, seen_names, Path('config'), log_buffer
                )
                classified_count += group_classified
                for _ in range(group_classified):
                    type_counts[card_type] = type_counts.get(card_type, 0) + 1
                skip_next_card = group_skip
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
            
            # Convert PDF to JPG and save to output location
            output_path = type_output_dir / f"{final_name}.jpg"
            _safe_unlink(output_path)
            
            # Hardcoded dimensions to match output_v2
            if orientation == 'landscape':
                target_width, target_height = 1430, 827
            else:  # portrait
                target_width, target_height = 827, 1430
            
            # Render PDF to JPG for front card
            try:
                doc = fitz.open(card_path)
                if len(doc) > 0:
                    page = doc[0]
                    # Calculate matrix to achieve target dimensions
                    page_rect = page.rect
                    zoom_x = target_width / page_rect.width
                    zoom_y = target_height / page_rect.height
                    mat = fitz.Matrix(zoom_x, zoom_y)
                    pix = page.get_pixmap(matrix=mat)
                    pix.pil_save(str(output_path), format="JPEG", optimize=True, quality=95)
                doc.close()
                
                # Inpaint corners
                _inpaint_card_corners(output_path, orientation, card_type)
            except Exception as e:
                log_buffer.append(f"WARNING: Failed to convert {card_path.name} to PNG: {e}")
                continue
            
            classified_count += 1
            type_counts[card_type] = type_counts.get(card_type, 0) + 1
            
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
            logger.info(f"Processing team: {team_dir.name}...")
            result = classify_team_cards(
                team_dir.name,
                extracted_path,
                archive_path,
                output_path,
                classifier
            )
            results.append(result)
            
            # Show quick summary for this team
            if result.get('status') == 'success':
                logger.info(f"  ✓ {team_dir.name}: {result.get('cards_classified', 0)} cards classified")
            elif result.get('status') == 'failed':
                logger.error(f"  ✗ {team_dir.name}: FAILED - {result.get('reason', 'unknown')}")
            elif result.get('status') == 'skipped':
                logger.warning(f"  ⊘ {team_dir.name}: SKIPPED - {result.get('reason', 'unknown')}")
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
                    
                    # Show quick summary for this team
                    if result.get('status') == 'success':
                        logger.info(f"  ✓ {team_name}: {result.get('cards_classified', 0)} cards classified")
                    elif result.get('status') == 'failed':
                        logger.error(f"  ✗ {team_name}: FAILED - {result.get('reason', 'unknown')}")
                    elif result.get('status') == 'skipped':
                        logger.warning(f"  ⊘ {team_name}: SKIPPED - {result.get('reason', 'unknown')}")
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
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("Card Classification Complete")
    logger.info("=" * 60)
    logger.info(f"Teams processed: {len(results)}")
    logger.info(f"  ✓ Successful: {len(successful)}")
    logger.info(f"  ✗ Failed: {len(failed)}")
    logger.info(f"  ⊘ Skipped: {len(skipped)}")
    logger.info(f"Total cards classified: {total_cards}")
    logger.info(f"Total cards skipped (NOTES): {total_skipped}")
    logger.info("")
    
    if all_type_counts:
        logger.info("Cards by type:")
        for card_type, count in sorted(all_type_counts.items()):
            logger.info(f"  {card_type}: {count}")
        logger.info("")
    
    # Collect and show failed cards from logs
    failed_cards = []
    for r in successful:
        for log_line in r.get('logs', []):
            if 'ERROR:' in log_line and 'copied to failed folder' in log_line:
                failed_cards.append(f"{r['team']}: {log_line.replace('ERROR: ', '')}")
    
    if failed_cards:
        logger.error("Failed cards (classification or naming errors):")
        for card_info in failed_cards:
            logger.error(f"  - {card_info}")
        logger.info("")
    
    if failed:
        logger.error("Failed teams (processing errors):")
        for r in failed:
            logger.error(f"  - {r['team']}: {r.get('reason', 'unknown error')}")
        logger.info("")
    
    if skipped:
        logger.warning("Skipped teams:")
        for r in skipped:
            logger.warning(f"  - {r['team']}: {r.get('reason', 'unknown reason')}")
        logger.info("")
    
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
