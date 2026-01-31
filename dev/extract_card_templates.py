"""
Extract marker coordinates from sample pages to create card extraction templates.
"""

import fitz  # PyMuPDF
from pathlib import Path
import numpy as np
import argparse
import cv2
import json


def find_markers(page: fitz.Page, dpi: int = 300, threshold: float = 0.7):
    """Find + marker coordinates on a page."""
    # Render page to image
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    
    # Convert to BGR for OpenCV
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Get edges
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    # Find markers at multiple sizes
    all_markers = []
    
    for size in [20, 25, 30, 35, 40, 45, 50]:
        cross_template = np.zeros((size, size), dtype=np.uint8)
        thickness = max(2, size // 8)
        center = size // 2
        
        # Draw cross
        cv2.line(cross_template, (0, center), (size, center), 255, thickness)
        cv2.line(cross_template, (center, 0), (center, size), 255, thickness)
        
        # Match template
        result = cv2.matchTemplate(edges, cross_template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        
        for pt in zip(*locations[::-1]):
            confidence = result[pt[1], pt[0]]
            all_markers.append((pt[0] + size//2, pt[1] + size//2, confidence))
    
    # Remove duplicates (keep highest confidence)
    unique_markers = []
    for (x, y, conf) in all_markers:
        is_duplicate = False
        for i, (ux, uy, uconf) in enumerate(unique_markers):
            dist = np.sqrt((x - ux)**2 + (y - uy)**2)
            if dist < 30:
                is_duplicate = True
                if conf > uconf:
                    unique_markers[i] = (x, y, conf)
                break
        
        if not is_duplicate:
            unique_markers.append((x, y, conf))
    
    # Sort by position (top to bottom, left to right)
    unique_markers.sort(key=lambda m: (m[1], m[0]))
    
    # Convert to regular Python ints for JSON serialization
    return [(int(x), int(y)) for x, y, _ in unique_markers]


def create_landscape_template(markers):
    """
    Create template for landscape cards (1x4 grid).
    Layout with 10 markers in 2 columns, 5 rows:
    1  2
    3  4
    5  6
    7  8
    9  10
    
    Cards: [1,2,3,4], [3,4,5,6], [5,6,7,8], [7,8,9,10]
    """
    if len(markers) < 10:
        raise ValueError(f"Expected 10 markers for landscape, got {len(markers)}")
    
    cards = []
    for i in range(4):
        base = i * 2
        card = {
            "top_left": markers[base],
            "top_right": markers[base + 1],
            "bottom_left": markers[base + 2],
            "bottom_right": markers[base + 3]
        }
        cards.append(card)
    
    return {
        "type": "landscape",
        "grid": "1x4",
        "marker_count": 10,
        "cards": cards
    }


def create_portrait_template(markers):
    """
    Create template for portrait cards (2x2 grid).
    Layout with 9 markers in 3 columns, 3 rows:
    1  2  3
    4  5  6
    7  8  9
    
    Cards: [1,2,4,5], [2,3,5,6], [4,5,7,8], [5,6,8,9]
    """
    if len(markers) < 7:
        raise ValueError(f"Expected at least 7 markers for portrait, got {len(markers)}")
    
    # Organize markers into grid (find columns and rows)
    # Sort by x to find columns
    by_x = sorted(markers, key=lambda m: m[0])
    
    # Find column breaks (significant gaps in x)
    x_gaps = []
    for i in range(len(by_x) - 1):
        gap = by_x[i+1][0] - by_x[i][0]
        x_gaps.append((gap, i))
    x_gaps.sort(reverse=True)
    
    # Assume 3 columns, so 2 major gaps
    col_breaks = sorted([g[1] for g in x_gaps[:2]])
    
    col1 = by_x[:col_breaks[0]+1]
    col2 = by_x[col_breaks[0]+1:col_breaks[1]+1] if len(col_breaks) > 1 else []
    col3 = by_x[col_breaks[1]+1:] if len(col_breaks) > 1 else []
    
    # Sort each column by y
    col1.sort(key=lambda m: m[1])
    col2.sort(key=lambda m: m[1])
    col3.sort(key=lambda m: m[1])
    
    # Extrapolate missing markers in bottom row if needed
    # We expect 3 rows of 3 markers each
    if len(col1) == 3 and len(col2) < 3 and len(col3) < 3:
        # Calculate row spacing from first column
        row_spacing = col1[1][1] - col1[0][1]
        expected_y_row3 = col1[2][1]
        
        # Calculate column spacing
        if len(col2) >= 1 and len(col3) >= 1:
            col_spacing_12 = col2[0][0] - col1[0][0]
            col_spacing_23 = col3[0][0] - col2[0][0]
            
            # Extrapolate missing marker in column 2, row 3
            if len(col2) == 2:
                marker_8 = (col2[0][0], expected_y_row3)
                col2.append(marker_8)
                print(f"  Extrapolated marker 8: {marker_8}")
            
            # Extrapolate missing marker in column 3, row 3
            if len(col3) == 2:
                marker_9 = (col3[0][0], expected_y_row3)
                col3.append(marker_9)
                print(f"  Extrapolated marker 9: {marker_9}")
    
    # Build grid (fill missing positions with None)
    max_rows = max(len(col1), len(col2), len(col3))
    grid = []
    for row in range(max_rows):
        grid_row = []
        for col in [col1, col2, col3]:
            if row < len(col):
                grid_row.append(col[row])
            else:
                grid_row.append(None)
        grid.append(grid_row)
    
    # Extract cards (2x2 grid of cards from 3x3 markers)
    cards = []
    for card_row in range(2):
        for card_col in range(2):
            tl = grid[card_row][card_col]
            tr = grid[card_row][card_col + 1]
            bl = grid[card_row + 1][card_col]
            br = grid[card_row + 1][card_col + 1]
            
            # Extrapolate missing corners if needed
            if tl and tr and bl and not br:
                # Calculate bottom-right from other corners
                br = (tr[0] + (bl[0] - tl[0]), bl[1] + (tr[1] - tl[1]))
            elif tl and tr and not bl and br:
                bl = (tl[0] + (br[0] - tr[0]), br[1] + (tl[1] - tr[1]))
            elif tl and not tr and bl and br:
                tr = (br[0] + (tl[0] - bl[0]), tl[1] + (br[1] - bl[1]))
            elif not tl and tr and bl and br:
                tl = (bl[0] + (tr[0] - br[0]), tr[1] + (bl[1] - br[1]))
            
            if tl and tr and bl and br:
                cards.append({
                    "top_left": tl,
                    "top_right": tr,
                    "bottom_left": bl,
                    "bottom_right": br
                })
    
    return {
        "type": "portrait",
        "grid": "2x2",
        "marker_count": len(markers),
        "cards": cards
    }


def main():
    parser = argparse.ArgumentParser(description='Create card extraction templates from sample pages')
    parser.add_argument('pdf', type=Path, help='Path to PDF file')
    parser.add_argument('--landscape-page', type=int, default=2, help='Page number with landscape cards (default: 2)')
    parser.add_argument('--portrait-page', type=int, default=5, help='Page number with portrait cards (default: 5)')
    parser.add_argument('--output', type=Path, default=Path('dev/card_templates.json'), help='Output JSON file')
    parser.add_argument('--dpi', type=int, default=300, help='DPI for rendering')
    
    args = parser.parse_args()
    
    if not args.pdf.exists():
        print(f"Error: PDF not found: {args.pdf}")
        return
    
    doc = fitz.open(args.pdf)
    
    print(f"Processing: {args.pdf.name}")
    print("="*60)
    
    # Extract landscape template
    print(f"\nPage {args.landscape_page} (landscape 1x4 grid):")
    landscape_markers = find_markers(doc[args.landscape_page - 1], args.dpi, threshold=0.7)
    print(f"  Found {len(landscape_markers)} markers")
    for i, (x, y) in enumerate(landscape_markers, 1):
        print(f"  Marker {i}: ({x}, {y})")
    
    landscape_template = create_landscape_template(landscape_markers)
    print(f"  ✓ Created template with {len(landscape_template['cards'])} cards")
    
    # Extract portrait template
    print(f"\nPage {args.portrait_page} (portrait 2x2 grid):")
    portrait_markers = find_markers(doc[args.portrait_page - 1], args.dpi, threshold=0.55)
    print(f"  Found {len(portrait_markers)} markers")
    for i, (x, y) in enumerate(portrait_markers, 1):
        print(f"  Marker {i}: ({x}, {y})")
    
    portrait_template = create_portrait_template(portrait_markers)
    print(f"  ✓ Created template with {len(portrait_template['cards'])} cards")
    
    doc.close()
    
    # Save templates
    templates = {
        "landscape": landscape_template,
        "portrait": portrait_template
    }
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(templates, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✓ Templates saved to: {args.output}")
    print(f"\nLandscape template: {len(landscape_template['cards'])} cards")
    print(f"Portrait template: {len(portrait_template['cards'])} cards")


if __name__ == '__main__':
    main()
