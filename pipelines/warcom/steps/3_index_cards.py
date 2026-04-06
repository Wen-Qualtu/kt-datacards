"""
Step 3: Index Cards and Tokens

**PRIMARY INDEXING STEP - ALL DETECTION LOGIC LIVES HERE**

This is the intelligence layer that analyzes all extracted PDFs/PNGs and creates
comprehensive indexes. All downstream steps (4a, 4b, 6, etc.) are simple executors
that read these indexes and perform actions with NO classification logic.

Responsibilities:
1. Card Classification:
   - Detect card types (datacards, equipment, faction-rules, token-guide, ploys, operative-selection)
   - Detect orientation (landscape/portrait)
   - Extract card names from text
   - Determine output folder structure

2. Card Relationships:
   - Front/back card pairs
   - Multi-card operatives (e.g., Crypteks with separate action cards)
   - Special layouts (2-column action pages)
   - "ACTIONS ARE PRESENTED ON THEIR OWN CARDS" pattern detection

3. Token Matching:
   - Match extracted tokens to text labels via proximity analysis
   - Look up configured shapes from team config
   - Filter out custom tokens
   - Validate all tokens have names and shapes

4. Metadata:
   - Content hashing for change detection
   - Relative file paths (workspace root)
   - Last modified timestamps

Input:  layers/warcom/extracted/{team}/cards/*.pdf
        layers/warcom/extracted/{team}/tokens/*.png
        config/team-config.yaml
Output: metadata/{team}/card_index.json
        metadata/{team}/token_index.json
"""

import argparse
import hashlib
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import fitz  # PyMuPDF
import numpy as np
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file content."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]  # First 16 chars for compactness


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF file."""
    try:
        doc = fitz.open(pdf_path)
        text = doc[0].get_text()
        doc.close()
        return text
    except Exception as e:
        logger.warning(f"Failed to extract text from {pdf_path}: {e}")
        return ""


def extract_text_blocks_sorted(pdf_path: Path) -> List[str]:
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


def is_notes_card(text: str) -> bool:
    """Check if card is a NOTES card (should be skipped)."""
    text_clean = text.strip().upper().replace(':', '').strip()
    return text_clean == 'NOTES'


def classify_card_type(text: str, lines: List[str], orientation: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Classify a card and extract its name.
    
    Key rules:
    - NOTES cards are skipped first
    - LANDSCAPE cards are ALWAYS datacards
    - PORTRAIT cards are classified by header text
    
    Args:
        text: Raw text from card
        lines: Sorted text lines from card
        orientation: 'landscape' or 'portrait'
    
    Returns:
        Tuple of (card_type, card_name)
    """
    # Check for NOTES cards first
    if is_notes_card(text):
        return ('notes', None)
    
    # LANDSCAPE cards are ALWAYS datacards
    if orientation == 'landscape':
        # Extract name from first meaningful text block
        card_name = extract_datacard_name(lines)
        return ('datacards', card_name)
    
    # PORTRAIT cards: classify by header structure
    # Check for operative selection first (special pattern)
    text_upper = text.upper()
    first_part = text_upper[:300]
    has_kill = 'KILL' in first_part
    has_team = 'TEAM' in first_part
    has_archetypes = 'ARCHETYPE' in text_upper
    
    if has_kill and has_team and has_archetypes:
        return ('operative-selection', 'operatives')
    
    # All other portrait cards: extract type from line 1 (header)
    card_type = extract_card_type_from_header(lines)
    if card_type:
        card_name = extract_portrait_card_name(lines, card_type)
        return (card_type, card_name)
    
    return (None, None)


def extract_card_type_from_header(lines: List[str]) -> Optional[str]:
    """
    Extract card type from header structure.
    Portrait cards have: line 0 = TEAM, line 1 = TYPE, line 2 = NAME
    
    Args:
        lines: Text lines from the card
    
    Returns:
        Card type folder name or None if not recognized
    """
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


def extract_datacard_name(lines: List[str]) -> Optional[str]:
    """Extract name from landscape datacard."""
    for line in lines[:10]:  # Check first 10 lines
        line_upper = line.upper()
        
        # Skip stat keywords
        if line_upper in ['APL', 'WOUNDS', 'SAVE', 'MOVE', 'GA', 'DF', 'SV']:
            continue
        
        # Skip pure numbers or stat values
        if re.match(r'^[\d"+\s]+$', line):
            continue
        
        # Name is usually all caps, reasonable length
        if line.isupper() and 5 <= len(line) <= 50:
            # Filter out likely keywords lines
            if ',' in line and line.count(',') > 2:
                continue
            return line.strip()
    
    return None


def extract_portrait_card_name(lines: List[str], card_type: str) -> Optional[str]:
    """Extract name from portrait card (line 2 for most types)."""
    # Token-guide always returns 'token-guide'
    if card_type == 'token-guide':
        return 'token-guide'
    
    # Check for multi-option faction rules (ACCURSED GIFTS, SANGUAVITAE)
    first_line = lines[0] if lines else ''
    if first_line in ['ACCURSED GIFTS', 'SANGUAVITAE']:
        # Look for option number or name in next few lines
        for line in lines[1:6]:
            # Check for numbered option like "1. Deformed Wings"
            option_match = re.match(r'^(\d+)\.?\s+(.+)', line)
            if option_match:
                option_name = option_match.group(2).strip()
                option_name = re.sub(r'[^A-Z0-9\s\-]', '', option_name)
                if option_name:
                    return f"{first_line.lower().replace(' ', '-')}-{option_name.lower().replace(' ', '-')}"
            # Check for non-numbered option name
            elif line and line not in ['WHEN', 'EFFECT', 'GOREMONGER', 'CHAOS CULT']:
                option_name = re.sub(r'[^A-Z0-9\s\-]', '', line)
                if option_name:
                    return f"{first_line.lower().replace(' ', '-')}-{option_name.lower().replace(' ', '-')}"
        # Fallback
        return first_line.lower().replace(' ', '-')
    
    # Regular portrait card: name is at line 2 (index 2)
    if len(lines) >= 3:
        name = lines[2]
        name = re.sub(r'[^A-Z0-9\s\-]', '', name)
        name = name.strip()
        if name:
            return name.lower().replace(' ', '-')
    
    return None


# ============================================================================
# TOKEN MATCHING FUNCTIONS
# ============================================================================

def load_team_config(config_path: Path) -> Dict:
    """Load team configuration from YAML."""
    if not config_path.exists():
        logger.warning(f"Team config not found at {config_path}")
        return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data.get('teams', {}) if data else {}
    except Exception as e:
        logger.warning(f"Could not load team config: {e}")
        return {}


def get_token_shape(team_config: Dict, token_name: str) -> Optional[str]:
    """Get the configured shape for a token.
    
    Args:
        team_config: Team configuration dict
        token_name: Token name (e.g., 'Breach marker', 'Omniscanner token')
    
    Returns:
        Shape string ('round', 'octagon', 'diamond', 'operative') or None
    """
    tokens = team_config.get('tokens', [])
    if not tokens:
        return None
    
    # Normalize for matching
    def normalize_name(name: str) -> str:
        norm = ' '.join(name.lower().split())
        for suffix in [' token', ' marker', ' tokens', ' markers']:
            if norm.endswith(suffix):
                norm = norm[:-len(suffix)].strip()
        return norm
    
    search_norm = normalize_name(token_name)
    
    for token_cfg in tokens:
        cfg_name = token_cfg.get('name', '')
        cfg_norm = normalize_name(cfg_name)
        
        if search_norm == cfg_norm:
            return token_cfg.get('shape')
    
    return None


def detect_token_shape_from_image(image_path: Path) -> str:
    """Auto-detect token shape from image analysis.
    
    Analyzes the token image to determine if it's round or operative shaped.
    Diamond and octagon shapes are rare (only 2 recent teams) and should be 
    configured explicitly in team-config.yaml.
    
    Args:
        image_path: Path to token image file
    
    Returns:
        Shape string: 'round' or 'operative' (never 'diamond' or 'octagon')
    """
    try:
        import cv2
        import numpy as np
        
        img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            return 'round'  # Default fallback
        
        h, w = img.shape
        
        # Find content (non-white pixels)
        content_mask = (img < 250).astype(np.uint8)
        
        if content_mask.sum() == 0:
            return 'round'
        
        # Get bounding box
        ys, xs = np.where(content_mask > 0)
        if len(xs) == 0:
            return 'round'
        
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        content_w = x1 - x0 + 1
        content_h = y1 - y0 + 1
        
        # Calculate aspect ratio
        aspect_ratio = content_w / max(content_h, 1)
        
        # Operative tokens are wide/tall (aspect != 1.0)
        # Round/octagon/diamond tokens are square (aspect ~1.0)
        #
        # For square tokens, we default to 'round' since:
        # - Most teams use round tokens
        # - Diamond/octagon are only in 2 recent teams
        # - Config should explicitly specify diamond/octagon if needed
        if abs(aspect_ratio - 1.0) < 0.15:
            return 'round'  # Default for square-ish tokens
        else:
            return 'operative'  # Non-square tokens
    
    except Exception:
        return 'round'  # Safe fallback


def match_tokens_to_names(
    tokens: List[Dict],
    text_elements: List[Dict],
    team_config: Dict = None
) -> Tuple[Dict[str, str], List[str]]:
    """Match tokens to their names using 1-to-1 assignment via proximity.
    
    Filters out text elements matching custom token names from config BEFORE matching.
    
    Args:
        tokens: List of token dicts with 'filename' and 'bbox'
        text_elements: List of text elements with 'text' and 'bbox'
        team_config: Team configuration dict (for filtering custom tokens)
    
    Returns:
        Tuple of (filename -> token_name dict, list of filtered text element texts)
    """
    if not tokens or not text_elements:
        return {}, []
    
    # Filter out custom token labels BEFORE matching
    custom_token_names = set()
    if team_config:
        tokens_cfg = team_config.get('tokens', [])
        for token_cfg in tokens_cfg:
            if token_cfg.get('type') == 'custom':
                name = token_cfg.get('name', '').strip()
                if name:
                    # Normalize name for matching
                    norm = ' '.join(name.lower().split())
                    custom_token_names.add(norm)
    
    # Filter text elements to exclude custom token names
    filtered_elements = []
    filtered_custom = []
    for elem in text_elements:
        text = elem.get('text', '').strip()
        if not text:
            continue
        
        # Normalize text for comparison
        normalized = ' '.join(text.lower().split())
        for suffix in [' token', ' marker', ' tokens', ' markers']:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
                break
        
        # Check if this matches a custom token name
        if normalized in custom_token_names:
            filtered_custom.append(text)
            continue
        
        filtered_elements.append(elem)
    
    if not filtered_elements:
        return {}, filtered_custom
    
    # Now do proximity matching with filtered list
    text_elements = filtered_elements
    
    # Get coordinate ranges
    token_xs = [t['bbox']['x'] + t['bbox']['width'] / 2 for t in tokens]
    token_ys = [t['bbox']['y'] + t['bbox']['height'] / 2 for t in tokens]
    label_xs = [e['bbox']['x'] + e['bbox']['width'] / 2 for e in text_elements]
    label_ys = [e['bbox']['y'] + e['bbox']['height'] / 2 for e in text_elements]
    
    # Detect scale by comparing ranges (text is usually 2x token coordinates)
    token_x_range = max(token_xs) - min(token_xs) if len(token_xs) > 1 else 1
    label_x_range = max(label_xs) - min(label_xs) if len(label_xs) > 1 else 1
    token_y_range = max(token_ys) - min(token_ys) if len(token_ys) > 1 else 1
    label_y_range = max(label_ys) - min(label_ys) if len(label_ys) > 1 else 1
    
    x_scale_ratio = label_x_range / token_x_range if token_x_range > 1 else 1.0
    y_scale_ratio = label_y_range / token_y_range if token_y_range > 1 else 1.0
    scale_ratio = (x_scale_ratio + y_scale_ratio) / 2
    
    # Scale text coordinates to match token coordinate system
    scaled_label_xs = [x / scale_ratio for x in label_xs]
    scaled_label_ys = [y / scale_ratio for y in label_ys]
    
    # Calculate distances for all token-label pairs
    # Labels are positioned RIGHT or BELOW tokens
    max_x_distance = 600.0
    max_y_distance = 1200.0
    pairs = []  # List of (priority_score, token_idx, text_idx)
    
    for tok_idx, token in enumerate(tokens):
        token_right = token['bbox']['x'] + token['bbox']['width']
        token_bottom = token['bbox']['y'] + token['bbox']['height']
        tx = token_xs[tok_idx]
        ty = token_ys[tok_idx]
        
        for txt_idx, elem in enumerate(text_elements):
            # Only match tokens and labels from same source card
            if token.get('source_card') != elem.get('source_card'):
                continue
            
            ex = scaled_label_xs[txt_idx]
            ey = scaled_label_ys[txt_idx]
            
            # Text must be RIGHT or BELOW token (not left or above)
            if ex < token_right and ey < token_bottom:
                continue
            
            dx = ex - tx
            dy = ey - ty
            dx_abs = abs(dx)
            dy_abs = abs(dy)
            
            if dx_abs > max_x_distance or dy_abs > max_y_distance:
                continue
            
            # Prioritize alignment based on label position
            if dy > 30:  # Label below
                priority = (dx_abs * 1.5) + (dy_abs * 0.3)
            else:  # Label to right
                priority = (dy_abs * 1.5) + (dx_abs * 0.3)
            
            pairs.append((priority, tok_idx, txt_idx))
    
    # Sort by priority (best matches first)
    pairs.sort(key=lambda x: x[0])
    
    # Greedy assignment
    assigned_tokens = set()
    assigned_texts = set()
    result = {}
    
    for dist, tok_idx, txt_idx in pairs:
        if tok_idx in assigned_tokens or txt_idx in assigned_texts:
            continue
        
        token = tokens[tok_idx]
        label = text_elements[txt_idx]
        result[token['filename']] = label['text']
        
        assigned_tokens.add(tok_idx)
        assigned_texts.add(txt_idx)
    
    return result, filtered_custom


# ============================================================================
# CARD RELATIONSHIP DETECTION
# ============================================================================


def detect_special_actions_card(text: str, operative_name: str = None) -> bool:
    """
    Detect if a card is a special 2-column actions layout.
    
    Pattern: "{OPERATIVE_NAME} ACTIONS" header with 2 columns of actions
    """
    if not text:
        return False
    
    # Check for "XXX ACTIONS" pattern
    if operative_name:
        pattern = f"{operative_name.upper()} ACTIONS"
        if pattern in text.upper():
            return True
    
    # Generic check for any "{NAME} ACTIONS" pattern
    if re.search(r'\b[A-Z]+\s+ACTIONS\b', text):
        # Verify it has action content (AP costs)
        if re.search(r'\d+AP', text):
            return True
    
    return False


def detect_reference_to_separate_actions(text: str) -> Optional[str]:
    """
    Detect if a card references separate action cards.
    
    Pattern: "XXX ACTIONS ARE PRESENTED ON THEIR OWN CARDS"
    Returns the operative name if found, None otherwise.
    """
    pattern = r'([A-Z]+)\s+ACTIONS\s+ARE\s+PRESENTED\s+ON\s+THEIR\s+OWN\s+CARDS'
    match = re.search(pattern, text.upper())
    if match:
        return match.group(1)
    return None


def detect_reference_to_separate_option_cards(text: str) -> bool:
    """
    Detect if a card references separate option/rule cards.
    
    Patterns:
    - "CHAPTER TACTIC OPTIONS ARE PRESENTED ON THEIR OWN CARD"
    - "OPTIONS ARE PRESENTED ON THEIR OWN CARDS"
    - Similar patterns indicating multi-card sets
    
    Returns True if this card has options on separate cards.
    """
    if not text:
        return False
    
    # Normalize text: remove line breaks and extra spaces
    text_normalized = ' '.join(text.upper().split())
    
    patterns = [
        'OPTIONS ARE PRESENTED ON THEIR OWN CARD',
        'OPTION ARE PRESENTED ON THEIR OWN CARD',
        'ARE PRESENTED ON THEIR OWN CARD',
        'PRESENTED ON THEIR OWN CARD'
    ]
    
    return any(pattern in text_normalized for pattern in patterns)


def detect_continues_on_back(text: str) -> bool:
    """
    Detect if a card continues on the back side.
    
    Pattern: "CONTINUES ON THE OTHER SIDE" or similar
    """
    if not text:
        return False
    
    text_upper = text.upper()
    patterns = [
        'CONTINUES ON THE OTHER SIDE',
        'CONTINUES ON OTHER SIDE',
        'CONTINUE ON THE OTHER SIDE',
        'CONTINUED ON THE OTHER SIDE'
    ]
    
    return any(pattern in text_upper for pattern in patterns)


def get_card_orientation(pdf_path: Path) -> str:
    """Determine if card is landscape or portrait from filename."""
    if '_landscape.pdf' in str(pdf_path):
        return 'landscape'
    elif '_portrait.pdf' in str(pdf_path):
        return 'portrait'
    return 'unknown'


def extract_operative_name_from_card(text: str, orientation: str) -> Optional[str]:
    """
    Extract operative name from card text.
    
    For landscape datacards: Usually in first or last significant text block
    """
    if not text:
        return None
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    if orientation == 'landscape':
        # Look for name patterns - often all-caps, not too long
        for line in lines:
            # Skip headers, stats, keywords
            if any(skip in line.upper() for skip in ['NAME', 'ATK', 'HIT', 'DMG', 'APL', 'WOUNDS', 'SAVE', 'MOVE']):
                continue
            if any(skip in line.upper() for skip in ['KILL TEAM', 'FACTION', 'EQUIPMENT']):
                continue
            
            # Name is usually all caps, 2-4 words, reasonable length
            if line.isupper() and 5 <= len(line) <= 50:
                # Filter out likely keywords lines
                if ',' in line and line.count(',') > 2:  # Likely keywords
                    continue
                return line.strip()
    
    return None


def index_team_cards(team_name: str, source_dir: Path, output_dir: Path, base_dir: Path = None) -> Dict:
    """
    Create index of all cards for a team (landscape AND portrait).
    
    Args:
        team_name: Team name
        source_dir: Source directory (e.g., layers/warcom/extracted root)
        output_dir: Output directory (e.g., output root)
        base_dir: Base directory for relative paths (default: current directory)
    
    Returns index structure with card relationships and metadata.
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    source_cards_dir = source_dir / team_name / 'cards'
    output_cards_dir = output_dir / team_name / 'cards'
    
    if not source_cards_dir.exists():
        logger.error(f"Source directory not found: {source_cards_dir}")
        return None
    
    # Get all PDFs sorted by page number
    landscape_pdfs = sorted(source_cards_dir.glob('*_landscape.pdf'))
    portrait_pdfs = sorted(source_cards_dir.glob('*_portrait.pdf'))
    
    logger.info(f"Found {len(landscape_pdfs)} landscape cards, {len(portrait_pdfs)} portrait cards")
    
    # Build index
    index = {
        'team': team_name,
        'generated': datetime.now(timezone.utc).isoformat(),
        'operatives': [],  # Landscape datacards with relationships
        'other_cards': []  # Portrait cards (equipment, ploys, etc.)
    }
    
    # Index landscape datacards (operatives with relationships)
    i = 0
    while i < len(landscape_pdfs):
        pdf_path = landscape_pdfs[i]
        text = extract_text_from_pdf(pdf_path)
        
        # Get corresponding PNG
        png_path = pdf_path.with_suffix('.png')
        
        # Check if this card references separate action cards
        referenced_actions = detect_reference_to_separate_actions(text)
        
        # Extract operative name
        operative_name = extract_operative_name_from_card(text, 'landscape')
        if referenced_actions:
            operative_name = referenced_actions  # Use the name from the reference
        
        if not operative_name:
            logger.warning(f"Could not extract operative name from {pdf_path.name}")
            operative_name = f"UNKNOWN_{i}"
        
        logger.info(f"  Card {i+1}: {operative_name}")
        
        # Build operative entry
        operative = {
            'name': operative_name,
            'cards': [],
            'needs_default_backs': False  # Will be set to True if no backs found
        }
        
        # Add main card (front)
        main_card = {
            'type': 'front',
            'layout': 'standard',
            'source_pdf': str(pdf_path.relative_to(base_dir)),
            'source_png': str(png_path.relative_to(base_dir)),
            'content_hash': compute_file_hash(pdf_path),
            'last_modified': datetime.fromtimestamp(pdf_path.stat().st_mtime, timezone.utc).isoformat()
        }
        
        operative['cards'].append(main_card)
        
        # Check if next card is action(s) for this operative
        if referenced_actions:
            logger.info(f"    → Looking for {referenced_actions} action cards...")
            
            # Scan ahead for action cards
            j = i + 1
            action_count = 0
            while j < len(landscape_pdfs):
                next_pdf = landscape_pdfs[j]
                next_text = extract_text_from_pdf(next_pdf)
                
                # Check if this is an action card for this operative
                if detect_special_actions_card(next_text, referenced_actions):
                    action_count += 1
                    logger.info(f"    → Found action card {action_count}: {next_pdf.name}")
                    
                    next_png = next_pdf.with_suffix('.png')
                    
                    action_card = {
                        'type': f'actions_{action_count}',
                        'layout': 'special_actions_2column',
                        'source_pdf': str(next_pdf.relative_to(base_dir)),
                        'source_png': str(next_png.relative_to(base_dir)),
                        'content_hash': compute_file_hash(next_pdf),
                        'last_modified': datetime.fromtimestamp(next_pdf.stat().st_mtime, timezone.utc).isoformat()
                    }
                    
                    operative['cards'].append(action_card)
                    j += 1
                else:
                    # Not an action card for this operative, stop searching
                    break
            
            # Skip processed action cards
            i = j
        else:
            # Check if next card is a back side (standard operative)
            if i + 1 < len(landscape_pdfs):
                next_pdf = landscape_pdfs[i + 1]
                next_text = extract_text_from_pdf(next_pdf)
                
                # Check if it's a back card (has actions/abilities but not a new operative)
                # Back cards typically don't have weapon stats or new operative names
                has_weapons = 'ATK' in next_text and 'HIT' in next_text
                has_stats = 'APL' in next_text and 'WOUNDS' in next_text and 'SAVE' in next_text
                is_new_operative = has_weapons and has_stats
                
                if not is_new_operative:
                    # Likely a back card
                    logger.info(f"    → Found back card: {next_pdf.name}")
                    
                    next_png = next_pdf.with_suffix('.png')
                    
                    back_card = {
                        'type': 'back',
                        'layout': 'standard',
                        'source_pdf': str(next_pdf.relative_to(base_dir)),
                        'source_png': str(next_png.relative_to(base_dir)),
                        'content_hash': compute_file_hash(next_pdf),
                        'last_modified': datetime.fromtimestamp(next_pdf.stat().st_mtime, timezone.utc).isoformat()
                    }
                    
                    operative['cards'].append(back_card)
                    i += 2  # Skip the back card
                else:
                    i += 1
            else:
                i += 1
        
        # Check if operative has any back cards
        has_back = any(card['type'] in ['back', 'actions_1', 'actions_2'] for card in operative['cards'][1:])
        if not has_back:
            operative['needs_default_backs'] = True  # Step 4a will generate synthetic back
        
        index['operatives'].append(operative)
    
    # Index portrait cards (equipment, ploys, faction-rules, etc.)
    # Process with front/back relationship detection AND multi-card sets
    i = 0
    while i < len(portrait_pdfs):
        pdf_path = portrait_pdfs[i]
        text = extract_text_from_pdf(pdf_path)
        png_path = pdf_path.with_suffix('.png')
        
        # Extract text blocks for classification
        lines = extract_text_blocks_sorted(pdf_path)
        
        # Classify card
        card_type, card_name = classify_card_type(text, lines, 'portrait')
        
        if not card_type or card_type == 'notes':
            i += 1
            continue  # Skip notes cards and unclassified
        
        # Check if this card has options on separate cards (like faction rules)
        has_option_cards = detect_reference_to_separate_option_cards(text)
        
        if has_option_cards:
            logger.info(f"    → Found multi-card set: {card_name}")
            
            # Build entry for this multi-card set
            card_entry = {
                'type': card_type,
                'name': card_name,
                'orientation': 'portrait',
                'cards': []
            }
            
            # Add main card (front)
            main_card = {
                'type': 'front',
                'layout': 'standard',
                'source_pdf': str(pdf_path.relative_to(base_dir)),
                'source_png': str(png_path.relative_to(base_dir)),
                'content_hash': compute_file_hash(pdf_path),
                'last_modified': datetime.fromtimestamp(pdf_path.stat().st_mtime, timezone.utc).isoformat()
            }
            
            card_entry['cards'].append(main_card)
            
            # Check if main card has a back
            main_has_back = detect_continues_on_back(text)
            j = i + 1
            
            if main_has_back and j < len(portrait_pdfs):
                next_pdf = portrait_pdfs[j]
                next_text = extract_text_from_pdf(next_pdf)
                next_png = next_pdf.with_suffix('.png')
                
                # Add main card back
                main_back = {
                    'type': 'back',
                    'layout': 'standard',
                    'source_pdf': str(next_pdf.relative_to(base_dir)),
                    'source_png': str(next_png.relative_to(base_dir)),
                    'content_hash': compute_file_hash(next_pdf),
                    'last_modified': datetime.fromtimestamp(next_pdf.stat().st_mtime, timezone.utc).isoformat()
                }
                
                card_entry['cards'].append(main_back)
                j += 1
            
            # Now scan for option cards
            option_count = 0
            while j < len(portrait_pdfs):
                option_pdf = portrait_pdfs[j]
                option_text = extract_text_from_pdf(option_pdf)
                option_lines = extract_text_blocks_sorted(option_pdf)
                option_type, option_name = classify_card_type(option_text, option_lines, 'portrait')
                
                # Check if this card belongs to the same set
                # Rules:
                # 1. If it has NO type or is 'notes', skip it
                # 2. If it has DIFFERENT type AND different name, stop (new card set)
                # 3. If it has SAME type AND same name, it's part of set (continuation card)
                # 4. If it has NO clear header (option_type is None), assume it's continuation
                
                if option_type == 'notes':
                    j += 1
                    continue
                
                # If we got a valid classification AND it's different, stop
                if option_type and option_name and (option_type != card_type or option_name != card_name):
                    # This is a different card - end of set
                    break
                
                # Either:
                # - Same type/name (faction-rules/chapter-tactics) → continuation
                # - No type/name (couldn't classify) → likely continuation card without main header
                # Both cases: treat as option card in the set
                
                # Check if this option card has "continue on other side"
                option_has_back = detect_continues_on_back(option_text)
                
                option_count += 1
                logger.info(f"        → Option card {option_count}: {option_pdf.name}")
                
                # Add option card (front)
                option_png = option_pdf.with_suffix('.png')
                option_card = {
                    'type': f'option_{option_count}',
                    'layout': 'pair' if option_has_back else 'single',
                    'source_pdf': str(option_pdf.relative_to(base_dir)),
                    'source_png': str(option_png.relative_to(base_dir)),
                    'content_hash': compute_file_hash(option_pdf),
                    'last_modified': datetime.fromtimestamp(option_pdf.stat().st_mtime, timezone.utc).isoformat()
                }
                
                card_entry['cards'].append(option_card)
                j += 1
                
                # If option has back, add it
                if option_has_back and j < len(portrait_pdfs):
                    option_back_pdf = portrait_pdfs[j]
                    option_back_png = option_back_pdf.with_suffix('.png')
                    
                    option_back_card = {
                        'type': f'option_{option_count}_back',
                        'layout': 'standard',
                        'source_pdf': str(option_back_pdf.relative_to(base_dir)),
                        'source_png': str(option_back_png.relative_to(base_dir)),
                        'content_hash': compute_file_hash(option_back_pdf),
                        'last_modified': datetime.fromtimestamp(option_back_pdf.stat().st_mtime, timezone.utc).isoformat()
                    }
                    
                    card_entry['cards'].append(option_back_card)
                    j += 1
            
            index['other_cards'].append(card_entry)
            i = j  # Skip all processed cards in the set
            continue
        
        # Not a multi-card set - process as normal single or front/back pair
        # Check if this card continues on the back
        has_back = detect_continues_on_back(text)
        
        if has_back and i + 1 < len(portrait_pdfs):
            # Check if next card has same name (confirming it's the back)
            next_pdf = portrait_pdfs[i + 1]
            next_text = extract_text_from_pdf(next_pdf)
            next_lines = extract_text_blocks_sorted(next_pdf)
            next_type, next_name = classify_card_type(next_text, next_lines, 'portrait')
            
            # If names match (or next card doesn't have clear type), treat as back
            if next_name == card_name or not next_type or next_type == card_type:
                logger.info(f"    → Found front/back pair: {card_name}")
                
                next_png = next_pdf.with_suffix('.png')
                
                # Create entry with front and back cards
                card_entry = {
                    'type': card_type,
                    'name': card_name,
                    'orientation': 'portrait',
                    'cards': [
                        {
                            'type': 'front',
                            'layout': 'standard',
                            'source_pdf': str(pdf_path.relative_to(base_dir)),
                            'source_png': str(png_path.relative_to(base_dir)),
                            'content_hash': compute_file_hash(pdf_path),
                            'last_modified': datetime.fromtimestamp(pdf_path.stat().st_mtime, timezone.utc).isoformat()
                        },
                        {
                            'type': 'back',
                            'layout': 'standard',
                            'source_pdf': str(next_pdf.relative_to(base_dir)),
                            'source_png': str(next_png.relative_to(base_dir)),
                            'content_hash': compute_file_hash(next_pdf),
                            'last_modified': datetime.fromtimestamp(next_pdf.stat().st_mtime, timezone.utc).isoformat()
                        }
                    ]
                }
                
                index['other_cards'].append(card_entry)
                i += 2  # Skip both front and back
                continue
        
        # Single-sided card (needs default back to be generated)
        card_entry = {
            'type': card_type,
            'name': card_name,
            'orientation': 'portrait',
            'source_pdf': str(pdf_path.relative_to(base_dir)),
            'source_png': str(png_path.relative_to(base_dir)),
            'content_hash': compute_file_hash(pdf_path),
            'last_modified': datetime.fromtimestamp(pdf_path.stat().st_mtime, timezone.utc).isoformat(),
            'needs_default_back': True  # Step 4a will generate synthetic back
        }
        
        index['other_cards'].append(card_entry)
        i += 1
    
    logger.info(f"  Indexed {len(index['other_cards'])} portrait cards")
    
    return index


def index_team_tokens(team_name: str, source_dir: Path, config_path: Path, base_dir: Path = None) -> Optional[Dict]:
    """
    Create index of all tokens for a team by matching them to names and shapes.
    
    Args:
        team_name: Team name
        source_dir: Source directory (e.g., layers/warcom/extracted root)
        config_path: Path to team config YAML
        base_dir: Base directory for relative paths (default: current directory)
    
    Returns:
        Token index structure or None if no tokens
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    tokens_dir = source_dir / team_name / 'tokens'
    metadata_path = tokens_dir / f'{team_name}_tokens_metadata.json'
    
    if not tokens_dir.exists() or not metadata_path.exists():
        logger.info("  No tokens found for this team")
        return None
    
    # Load token metadata from step 2b
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    except Exception as e:
        logger.warning(f"  Failed to load token metadata: {e}")
        return None
    
    tokens = metadata.get('tokens', [])
    text_elements = metadata.get('text_elements', [])
    
    if not tokens:
        logger.info("  No tokens in metadata")
        return None
    
    logger.info(f"  Found {len(tokens)} tokens to index")
    
    # Load team config for shape lookup
    all_teams_config = load_team_config(config_path)
    team_config = all_teams_config.get(team_name, {})
    
    # Match tokens to names
    token_names, filtered_custom = match_tokens_to_names(tokens, text_elements, team_config)
    
    logger.info(f"  Matched {len(token_names)} tokens to names")
    if filtered_custom:
        logger.info(f"  Filtered {len(filtered_custom)} custom token labels:")
        for label in filtered_custom:
            logger.info(f"    - {label}")
    for fname, name in token_names.items():
        logger.debug(f"    {fname} → {name}")
    
    # Build token index
    index = {
        'team': team_name,
        'generated': datetime.now(timezone.utc).isoformat(),
        'tokens': []
    }
    
    # Track validation issues
    unmatched = []
    missing_config = []
    
    for token in tokens:
        filename = token['filename']
        
        # Check if matched to a name
        if filename not in token_names:
            unmatched.append(filename)
            continue
        
        token_name = token_names[filename]
        
        # Look up shape from config (REQUIRED - no fallbacks)
        config_shape = get_token_shape(team_config, token_name)
        
        if not config_shape:
            logger.warning(f"  ⚠ Token '{token_name}' not found in config - SKIPPING")
            missing_config.append((filename, token_name))
            continue
        
        # Add to index
        token_entry = {
            'name': token_name,
            'shape': config_shape,
            'source_file': str((tokens_dir / filename).relative_to(base_dir)),
            'bbox': token['bbox'],
            'area': token.get('area', 0)
        }
        
        index['tokens'].append(token_entry)
    
    # Report validation issues
    if unmatched:
        logger.warning(f"  ⚠ {len(unmatched)} tokens not matched to names")
        for fname in unmatched:
            logger.warning(f"    - {fname}")
    
    if missing_config:
        logger.error(f"  ✗ {len(missing_config)} tokens NOT IN CONFIG:")
        for fname, name in missing_config:
            logger.error(f"      '{name}' ({fname})")
        logger.error(f"  → Add these tokens to config/team-config.yaml")
    
    logger.info(f"  ✓ Indexed {len(index['tokens'])} tokens")
    
    return index if index['tokens'] else None


def run(team: str = None, base_dir: Path = None, output_dir: Path = None) -> Dict:
    """
    Main entry point for card indexing.
    
    Args:
        team: Team name to process (or None for all teams)
        base_dir: Base directory (default: current directory)
        output_dir: Root output directory (default: base_dir / 'output')
    
    Returns:
        Dictionary with processing results
    """
    if base_dir is None:
        base_dir = Path.cwd()
    if output_dir is None:
        output_dir = base_dir / 'output'
    
    # Source directory is always layers/warcom/extracted
    source_dir = base_dir / 'layers' / 'warcom' / 'extracted'
    
    # Get list of teams
    if team:
        teams = [team]
    else:
        if not source_dir.exists():
            logger.error(f"Extracted directory not found: {source_dir}")
            return {'error': 'No extracted teams found'}
        
        teams = [d.name for d in source_dir.iterdir() if d.is_dir()]
    
    results = {
        'processed': [],
        'failed': [],
        'total_operatives': 0
    }
    
    for team_name in teams:
        logger.info(f"\n{'='*60}")
        logger.info(f"Indexing cards and tokens for: {team_name}")
        logger.info(f"{'='*60}")
        
        try:
            # Index cards
            card_index = index_team_cards(team_name, source_dir, output_dir, base_dir)
            
            if card_index:
                # Save card index to metadata directory
                metadata_dir = base_dir / 'metadata' / team_name
                metadata_dir.mkdir(parents=True, exist_ok=True)
                card_index_path = metadata_dir / 'card_index.json'
                
                with open(card_index_path, 'w', encoding='utf-8') as f:
                    json.dump(card_index, f, indent=2, ensure_ascii=False)
                
                operative_count = len(card_index['operatives'])
                card_count = sum(len(op['cards']) for op in card_index['operatives'])
                
                logger.info(f"\n✓ Card index: {operative_count} operatives, {card_count} cards")
                logger.info(f"  Saved to: {card_index_path}")
                
                # Index tokens
                config_path = base_dir / 'config' / 'team-config.yaml'
                token_index = index_team_tokens(team_name, source_dir, config_path, base_dir)
                
                if token_index:
                    token_index_path = metadata_dir / 'token_index.json'
                    
                    with open(token_index_path, 'w', encoding='utf-8') as f:
                        json.dump(token_index, f, indent=2, ensure_ascii=False)
                    
                    token_count = len(token_index['tokens'])
                    logger.info(f"\n✓ Token index: {token_count} tokens")
                    logger.info(f"  Saved to: {token_index_path}")
                
                results['processed'].append(team_name)
                results['total_operatives'] += operative_count
            else:
                logger.error(f"✗ Failed to index {team_name}")
                results['failed'].append(team_name)
        
        except Exception as e:
            logger.error(f"✗ Error processing {team_name}: {e}", exc_info=True)
            results['failed'].append(team_name)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"INDEX COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Processed: {len(results['processed'])} teams")
    logger.info(f"Total operatives: {results['total_operatives']}")
    if results['failed']:
        logger.info(f"Failed: {len(results['failed'])} teams")
    
    return results


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description='Index cards and create relationship manifest'
    )
    parser.add_argument(
        '--team',
        help='Specific team to process (default: all teams)'
    )
    parser.add_argument(
        '--base-dir',
        type=Path,
        help='Base directory (default: current directory)'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        help='Output directory root (default: ./output)'
    )
    
    args = parser.parse_args()
    
    results = run(
        team=args.team,
        base_dir=getattr(args, 'base_dir', None),
        output_dir=args.output_dir
    )
    
    # Exit with error code if any failures
    if results.get('failed'):
        sys.exit(1)


if __name__ == '__main__':
    main()
