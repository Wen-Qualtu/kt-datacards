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
            
            total_cards += 1
        
        pages_processed += 1
        
        # Reset skip counter - we found cards on this page
        skipped_count = 0
        
        # Free memory
        del page_img
    
    doc.close()
    
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
    
    templates = load_card_templates(templates_file)
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
            
            return {
                'pdf_file': pdf_file,
                'extracted_name': extracted_name,
                'team_name': team_name,
                'result': result,
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
