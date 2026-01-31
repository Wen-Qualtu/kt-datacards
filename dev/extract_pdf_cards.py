"""
Extract datacards and icons from Warhammer Community Kill Team PDFs.

This script processes PDFs downloaded from Warhammer Community and extracts:
1. Team icon (page 1, top left)
2. Token bag icon (page 14)
3. Datacards using corner markers:
   - Pages 1-~8: Landscape 1x4 grid (datacards)
   - Pages ~9-10: Portrait 2x2 grid (rules, ploys, equipment)
"""

import fitz  # PyMuPDF
from pathlib import Path
from PIL import Image
import numpy as np
import argparse
import re
from typing import List, Tuple, Optional
import cv2


def extract_team_slug_from_filename(pdf_path: Path) -> str:
    """Extract team slug from PDF filename."""
    # Example: eng_28-01_kill_team_team_rules_murderwing-nk5ocpzzgd-qcvchireiu.pdf
    # Extract 'murderwing'
    filename = pdf_path.stem
    match = re.search(r'team_rules_([a-z-]+)-[a-z0-9]+', filename)
    if match:
        return match.group(1)
    
    # Fallback: try to extract anything between team_rules_ and next -
    match = re.search(r'team_rules_([a-z-]+)', filename)
    if match:
        return match.group(1)
    
    return "unknown"


def pdf_page_to_image(page: fitz.Page, dpi: int = 300) -> np.ndarray:
    """Convert PDF page to numpy array image."""
    # Render page to pixmap
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    
    # Convert to numpy array
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    
    # Convert RGBA to RGB if needed
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    
    return img


def find_corner_markers(img: np.ndarray, threshold: int = 200) -> List[Tuple[int, int]]:
    """
    Find + corner markers in the image.
    Returns list of (x, y) coordinates of marker centers.
    """
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    
    # Threshold to find dark markers
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
    
    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    markers = []
    for contour in contours:
        # Get bounding box
        x, y, w, h = cv2.boundingRect(contour)
        
        # Filter by size (markers should be small, roughly square)
        if 10 < w < 100 and 10 < h < 100 and 0.5 < w/h < 2.0:
            # Check if it looks like a + shape
            area = cv2.contourArea(contour)
            bbox_area = w * h
            if 0.2 < area / bbox_area < 0.8:  # + shape won't fill the bbox
                center_x = x + w // 2
                center_y = y + h // 2
                markers.append((center_x, center_y))
    
    return markers


def group_markers_into_cards(markers: List[Tuple[int, int]], 
                             orientation: str = 'landscape') -> List[Tuple[int, int, int, int]]:
    """
    Group corner markers into card rectangles.
    Returns list of (x1, y1, x2, y2) bounding boxes.
    """
    if len(markers) < 4:
        return []
    
    # Sort markers
    markers = sorted(markers)
    
    cards = []
    
    if orientation == 'landscape':
        # 1x4 grid: cards stacked vertically
        # Group markers by y-coordinate (rows)
        y_sorted = sorted(markers, key=lambda m: m[1])
        
        # Try to find 5 rows of markers (4 cards = 5 horizontal lines)
        rows = []
        current_row = [y_sorted[0]]
        
        for marker in y_sorted[1:]:
            if abs(marker[1] - current_row[0][1]) < 50:  # Same row
                current_row.append(marker)
            else:
                if len(current_row) >= 2:  # Valid row
                    rows.append(current_row)
                current_row = [marker]
        
        if len(current_row) >= 2:
            rows.append(current_row)
        
        # Extract cards from consecutive rows
        for i in range(len(rows) - 1):
            top_row = sorted(rows[i], key=lambda m: m[0])
            bottom_row = sorted(rows[i + 1], key=lambda m: m[0])
            
            if len(top_row) >= 2 and len(bottom_row) >= 2:
                x1 = top_row[0][0]
                y1 = top_row[0][1]
                x2 = top_row[-1][0]
                y2 = bottom_row[0][1]
                cards.append((x1, y1, x2, y2))
    
    else:  # portrait - 2x2 grid
        # Group into 3 rows and 3 columns of markers
        y_sorted = sorted(markers, key=lambda m: m[1])
        
        # Find row groups
        rows = []
        current_row = [y_sorted[0]]
        
        for marker in y_sorted[1:]:
            if abs(marker[1] - current_row[0][1]) < 50:
                current_row.append(marker)
            else:
                if len(current_row) >= 2:
                    rows.append(sorted(current_row, key=lambda m: m[0]))
                current_row = [marker]
        
        if len(current_row) >= 2:
            rows.append(sorted(current_row, key=lambda m: m[0]))
        
        # Extract 2x2 grid of cards
        for row_idx in range(len(rows) - 1):
            top_markers = rows[row_idx]
            bottom_markers = rows[row_idx + 1]
            
            for col_idx in range(len(top_markers) - 1):
                x1 = top_markers[col_idx][0]
                y1 = top_markers[col_idx][1]
                x2 = top_markers[col_idx + 1][0]
                y2 = bottom_markers[col_idx][1] if col_idx < len(bottom_markers) else bottom_markers[-1][1]
                
                cards.append((x1, y1, x2, y2))
    
    return cards


def extract_icon_region(img: np.ndarray, region: Tuple[int, int, int, int]) -> Image.Image:
    """Extract a rectangular region from the image."""
    x1, y1, x2, y2 = region
    cropped = img[y1:y2, x1:x2]
    return Image.fromarray(cropped)


def extract_team_icon(page: fitz.Page, dpi: int = 300) -> Optional[Image.Image]:
    """Extract team icon from top left of page 1."""
    img = pdf_page_to_image(page, dpi)
    height, width = img.shape[:2]
    
    # Icon is roughly in top left, estimate region
    # Adjust these values based on actual PDF layout
    x1 = int(width * 0.05)
    y1 = int(height * 0.05)
    x2 = int(width * 0.25)
    y2 = int(height * 0.20)
    
    icon = extract_icon_region(img, (x1, y1, x2, y2))
    return icon


def extract_token_icon(page: fitz.Page, dpi: int = 300) -> Optional[Image.Image]:
    """Extract token bag icon from page (usually page 14)."""
    img = pdf_page_to_image(page, dpi)
    height, width = img.shape[:2]
    
    # Token icon location - adjust based on actual layout
    x1 = int(width * 0.05)
    y1 = int(height * 0.05)
    x2 = int(width * 0.25)
    y2 = int(height * 0.20)
    
    icon = extract_icon_region(img, (x1, y1, x2, y2))
    return icon


def extract_cards_from_page(page: fitz.Page, page_num: int, 
                            output_dir: Path, team_slug: str, dpi: int = 300):
    """Extract individual cards from a page using corner markers."""
    img = pdf_page_to_image(page, dpi)
    
    # Determine orientation based on page number
    # First ~8 pages are landscape datacards, rest are portrait
    orientation = 'landscape' if page_num <= 8 else 'portrait'
    
    # Find corner markers
    markers = find_corner_markers(img)
    
    if len(markers) < 4:
        print(f"  Page {page_num}: Not enough markers found ({len(markers)})")
        return
    
    # Group markers into cards
    cards = group_markers_into_cards(markers, orientation)
    
    print(f"  Page {page_num}: Found {len(cards)} cards")
    
    # Extract and save each card
    for idx, (x1, y1, x2, y2) in enumerate(cards):
        card_img = extract_icon_region(img, (x1, y1, x2, y2))
        
        # Save card
        card_filename = f"{team_slug}_page{page_num:02d}_card{idx+1:02d}.png"
        card_path = output_dir / card_filename
        card_img.save(card_path)
        print(f"    Saved: {card_filename}")


def process_pdf(pdf_path: Path, output_base_dir: Path, dpi: int = 300):
    """Process a Kill Team PDF and extract all cards and icons."""
    print(f"\nProcessing: {pdf_path.name}")
    
    # Extract team slug
    team_slug = extract_team_slug_from_filename(pdf_path)
    print(f"Team: {team_slug}")
    
    # Create output directory
    output_dir = output_base_dir / team_slug / "pdf_extracted"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Open PDF
    doc = fitz.open(pdf_path)
    
    try:
        # Extract team icon from page 1
        if len(doc) >= 1:
            print("Extracting team icon from page 1...")
            icon = extract_team_icon(doc[0], dpi)
            if icon:
                icon_path = output_dir / f"{team_slug}_icon.png"
                icon.save(icon_path)
                print(f"  Saved: {icon_path.name}")
        
        # Extract token bag icon from page 14
        if len(doc) >= 14:
            print("Extracting token bag icon from page 14...")
            token_icon = extract_token_icon(doc[13], dpi)  # 0-indexed
            if token_icon:
                token_path = output_dir / f"{team_slug}_token_icon.png"
                token_icon.save(token_path)
                print(f"  Saved: {token_path.name}")
        
        # Extract cards from pages 1-10 (before fluff section)
        print("Extracting cards...")
        for page_num in range(1, min(11, len(doc) + 1)):
            page = doc[page_num - 1]  # 0-indexed
            extract_cards_from_page(page, page_num, output_dir, team_slug, dpi)
        
        print(f"\n✅ Completed extraction for {team_slug}")
        print(f"   Output: {output_dir}")
    
    finally:
        doc.close()


def main():
    parser = argparse.ArgumentParser(
        description='Extract cards and icons from Warhammer Community Kill Team PDFs'
    )
    parser.add_argument('pdf', type=Path, help='Path to PDF file')
    parser.add_argument('--output', type=Path, default=Path('dev/pdf_extraction'),
                       help='Output directory (default: dev/pdf_extraction)')
    parser.add_argument('--dpi', type=int, default=300,
                       help='DPI for rendering (default: 300)')
    
    args = parser.parse_args()
    
    if not args.pdf.exists():
        print(f"Error: PDF not found: {args.pdf}")
        return
    
    process_pdf(args.pdf, args.output, args.dpi)


if __name__ == '__main__':
    main()
