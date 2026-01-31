"""
Extract cards from PDF using pre-generated templates.
Auto-detects which template (landscape/portrait) to use for each page.
"""

import fitz  # PyMuPDF
from pathlib import Path
import numpy as np
import argparse
import cv2
import json


def load_templates(template_file: Path):
    """Load card extraction templates."""
    with open(template_file) as f:
        return json.load(f)


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
                dist = np.sqrt((marker[0] - existing[0])**2 + (marker[1] - existing[1])**2)
                if dist < 30:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_markers.append(marker)
        markers = unique_markers
    
    return markers


def extract_template_markers(template: dict) -> list:
    """Extract all marker positions from a template."""
    markers = []
    for card in template['cards']:
        # Each card has 4 corners
        markers.append(tuple(card['top_left']))
        markers.append(tuple(card['top_right']))
        markers.append(tuple(card['bottom_left']))
        markers.append(tuple(card['bottom_right']))
    
    # Deduplicate (shared corners between cards)
    return list(set(markers))


def scale_markers(markers: list, scale: float) -> list:
    """Scale marker coordinates by a factor."""
    return [(int(x * scale), int(y * scale)) for x, y in markers]


def match_markers_to_template(detected_markers: list, template_markers: list, tolerance: int = 5) -> float:
    """
    Calculate how well detected markers match template markers.
    Returns sum of confidence scores for markers that match template positions.
    """
    if not template_markers:
        return 0.0
    
    total_score = 0.0
    for template_marker in template_markers:
        # Find the best matching detected marker for this template position
        best_confidence = 0.0
        for detected in detected_markers:
            dx = abs(detected[0] - template_marker[0])
            dy = abs(detected[1] - template_marker[1])
            if dx <= tolerance and dy <= tolerance:
                # detected[2] is the confidence score
                if detected[2] > best_confidence:
                    best_confidence = detected[2]
        
        total_score += best_confidence
    
    return total_score


def detect_page_template(img: np.ndarray, templates: dict, marker_template: np.ndarray, dpi_scale: float = 0.5) -> str:
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
    # Landscape has 10 markers, portrait has 9
    landscape_min_score = len(landscape_markers) * 0.7 * 0.5  # 70% markers × 0.5 confidence
    portrait_min_score = len(portrait_markers) * 0.7 * 0.5
    
    # Return the template with the highest score if it meets minimum
    if landscape_score < landscape_min_score and portrait_score < portrait_min_score:
        return None  # No good match
    
    if landscape_score > portrait_score:
        return 'landscape'
    else:
        return 'portrait'


def render_page_to_image(page: fitz.Page, dpi: int = 300) -> np.ndarray:
    """Render a PDF page to a BGR image."""
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    
    # Convert to BGR for OpenCV
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    
    return img


def extract_card_region(img: np.ndarray, card_coords: dict, dpi_scale: float = 1.0) -> np.ndarray:
    """Extract a card region from a page image using corner coordinates."""
    # Extract coordinates and scale them
    x1, y1 = int(card_coords['top_left'][0] * dpi_scale), int(card_coords['top_left'][1] * dpi_scale)
    x2, y2 = int(card_coords['top_right'][0] * dpi_scale), int(card_coords['top_right'][1] * dpi_scale)
    x3, y3 = int(card_coords['bottom_left'][0] * dpi_scale), int(card_coords['bottom_left'][1] * dpi_scale)
    x4, y4 = int(card_coords['bottom_right'][0] * dpi_scale), int(card_coords['bottom_right'][1] * dpi_scale)
    
    # Crop the rectangle (use min/max to handle any orientation)
    left = min(x1, x3)
    right = max(x2, x4)
    top = min(y1, y2)
    bottom = max(y3, y4)
    
    card = img[top:bottom, left:right]
    
    return card


def extract_cards_from_pdf(pdf_path: Path, templates: dict, output_dir: Path, dpi: int = 150, 
                          start_page: int = 1, end_page: int = None):
    """Extract all cards from PDF using templates with auto-detection."""
    # Clean output directory
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    
    if end_page is None:
        end_page = len(doc)
    else:
        end_page = min(end_page, len(doc))
    
    landscape_template = templates['landscape']
    portrait_template = templates['portrait']
    
    # Create marker template for detection
    marker_template = np.array([
        [0, 1, 0],
        [1, 1, 1],
        [0, 1, 0]
    ], dtype=np.uint8) * 255
    
    total_cards = 0
    skipped_count = 0
    
    # Process all pages
    print("\nProcessing pages:")
    print("-" * 60)
    
    for page_num in range(start_page, end_page + 1):
        page = doc[page_num - 1]
        
        # Render page once
        print(f"  Page {page_num}: Rendering...", end='', flush=True)
        page_img = render_page_to_image(page, dpi)
        
        # Detect which template to use
        print(" Detecting template...", end='', flush=True)
        dpi_scale = dpi / 300.0  # Templates are at 300 DPI
        template_type = detect_page_template(page_img, templates, marker_template, dpi_scale)
        
        if template_type is None:
            print(f"\r  Page {page_num}: Skipped (no cards detected)")
            skipped_count += 1
            # Stop processing after first skipped page - no more cards after this
            if skipped_count >= 1:
                print(f"\n  Stopping: No more cards expected after first non-card page")
                break
            del page_img
            continue
        
        # Select appropriate template
        if template_type == 'landscape':
            card_template = landscape_template
            template_name = 'landscape'
        else:
            card_template = portrait_template
            template_name = 'portrait'
        
        print(f"\r  Page {page_num} ({template_name}): Extracting cards...")
        
        # Extract cards using selected template
        for card_idx, card_coords in enumerate(card_template['cards'], 1):
            card_img = extract_card_region(page_img, card_coords, dpi_scale)
            
            # Save card
            filename = f"page{page_num:02d}_card{card_idx}_{template_name}.png"
            output_path = output_dir / filename
            cv2.imwrite(str(output_path), card_img)
            
            print(f"    ✓ Card {card_idx}: {card_img.shape[1]}x{card_img.shape[0]}px")
            total_cards += 1
        
        # Reset skip counter - we found cards on this page
        skipped_count = 0
        
        # Free memory
        del page_img
    
    doc.close()
    
    return total_cards


def main():
    parser = argparse.ArgumentParser(description='Extract cards from PDF using templates')
    parser.add_argument('pdf', type=Path, help='Path to PDF file')
    parser.add_argument('--templates', type=Path, default=Path('dev/card_templates.json'),
                       help='Path to templates JSON (default: dev/card_templates.json)')
    parser.add_argument('--output', type=Path, default=Path('dev/extracted_cards'),
                       help='Output directory (default: dev/extracted_cards)')
    parser.add_argument('--dpi', type=int, default=150,
                       help='DPI for rendering (default: 150)')
    parser.add_argument('--start-page', type=int, default=1,
                       help='First page to process (default: 1)')
    parser.add_argument('--end-page', type=int, default=None,
                       help='Last page to process (default: all pages)')
    
    args = parser.parse_args()
    
    if not args.pdf.exists():
        print(f"Error: PDF not found: {args.pdf}")
        return
    
    if not args.templates.exists():
        print(f"Error: Templates not found: {args.templates}")
        return
    
    print(f"Processing: {args.pdf.name}")
    print(f"Templates: {args.templates}")
    print(f"Output: {args.output}")
    print(f"DPI: {args.dpi}")
    print("=" * 60)
    
    # Load templates
    templates = load_templates(args.templates)
    print(f"\nLoaded templates:")
    print(f"  Landscape: {len(templates['landscape']['cards'])} cards per page")
    print(f"  Portrait: {len(templates['portrait']['cards'])} cards per page")
    
    # Extract cards
    total_cards = extract_cards_from_pdf(args.pdf, templates, args.output, args.dpi, 
                                         args.start_page, args.end_page)
    
    print("\n" + "=" * 60)
    print(f"✓ Extraction complete!")
    print(f"  Total cards extracted: {total_cards}")
    print(f"  Output directory: {args.output}")


if __name__ == '__main__':
    main()
