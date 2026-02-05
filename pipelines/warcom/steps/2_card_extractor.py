"""
Step 2: Extract datacards from Kill Team PDFs.
Uses template matching to detect and extract individual card images.
"""

import fitz  # PyMuPDF
from pathlib import Path
import numpy as np
import cv2
import json
import re
import shutil
import yaml
from typing import Optional, Tuple, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)


# Icon extraction coordinates (as percentage of page dimensions)
# Page 1 - Card backside icons
PORTRAIT_ICON_X1 = 0.0243
PORTRAIT_ICON_Y1 = 0.0006
PORTRAIT_ICON_X2 = 0.1620
PORTRAIT_ICON_Y2 = 0.1324

LANDSCAPE_ICON_X1 = 0.0008
LANDSCAPE_ICON_Y1 = 0.0232
LANDSCAPE_ICON_X2 = 0.1839
LANDSCAPE_ICON_Y2 = 0.1027

# Token bag icon page
TOKEN_ICON_X1 = 0.1288
TOKEN_ICON_Y1 = 0.1625
TOKEN_ICON_X2 = 0.2724
TOKEN_ICON_Y2 = 0.2613


def load_templates(template_file: Path):
    """Load card extraction templates."""
    with open(template_file) as f:
        return json.load(f)


def load_team_config(config_file: Path = None) -> Dict[str, dict]:
    """Load team configuration with aliases from team-config.yaml."""
    if config_file is None:
        config_file = Path('config/team-config.yaml')
    
    if not config_file.exists():
        return {}
    
    with open(config_file) as f:
        data = yaml.safe_load(f)
        return data.get('teams', {})


def match_team_name(extracted_name: str, team_config: Dict[str, dict]) -> Optional[str]:
    """Match extracted team name against config including aliases. Returns normalized team name or None."""
    if not team_config:
        return None
    
    # Normalize extracted name for comparison
    normalized_extracted = extracted_name.lower().replace('-', ' ').replace('_', ' ').strip()
    
    # Try exact match against canonical names
    for config_key, config_data in team_config.items():
        canonical = config_data.get('canonical_name', config_key)
        normalized_canonical = canonical.lower().replace('-', ' ').replace('_', ' ').strip()
        if normalized_extracted == normalized_canonical:
            return config_key.lower().replace(' ', '-')
    
    # Try matching against aliases
    for config_key, config_data in team_config.items():
        aliases = config_data.get('aliases', [])
        for alias in aliases:
            normalized_alias = alias.lower().replace('-', ' ').replace('_', ' ').strip()
            if normalized_extracted == normalized_alias:
                return config_key.lower().replace(' ', '-')
    
    return None


def extract_team_name_from_pdf(pdf_path: Path) -> str:
    """
    Extract team name from PDF by finding large text near 'KILL TEAM' on later pages.
    Returns the extracted team name or the PDF filename stem as fallback.
    
    NOTE: This function is fragile and may extract incorrect text. It works for now but
    should be improved for better reliability - consider checking multiple pages or using
    more specific patterns to identify team names vs other large text.
    """
    try:
        doc = fitz.open(pdf_path)
        
        # Look at last 5 pages (or all if fewer)
        start_page = max(0, len(doc) - 5)
        
        best_team_name = None
        max_font_size = 0
        
        for page_num in range(start_page, len(doc)):
            page = doc[page_num]
            
            # Get text with detailed information including font size
            text_dict = page.get_text("dict")
            
            # Extract all text blocks with font sizes
            for block in text_dict.get("blocks", []):
                if "lines" not in block:
                    continue
                
                for line in block["lines"]:
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        font_size = span.get("size", 0)
                        
                        # Skip small text or very short text
                        if font_size < 20 or len(text) < 3:
                            continue
                        
                        # Check if this is likely a team name (large text, multiple words, uppercase)
                        if font_size > max_font_size:
                            # Clean up the text
                            clean_text = text.upper().strip()
                            
                            # Skip if it's just "KILL TEAM" itself
                            if clean_text == "KILL TEAM":
                                continue
                            
                            # If it contains letters and looks like a team name
                            if re.search(r'[A-Z]{3,}', clean_text):
                                max_font_size = font_size
                                best_team_name = clean_text
        
        doc.close()
        
        if best_team_name:
            # Clean up the team name - remove "KILL TEAM" suffix if present
            best_team_name = re.sub(r'\s*KILL\s*TEAM\s*$', '', best_team_name, flags=re.IGNORECASE)
            # Remove common suffixes like "OPERATIVES", "OPERATIVE"
            best_team_name = re.sub(r'\s*OPERATIVES?\s*$', '', best_team_name, flags=re.IGNORECASE)
            # Convert to lowercase with hyphens (standard format)
            best_team_name = best_team_name.lower().replace(' ', '-').replace('_', '-')
            # Remove any non-alphanumeric except hyphens
            best_team_name = re.sub(r'[^a-z0-9-]', '', best_team_name)
            return best_team_name
        
    except Exception as e:
        logger.warning(f"  Warning: Could not extract team name: {e}")
    
    # Fallback to filename
    return pdf_path.stem


def find_markers(img: np.ndarray, marker_template: np.ndarray, threshold: float = 0.55) -> list:
    """
    Find + markers in the image using edge-based template matching.
    Returns list of (x, y, confidence) tuples.
    """
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply Canny edge detection
    edges = cv2.Canny(gray, 50, 150)
    
    # Template match on edges
    result = cv2.matchTemplate(edges, marker_template, cv2.TM_CCOEFF_NORMED)
    
    # Find matches above threshold
    locations = np.where(result >= threshold)
    
    # Get marker centers with confidence
    markers = []
    h, w = marker_template.shape
    for pt in zip(*locations[::-1]):
        confidence = result[pt[1], pt[0]]
        center_x = int(pt[0] + w / 2)
        center_y = int(pt[1] + h / 2)
        markers.append((center_x, center_y, confidence))
    
    # Deduplicate markers within 30 pixels
    if markers:
        markers = sorted(markers, key=lambda m: m[2], reverse=True)
        unique_markers = []
        for marker in markers:
            is_duplicate = False
            for existing in unique_markers:
                dx = abs(marker[0] - existing[0])
                dy = abs(marker[1] - existing[1])
                if dx < 30 and dy < 30:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_markers.append(marker)
        markers = unique_markers
    
    return markers


def extract_template_markers(template: dict) -> list:
    """Extract all marker positions from a template (from card corners)."""
    markers = []
    for card in template['cards']:
        # Each card has 4 corners
        markers.append(tuple(card['top_left']) + (1.0,))
        markers.append(tuple(card['top_right']) + (1.0,))
        markers.append(tuple(card['bottom_left']) + (1.0,))
        markers.append(tuple(card['bottom_right']) + (1.0,))
    
    # Deduplicate (shared corners between cards) - keep first occurrence
    unique = []
    seen_positions = set()
    for marker in markers:
        pos = (marker[0], marker[1])
        if pos not in seen_positions:
            seen_positions.add(pos)
            unique.append(marker)
    
    return unique


def find_kill_team_page(pdf_path: Path) -> int:
    """
    Find the page with large "KILL TEAM" text (operatives list page).
    
    This page has:
    - Team name followed by "KILL TEAM" in large text
    - Dark background
    - Operative list
    
    Args:
        pdf_path: Path to team PDF
    
    Returns:
        Page number (0-indexed) or -1 if not found
    """
    try:
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Get text with font information
            text_dict = page.get_text("dict")
            
            # Look for large text containing "KILL TEAM"
            for block in text_dict.get("blocks", []):
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        # Check if line has large font size (typically > 20)
                        for span in line.get("spans", []):
                            text = span.get("text", "").upper()
                            size = span.get("size", 0)
                            
                            # Look for "KILL TEAM" in large text (size > 20)
                            if "KILL TEAM" in text and size > 20:
                                doc.close()
                                return page_num
        
        doc.close()
        return -1
        
    except Exception as e:
        logger.warning(f"Error finding KILL TEAM page: {e}")
        return -1


def extract_icons_from_pdf(pdf_path: Path, output_dir: Path, team_name: str) -> dict:
    """
    Extract team icons from PDF for card backsides and token bag.
    
    Extracts:
    - Portrait icon from page 1 (for portrait card backsides)
    - Landscape icon from page 1 (for landscape card backsides)
    - Token bag icon from KILL TEAM page
    
    Args:
        pdf_path: Path to team PDF
        output_dir: Directory to save icons (will create icons/ subdirectory)
        team_name: Team slug name
    
    Returns:
        Dict with extraction results
    """
    icons_dir = output_dir / 'icons'
    icons_dir.mkdir(parents=True, exist_ok=True)
    
    extracted = {
        'portrait': False,
        'landscape': False,
        'token': False
    }
    
    try:
        doc = fitz.open(pdf_path)
        
        # Extract from page 1 (card backside icons)
        if len(doc) > 0:
            page = doc[0]
            
            # Render at 5x DPI for high quality card backsides
            mat = fitz.Matrix(5.0, 5.0)
            pix = page.get_pixmap(matrix=mat)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
            page_width = pix.width
            page_height = pix.height
            
            # Extract portrait icon
            port_x1 = int(page_width * PORTRAIT_ICON_X1)
            port_y1 = int(page_height * PORTRAIT_ICON_Y1)
            port_x2 = int(page_width * PORTRAIT_ICON_X2)
            port_y2 = int(page_height * PORTRAIT_ICON_Y2)
            
            portrait_icon = img[port_y1:port_y2, port_x1:port_x2]
            portrait_path = icons_dir / f'{team_name}-icon-portrait.jpg'
            cv2.imwrite(str(portrait_path), portrait_icon, [cv2.IMWRITE_JPEG_QUALITY, 95])
            extracted['portrait'] = True
            
            # Extract landscape icon
            land_x1 = int(page_width * LANDSCAPE_ICON_X1)
            land_y1 = int(page_height * LANDSCAPE_ICON_Y1)
            land_x2 = int(page_width * LANDSCAPE_ICON_X2)
            land_y2 = int(page_height * LANDSCAPE_ICON_Y2)
            
            landscape_icon = img[land_y1:land_y2, land_x1:land_x2]
            landscape_path = icons_dir / f'{team_name}-icon-landscape.jpg'
            cv2.imwrite(str(landscape_path), landscape_icon, [cv2.IMWRITE_JPEG_QUALITY, 95])
            extracted['landscape'] = True
        
        # Find and extract token bag icon
        page_num = find_kill_team_page(pdf_path)
        
        if page_num != -1:
            page = doc[page_num]
            
            # Render at 5x DPI for high quality
            mat = fitz.Matrix(5.0, 5.0)
            pix = page.get_pixmap(matrix=mat)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
            page_width = pix.width
            page_height = pix.height
            
            # Extract token bag icon
            tok_x1 = int(page_width * TOKEN_ICON_X1)
            tok_y1 = int(page_height * TOKEN_ICON_Y1)
            tok_x2 = int(page_width * TOKEN_ICON_X2)
            tok_y2 = int(page_height * TOKEN_ICON_Y2)
            
            token_icon = img[tok_y1:tok_y2, tok_x1:tok_x2]
            token_path = icons_dir / f'{team_name}-icon-token.jpg'
            cv2.imwrite(str(token_path), token_icon, [cv2.IMWRITE_JPEG_QUALITY, 95])
            extracted['token'] = True
        
        doc.close()
        
    except Exception as e:
        logger.warning(f"Error extracting icons for {team_name}: {e}")
    
    return extracted


def is_token_guide_card(page: fitz.Page, card_coords: dict) -> bool:
    """
    Detect if a portrait card is a token/marker guide card.
    
    Checks if the first line of text equals "MARKER/TOKEN GUIDE".
    
    Args:
        page: PyMuPDF page object
        card_coords: Card corner coordinates
    
    Returns:
        True if this is a token guide card
    """
    # Calculate card bounding box in PDF points
    x1, y1 = card_coords['top_left']
    x2, y2 = card_coords['top_right']
    x3, y3 = card_coords['bottom_left']
    x4, y4 = card_coords['bottom_right']
    
    pdf_scale = 72 / 300.0  # Convert from template coords (300 DPI) to PDF points (72 DPI)
    left = min(x1, x3) * pdf_scale
    top = min(y1, y2) * pdf_scale
    right = max(x2, x4) * pdf_scale
    bottom = max(y3, y4) * pdf_scale
    
    clip_rect = fitz.Rect(left, top, right, bottom)
    
    # Extract text from card
    text = page.get_text("text", clip=clip_rect)
    
    # Split into lines and check first row
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    if len(lines) >= 1:
        first_line = lines[0].upper()
        # Check if first line contains "MARKER/TOKEN GUIDE"
        return 'MARKER' in first_line or 'TOKEN GUIDE' in first_line
    
    return False


def extract_tokens_from_card(
    card_img: np.ndarray,
    page: fitz.Page,
    card_coords: dict,
    output_dir: Path,
    card_filename_base: str,
    skip_header_percent: float = 15.0,
    min_token_area: int = 3000,
    extract_dpi: int = 300
) -> dict:
    """
    Extract individual tokens from a token guide card at high resolution.
    
    Detects token locations using the rendered card image, then extracts
    the actual token regions directly from the PDF at higher DPI.
    
    Args:
        card_img: Card image for detection (BGR, typically 150 DPI)
        page: PyMuPDF page object
        card_coords: Card corner coordinates (at template 300 DPI)
        output_dir: Directory to save extracted tokens
        card_filename_base: Base filename (e.g., "page06_card1")
        skip_header_percent: Percentage of top to skip
        min_token_area: Minimum contour area
        extract_dpi: DPI for extracting final tokens from PDF
    
    Returns:
        Dict with extraction metadata
    """
    height, width = card_img.shape[:2]
    
    # Skip header area for detection
    skip_rows = int(height * (skip_header_percent / 100))
    img_no_header = card_img[skip_rows:, :]
    
    # Convert to grayscale
    gray = cv2.cvtColor(img_no_header, cv2.COLOR_BGR2GRAY)
    
    # Apply threshold
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Morphological operations
    kernel = np.ones((5, 5), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=3)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)
    
    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter by area and aspect ratio
    token_contours = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area >= min_token_area:
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            
            if 0.3 <= aspect_ratio <= 2.5:
                token_contours.append((contour, area, x, y, w, h))
    
    # Sort by position (top to bottom, left to right)
    token_contours.sort(key=lambda x: (x[3], x[2]))
    
    # Calculate card region in PDF coordinates
    x1, y1 = card_coords['top_left']
    x2, y2 = card_coords['top_right']
    x3, y3 = card_coords['bottom_left']
    x4, y4 = card_coords['bottom_right']
    
    pdf_scale = 72 / 300.0
    card_left = min(x1, x3) * pdf_scale
    card_top = min(y1, y2) * pdf_scale
    card_right = max(x2, x4) * pdf_scale
    card_bottom = max(y3, y4) * pdf_scale
    card_rect = fitz.Rect(card_left, card_top, card_right, card_bottom)
    
    # Render card at high DPI for extraction
    mat = fitz.Matrix(extract_dpi / 72, extract_dpi / 72)
    pix = page.get_pixmap(matrix=mat, clip=card_rect)
    high_res_img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    
    if pix.n == 4:  # RGBA
        high_res_img = cv2.cvtColor(high_res_img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:  # RGB
        high_res_img = cv2.cvtColor(high_res_img, cv2.COLOR_RGB2BGR)
    
    hr_height, hr_width = high_res_img.shape[:2]
    
    # Extract each token at high resolution
    tokens_metadata = []
    scale_factor = hr_width / width
    
    for idx, (contour, area, x, y, w, h) in enumerate(token_contours, 1):
        # Adjust for skipped header and scale to high-res
        y_abs = y + skip_rows
        
        padding = int(10 * scale_factor)
        x1_hr = max(0, int(x * scale_factor) - padding)
        y1_hr = max(0, int(y_abs * scale_factor) - padding)
        x2_hr = min(hr_width, int((x + w) * scale_factor) + padding)
        y2_hr = min(hr_height, int((y_abs + h) * scale_factor) + padding)
        
        # Extract token from high-res image
        token_img = high_res_img[y1_hr:y2_hr, x1_hr:x2_hr]
        
        # Save token with page and card prefix
        token_filename = f'{card_filename_base}_token{idx:02d}.png'
        token_path = output_dir / token_filename
        cv2.imwrite(str(token_path), token_img)
        
        # Store metadata with original detection coordinates
        tokens_metadata.append({
            'filename': token_filename,
            'index': idx,
            'bbox': {
                'x': x,
                'y': y_abs,
                'width': w,
                'height': h
            },
            'area': int(area)
        })
    
    return {
        'tokens_extracted': len(tokens_metadata),
        'tokens': tokens_metadata
    }


def extract_text_from_token_guide(
    page: fitz.Page,
    card_coords: dict,
    skip_header_percent: float = 15.0
) -> list:
    """
    Extract all text blocks with locations from a token guide card.
    
    Uses text blocks to preserve multi-line names as they appear in the PDF.
    
    Args:
        page: PyMuPDF page object
        card_coords: Card corner coordinates
        skip_header_percent: Percentage of top to skip
    
    Returns:
        List of dicts with 'text' and 'bbox' (x, y, width, height in card coords)
    """
    # Calculate card bounding box in PDF points
    x1, y1 = card_coords['top_left']
    x2, y2 = card_coords['top_right']
    x3, y3 = card_coords['bottom_left']
    x4, y4 = card_coords['bottom_right']
    
    pdf_scale = 72 / 300.0
    card_left = min(x1, x3) * pdf_scale
    card_top = min(y1, y2) * pdf_scale
    card_right = max(x2, x4) * pdf_scale
    card_bottom = max(y3, y4) * pdf_scale
    card_height = card_bottom - card_top
    
    # Skip header area
    skip_height = card_height * (skip_header_percent / 100)
    content_top = card_top + skip_height
    card_rect = fitz.Rect(card_left, content_top, card_right, card_bottom)
    
    # Extract text with positions using words method (same as tools/extract_tokens.py)
    text_data = page.get_text("words", clip=card_rect)
    
    # Heuristics from tools/extract_tokens.py
    text_gap_max = 6.0
    same_line_y_max = 15.0
    next_line_y_min = 5.0
    next_line_y_max = 25.0
    next_line_x_overlap_ratio = 0.25
    
    text_positions = {}
    current_group = []
    current_pos = None
    
    for item in text_data:
        x0, y0, x1_word, y1, word, block_no, line_no, word_no = item
        
        # Calculate center position
        center_x = (x0 + x1_word) / 2
        center_y = (y0 + y1) / 2
        
        # Clean up word
        word = re.sub(r'[^a-zA-Z0-9\s\'-]', '', word)
        if not word or word.lower() in ['marker', 'guide']:
            continue
        
        # Group words that are close together
        if current_pos is None:
            current_pos = (center_x, center_y)
            current_group = [word]
            last_x1 = x1_word
            group_x_min = x0
            group_x_max = x1_word
        else:
            prev_x, prev_y = current_pos
            
            # Calculate gap from previous word's right edge to this word's left edge
            gap = abs(x0 - last_x1)
            y_diff = abs(center_y - prev_y)
            
            # Check if x positions overlap with current group (for multi-line names)
            overlap_len = max(0.0, min(x1_word, group_x_max) - max(x0, group_x_min))
            group_width = max(1.0, group_x_max - group_x_min)
            word_width = max(1.0, x1_word - x0)
            overlap_ratio = overlap_len / min(group_width, word_width)
            x_overlap = overlap_ratio >= next_line_x_overlap_ratio
            
            # Same line with small gap = same token name
            same_line = y_diff < same_line_y_max and gap < text_gap_max
            
            # Next line with overlapping x = continuation of multi-line token name
            next_line_continuation = (
                y_diff > next_line_y_min
                and y_diff < next_line_y_max
                and x_overlap
            )
            
            if same_line or next_line_continuation:
                current_group.append(word)
                current_pos = ((prev_x + center_x) / 2, (prev_y + center_y) / 2)
                last_x1 = x1_word
                # Update group x range
                group_x_min = min(group_x_min, x0)
                group_x_max = max(group_x_max, x1_word)
            else:
                # Save previous group
                if current_group:
                    text_positions[current_pos] = ' '.join(current_group)
                current_pos = (center_x, center_y)
                current_group = [word]
                last_x1 = x1_word
                group_x_min = x0
                group_x_max = x1_word
    
    # Save last group
    if current_group and current_pos:
        text_positions[current_pos] = ' '.join(current_group)
    
    # Now split each text element by "token" or "marker" delimiter
    text_elements = []
    for (center_x, center_y), text in text_positions.items():
        # Split by token/marker
        parts = re.split(r'\s+(token|marker)\s*', text, flags=re.IGNORECASE)
        
        # Recombine with delimiter
        current = ""
        for i, part in enumerate(parts):
            if i % 2 == 0:  # Text part
                current += part
            else:  # Delimiter (token/marker)
                current += " " + part
                # Complete token name - save it
                token_name = current.strip()
                if token_name:
                    # Convert position from PDF to card coordinates
                    rel_x = int((center_x - card_left) / pdf_scale)
                    rel_y = int((center_y - card_top) / pdf_scale)
                    
                    text_elements.append({
                        'text': token_name,
                        'bbox': {
                            'x': rel_x,
                            'y': rel_y,
                            'width': 100,  # Approximate - will be refined by matching
                            'height': 45
                        },
                        'font_size': 8.5
                    })
                current = ""
    
    return text_elements


def scale_markers(markers: list, scale: float) -> list:
    """Scale marker positions by a factor."""
    return [(int(x * scale), int(y * scale), conf) for x, y, conf in markers]


def match_markers_to_template(detected_markers: list, template_markers: list, tolerance: int = 5) -> float:
    """
    Match detected markers to template markers.
    Returns sum of confidence scores for matched markers.
    """
    total_score = 0.0
    
    for template_marker in template_markers:
        tx, ty, _ = template_marker
        
        # Find closest detected marker within tolerance
        best_confidence = 0.0
        for detected in detected_markers:
            dx, dy = detected[0], detected[1]
            distance = ((dx - tx) ** 2 + (dy - ty) ** 2) ** 0.5
            
            if distance <= tolerance:
                if detected[2] > best_confidence:
                    best_confidence = detected[2]
        
        total_score += best_confidence
    
    return total_score


def detect_page_template(img: np.ndarray, templates: dict, marker_template: np.ndarray, dpi_scale: float = 0.5) -> Optional[str]:
    """
    Detect which template (landscape/portrait/none) best fits the page by matching markers.
    Returns 'landscape', 'portrait', or None.
    """
    # Find markers (use lower threshold to catch all possible markers)
    detected_markers = find_markers(img, marker_template, threshold=0.5)
    
    if len(detected_markers) < 5:
        return None  # Not enough markers
    
    # Extract expected marker positions from both templates (at 300 DPI)
    landscape_markers = extract_template_markers(templates['landscape'])
    portrait_markers = extract_template_markers(templates['portrait'])
    
    # Scale template markers to match current DPI
    landscape_markers = scale_markers(landscape_markers, dpi_scale)
    portrait_markers = scale_markers(portrait_markers, dpi_scale)
    
    # Calculate match score for each template (sum of confidence scores)
    landscape_score = match_markers_to_template(detected_markers, landscape_markers, tolerance=5)
    portrait_score = match_markers_to_template(detected_markers, portrait_markers, tolerance=5)
    
    # Require strong match - at least 70% of expected markers with avg confidence > 0.5
    landscape_min_score = len(landscape_markers) * 0.7 * 0.5
    portrait_min_score = len(portrait_markers) * 0.7 * 0.5
    
    # Return the template with the highest score if it meets minimum
    if landscape_score < landscape_min_score and portrait_score < portrait_min_score:
        return None  # No good match
    
    if landscape_score > portrait_score:
        return 'landscape'
    else:
        return 'portrait'


def render_page_to_image(page: fitz.Page, dpi: int = 150) -> np.ndarray:
    """Render a PDF page to a BGR image."""
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    
    # Convert to BGR for OpenCV (PyMuPDF returns RGB/RGBA)
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    elif pix.n == 1:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    
    return img


def extract_card_region(img: np.ndarray, card_coords: dict, scale: float = 1.0) -> np.ndarray:
    """Extract a card region from a page image using corner coordinates."""
    # Extract coordinates and scale them
    x1, y1 = int(card_coords['top_left'][0] * scale), int(card_coords['top_left'][1] * scale)
    x2, y2 = int(card_coords['top_right'][0] * scale), int(card_coords['top_right'][1] * scale)
    x3, y3 = int(card_coords['bottom_left'][0] * scale), int(card_coords['bottom_left'][1] * scale)
    x4, y4 = int(card_coords['bottom_right'][0] * scale), int(card_coords['bottom_right'][1] * scale)
    
    # Calculate base bounding box
    left = min(x1, x3)
    right = max(x2, x4)
    top = min(y1, y2)
    bottom = max(y3, y4)
    
    # Apply per-card border adjustments if available
    if 'adjust' in card_coords:
        adjust = card_coords['adjust']
        left += adjust.get('left', 0)
        top += adjust.get('top', 0)
        right += adjust.get('right', 0)
        bottom += adjust.get('bottom', 0)
    
    return img[top:bottom, left:right]


def save_single_card_as_pdf(page: fitz.Page, card_coords: dict, output_path: Path, dpi: int = 150):
    """
    Extract a single card region from a PDF page and save as a new PDF (preserving text layer).
    
    Args:
        page: The PyMuPDF page object
        card_coords: Dictionary with card corner coordinates at 300 DPI
        output_path: Path where to save the extracted card PDF
        dpi: DPI used for rendering (default: 150)
    """
    # Calculate scale factor (coordinates are at 300 DPI reference)
    scale = dpi / 300.0
    
    # Extract and scale coordinates
    x1, y1 = card_coords['top_left'][0] * scale, card_coords['top_left'][1] * scale
    x2, y2 = card_coords['top_right'][0] * scale, card_coords['top_right'][1] * scale
    x3, y3 = card_coords['bottom_left'][0] * scale, card_coords['bottom_left'][1] * scale
    x4, y4 = card_coords['bottom_right'][0] * scale, card_coords['bottom_right'][1] * scale
    
    # Calculate bounding box in PDF points (72 DPI)
    # Convert from image coordinates to PDF coordinates
    pdf_scale = 72 / dpi
    left = min(x1, x3) * pdf_scale
    top = min(y1, y2) * pdf_scale
    right = max(x2, x4) * pdf_scale
    bottom = max(y3, y4) * pdf_scale
    
    # Apply border adjustments if available
    if 'adjust' in card_coords:
        adjust = card_coords['adjust']
        left += adjust.get('left', 0) * pdf_scale
        top += adjust.get('top', 0) * pdf_scale
        right += adjust.get('right', 0) * pdf_scale
        bottom += adjust.get('bottom', 0) * pdf_scale
    
    # Create crop rectangle
    crop_rect = fitz.Rect(left, top, right, bottom)
    
    # Create new PDF document with one page
    new_doc = fitz.open()
    new_page = new_doc.new_page(width=crop_rect.width, height=crop_rect.height)
    
    # Copy the cropped content from original page
    # Use show_pdf_page to copy content with text layer preserved
    new_page.show_pdf_page(
        new_page.rect,  # Target rectangle (full new page)
        page.parent,    # Source document
        page.number,    # Source page number
        clip=crop_rect  # Clip to card region
    )
    
    # Save the new PDF
    new_doc.save(str(output_path))
    new_doc.close()


def process_pdf_and_extract_all_cards(pdf_path: Path, templates: dict, output_dir: Path, 
                                      dpi: int = 150, start_page: int = 1, 
                                      end_page: Optional[int] = None) -> dict:
    """
    Process a PDF file and extract all cards from it using templates.
    Saves both PNG and PDF versions of each card.
    Returns dict with extraction statistics.
    """
    # Open PDF
    doc = fitz.open(pdf_path)
    
    if end_page is None:
        end_page = len(doc)
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get templates
    landscape_template = templates['landscape']
    portrait_template = templates['portrait']
    
    # Create + marker template for detection
    marker_template = np.array([
        [0, 1, 0],
        [1, 1, 1],
        [0, 1, 0]
    ], dtype=np.uint8) * 255
    
    total_cards = 0
    skipped_count = 0
    pages_processed = 0
    
    # Accumulate tokens across all token guide cards
    all_tokens_metadata = []
    all_text_elements = []
    
    # Process all pages
    for page_num in range(start_page, end_page + 1):
        page = doc[page_num - 1]
        
        # Render page once
        page_img = render_page_to_image(page, dpi)
        
        # Detect which template to use
        dpi_scale = dpi / 300.0  # Templates are at 300 DPI
        template_type = detect_page_template(page_img, templates, marker_template, dpi_scale)
        
        if template_type is None:
            skipped_count += 1
            # Stop processing after first skipped page - no more cards after this
            if skipped_count >= 1:
                del page_img
                break
            del page_img
            continue
        
        # Select appropriate template
        if template_type == 'landscape':
            card_template = landscape_template
        else:
            card_template = portrait_template
        
        # Extract cards using selected template
        for card_idx, card_coords in enumerate(card_template['cards'], 1):
            card_img = extract_card_region(page_img, card_coords, dpi_scale)
            
            # Save as PNG
            filename_png = f"page{page_num:02d}_card{card_idx}_{template_type}.png"
            output_path_png = output_dir / filename_png
            cv2.imwrite(str(output_path_png), card_img)
            
            # Save as PDF (preserving text layer)
            filename_pdf = f"page{page_num:02d}_card{card_idx}_{template_type}.pdf"
            output_path_pdf = output_dir / filename_pdf
            save_single_card_as_pdf(page, card_coords, output_path_pdf, dpi)
            
            # Check if this is a token guide card and extract tokens
            if template_type == 'portrait' and is_token_guide_card(page, card_coords):
                card_base = f"page{page_num:02d}_card{card_idx}"
                tokens_dir = output_dir.parent / 'tokens'
                tokens_dir.mkdir(parents=True, exist_ok=True)
                
                print(f"  → Detected token guide card: {card_base}")
                
                # Extract tokens at high resolution from PDF
                tokens_metadata = extract_tokens_from_card(
                    card_img=card_img,
                    page=page,
                    card_coords=card_coords,
                    output_dir=tokens_dir,
                    card_filename_base=card_base,
                    skip_header_percent=15.0,
                    min_token_area=3000,
                    extract_dpi=300
                )
                
                # Extract text elements from card for later name matching
                text_elements = extract_text_from_token_guide(
                    page=page,
                    card_coords=card_coords,
                    skip_header_percent=15.0
                )
                
                # Add source_card identifier to each token and accumulate
                for token in tokens_metadata.get('tokens', []):
                    token['source_card'] = card_base
                    all_tokens_metadata.append(token)
                
                # Add source_card identifier to each text element and accumulate
                for text_elem in text_elements:
                    text_elem['source_card'] = card_base
                    all_text_elements.append(text_elem)
                
                print(f"  → Extracted {tokens_metadata['tokens_extracted']} tokens at 300 DPI")
                print(f"  → Found {len(text_elements)} text elements for name matching")
            
            total_cards += 1
        
        pages_processed += 1
        
        # Reset skip counter - we found cards on this page
        skipped_count = 0
        
        # Free memory
        del page_img
    
    doc.close()
    
    # Save accumulated tokens metadata from all token guide cards
    if all_tokens_metadata or all_text_elements:
        tokens_dir = output_dir.parent / 'tokens'
        tokens_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = tokens_dir / 'tokens_metadata.json'
        
        combined_metadata = {
            'tokens': all_tokens_metadata,
            'text_elements': all_text_elements
        }
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(combined_metadata, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Saved tokens metadata: {len(all_tokens_metadata)} tokens, {len(all_text_elements)} text elements")
    
    return {
        'total_cards': total_cards,
        'pages_processed': pages_processed
    }


def run(input_dir: Path = None, output_dir: Path = None, templates_file: Path = None, 
        dpi: int = 150, max_workers: int = None) -> dict:
    """
    Main function to extract cards from PDFs.
    
    Args:
        input_dir: Directory containing PDF files (default: input/)
        output_dir: Directory to save extracted cards (default: extraction/)
        templates_file: Path to templates JSON (default: config/pipelines/warcom/card_templates.json)
        dpi: DPI for rendering (default: 150)
        max_workers: Max concurrent workers (default: None = auto)
        
    Returns:
        dict with 'success', 'files_processed', 'total_cards', 'failed' counts
    """
    if input_dir is None:
        input_dir = Path('layers/warcom/staging')
    
    if output_dir is None:
        output_dir = Path('layers/warcom/extracted')
    
    if templates_file is None:
        templates_file = Path('config/pipelines/warcom/card_templates.json')
    
    logger.info("=" * 70)
    logger.info("Step 2: Extract Cards from PDFs")
    logger.info("=" * 70)
    logger.info("")
    
    # Load card templates
    if not templates_file.exists():
        logger.error(f"Error: Templates not found: {templates_file}")
        return {'success': False, 'extracted': 0, 'failed': 0}
    
    templates = load_templates(templates_file)
    logger.info(f"Templates: {templates_file}")
    logger.info(f"  Landscape: {len(templates['landscape']['cards'])} cards per page")
    logger.info(f"  Portrait: {len(templates['portrait']['cards'])} cards per page")
    logger.info("")
    
    # Load team config for name matching
    team_config = load_team_config()
    if team_config:
        logger.info(f"Loaded {len(team_config)} teams from config")
    else:
        logger.warning("Warning: No team config found, using extracted names as-is")
    logger.info("")
    
    # Find all PDFs
    pdf_files = sorted(input_dir.glob('*.pdf'))
    
    if not pdf_files:
        logger.error(f"No PDF files found in {input_dir}")
        return {'success': True, 'files_processed': 0, 'total_cards': 0, 'failed': 0}
    
    logger.info(f"Found {len(pdf_files)} PDF files")
    logger.info(f"Output: {output_dir}")
    logger.info(f"DPI: {dpi}")
    # Limit workers to avoid overwhelming system with 46 PDFs
    actual_workers = max_workers if max_workers else 4
    logger.info(f"Workers: {actual_workers} (limited for stability)")
    logger.info("")
    logger.info("Processing PDFs concurrently:")
    logger.info("-" * 70)
    
    files_processed = 0
    total_cards = 0
    failed_count = 0
    archived_count = 0
    
    # Prepare archive directories
    archive_dir = Path('layers/archive')
    failed_dir = Path('layers/warcom/staging/failed')
    
    # Helper function to process one PDF (includes setup)
    def process_single_pdf(pdf_file):
        """Process one PDF: extract team name, setup folders, extract cards."""
        pdf_name = pdf_file.stem  # Filename without extension for logging
        try:
            print(f"\n[STARTING] {pdf_file.name}")
            
            # Extract team name from PDF content
            print(f"  [{pdf_name}] Extracting team name...")
            extracted_name = extract_team_name_from_pdf(pdf_file)
            # Match against config
            team_name = match_team_name(extracted_name, team_config) if team_config else extracted_name
            print(f"  [{pdf_name}] Team: {team_name} (from '{extracted_name}')")
            
            # Delete existing team folder to start fresh (per-team overwrite)
            team_folder = output_dir / (team_name if team_name else extracted_name)
            if team_folder.exists():
                print(f"  [{pdf_name}] Cleaning existing output...")
                shutil.rmtree(team_folder)
            
            # Create cards subdirectory within team folder
            team_output_dir = team_folder / 'cards'
            
            # Process and extract cards
            print(f"  [{pdf_name}] Extracting cards from PDF...")
            result = process_pdf_and_extract_all_cards(pdf_file, templates, team_output_dir, dpi)
            print(f"  [{pdf_name}] Done: {result['total_cards']} cards from {result['pages_processed']} pages")
            
            # Extract icons
            print(f"  [{pdf_name}] Extracting team icons...")
            icons_result = extract_icons_from_pdf(pdf_file, team_folder, team_name if team_name else extracted_name)
            icons_extracted = sum(1 for v in icons_result.values() if v)
            print(f"  [{pdf_name}] Icons: {icons_extracted}/3 extracted")
            
            return {
                'pdf_file': pdf_file,
                'extracted_name': extracted_name,
                'team_name': team_name,
                'result': result,
                'icons': icons_result,
                'error': None
            }
        except Exception as e:
            print(f"  [{pdf_name}] ✗ ERROR: {e}")
            return {
                'pdf_file': pdf_file,
                'extracted_name': None,
                'team_name': None,
                'result': None,
                'error': str(e)
            }
    
    # Process PDFs concurrently (limited workers for stability)
    actual_workers = max_workers if max_workers else 4
    with ThreadPoolExecutor(max_workers=actual_workers) as executor:
        # Submit all PDF processing tasks
        future_to_pdf = {
            executor.submit(process_single_pdf, pdf_file): pdf_file
            for pdf_file in pdf_files
        }
        
        # Process results as they complete
        for i, future in enumerate(as_completed(future_to_pdf), 1):
            pdf_file = future_to_pdf[future]
            
            try:
                data = future.result()
                
                # Check for errors
                if data['error']:
                    logger.error(f"\n[{i}/{len(pdf_files)}] ✗ FAILED: {pdf_file.name}")
                    failed_count += 1
                    continue
                
                extracted_name = data['extracted_name']
                team_name = data['team_name']
                result = data['result']
                
                logger.info(f"\n[{i}/{len(pdf_files)}] ✓ COMPLETED: {pdf_file.name}")
                
                # Archive the PDF
                if team_name:
                    # Move to archive/{team}/warcom/
                    team_archive_dir = archive_dir / team_name / 'warcom'
                    team_archive_dir.mkdir(parents=True, exist_ok=True)
                    archive_path = team_archive_dir / pdf_file.name
                    shutil.move(str(pdf_file), str(archive_path))
                    logger.info(f"  + Archived: {archive_path}")
                    archived_count += 1
                    files_processed += 1
                    total_cards += result['total_cards']
                else:
                    # Move to staging/failed/
                    failed_dir.mkdir(parents=True, exist_ok=True)
                    failed_path = failed_dir / pdf_file.name
                    shutil.move(str(pdf_file), str(failed_path))
                    logger.warning(f"  + Moved to failed: {failed_path}")
                    failed_count += 1
                
            except Exception as e:
                logger.error(f"  ✗ Unexpected error: {e}")
                failed_count += 1
    
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"Extraction complete!")
    logger.info(f"  Files processed: {files_processed}")
    logger.info(f"  Total cards: {total_cards}")
    logger.info(f"  Archived: {archived_count}")
    logger.info(f"  Failed: {failed_count}")
    logger.info(f"  Output: {output_dir}")
    logger.info("=" * 70)
    
    return {
        'success': failed_count == 0,
        'files_processed': files_processed,
        'total_cards': total_cards,
        'archived': archived_count,
        'failed': failed_count
    }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Step 2: Extract datacards from Kill Team PDFs'
    )
    parser.add_argument('--input', type=Path, default=Path('layers/warcom/staging'),
                       help='Input directory with PDFs (default: layers/warcom/staging)')
    parser.add_argument('--output', type=Path, default=Path('layers/warcom/extracted'),
                       help='Output directory (default: layers/warcom/extracted)')
    parser.add_argument('--templates', type=Path, default=Path('config/pipelines/warcom/card_templates.json'),
                       help='Templates file (default: config/pipelines/warcom/card_templates.json)')
    parser.add_argument('--dpi', type=int, default=150,
                       help='DPI for rendering (default: 150)')
    parser.add_argument('--workers', type=int, default=None,
                       help='Max concurrent workers (default: auto)')
    
    args = parser.parse_args()
    
    result = run(
        input_dir=args.input,
        output_dir=args.output,
        templates_file=args.templates,
        dpi=args.dpi,
        max_workers=args.workers
    )
    
    # Exit with error code if failed
    if not result['success']:
        exit(1)


if __name__ == '__main__':
    main()
