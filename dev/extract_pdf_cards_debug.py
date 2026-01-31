"""
Debug mode for PDF card extraction - visualizes marker detection.
"""

import fitz  # PyMuPDF
from pathlib import Path
import numpy as np
import argparse
import cv2


def debug_visualize_page(page: fitz.Page, page_num: int, output_dir: Path, dpi: int = 300):
    """Visualize marker detection on a single page."""
    # Render page to image
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    
    # Convert to BGR for OpenCV
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    
    # Create debug image
    debug_img = img.copy()
    
    # Convert to grayscale for processing
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    print(f"\nPage {page_num}:")
    print(f"  Size: {img.shape[1]}x{img.shape[0]} pixels")
    
    # Get edges - this is where the + markers will be visible
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    # Create template of the + marker (cross shape)
    # Try multiple sizes to find the markers
    all_markers = []
    
    for size in [20, 25, 30, 35, 40, 45, 50]:
        cross_template = np.zeros((size, size), dtype=np.uint8)
        thickness = max(2, size // 8)
        center = size // 2
        
        # Draw horizontal line
        cv2.line(cross_template, (0, center), (size, center), 255, thickness)
        # Draw vertical line
        cv2.line(cross_template, (center, 0), (center, size), 255, thickness)
        
        # Match template in the EDGES image
        result = cv2.matchTemplate(edges, cross_template, cv2.TM_CCOEFF_NORMED)
        threshold = 0.55  # Lower threshold to catch bottom row markers
        locations = np.where(result >= threshold)
        
        for pt in zip(*locations[::-1]):
            confidence = result[pt[1], pt[0]]
            all_markers.append((pt[0] + size//2, pt[1] + size//2, size, confidence))
    
    # Remove duplicates (markers found at multiple sizes)
    # Keep the one with highest confidence
    print(f"  Total markers before dedup: {len(all_markers)}")
    
    unique_markers = []
    for (x, y, size, conf) in all_markers:
        # Check if this is close to an existing marker
        is_duplicate = False
        for i, (ux, uy, usize, uconf) in enumerate(unique_markers):
            dist = np.sqrt((x - ux)**2 + (y - uy)**2)
            if dist < 30:  # Within 30 pixels
                is_duplicate = True
                # Keep the one with higher confidence
                if conf > uconf:
                    unique_markers[i] = (x, y, size, conf)
                break
        
        if not is_duplicate:
            unique_markers.append((x, y, size, conf))
    
    # Draw ALL markers (before dedup) in light green
    for (x, y, size, conf) in all_markers:
        cv2.circle(debug_img, (x, y), 10, (100, 255, 100), 1)
    
    # Draw unique markers on debug image in bright colors
    for (x, y, size, conf) in unique_markers:
        # Draw circle at marker center
        cv2.circle(debug_img, (x, y), 20, (0, 255, 0), 3)
        cv2.circle(debug_img, (x, y), 5, (0, 0, 255), -1)
        # Draw small box around it
        half = size // 2
        cv2.rectangle(debug_img, (x-half, y-half), (x+half, y+half), (255, 0, 255), 2)
        # Add confidence text
        cv2.putText(debug_img, f"{conf:.2f}", (x+25, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
    
    print(f"  Found {len(unique_markers)} + markers in edges (green circles with magenta boxes)")
    
    # Method 2: Edge detection + contour analysis (for reference)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    # Draw some contours in light blue for reference
    cv2.drawContours(debug_img, contours[:500], -1, (255, 200, 100), 1)
    print(f"  Edge contours: {len(contours)} found (light blue)")
    
    # Save debug image
    debug_path = output_dir / f'page_{page_num:02d}_debug.png'
    cv2.imwrite(str(debug_path), debug_img)
    print(f"  ✓ Saved: {debug_path.name}")
    
    # Also save edge detection
    edges_path = output_dir / f'page_{page_num:02d}_edges.png'
    cv2.imwrite(str(edges_path), edges)
    print(f"  ✓ Saved edges: {edges_path.name}")


def main():
    parser = argparse.ArgumentParser(
        description='Debug visualization for PDF card extraction'
    )
    parser.add_argument('pdf', type=Path, help='Path to PDF file')
    parser.add_argument('--output', type=Path, default=Path('dev/pdf_extraction/debug'),
                       help='Output directory (default: dev/pdf_extraction/debug)')
    parser.add_argument('--dpi', type=int, default=300,
                       help='DPI for rendering (default: 300)')
    parser.add_argument('--pages', type=str, default='1-15',
                       help='Page range to process, e.g. "1-5" or "1,3,5" (default: 1-15)')
    
    args = parser.parse_args()
    
    if not args.pdf.exists():
        print(f"Error: PDF not found: {args.pdf}")
        return
    
    # Parse page range
    pages_to_process = []
    if '-' in args.pages:
        start, end = map(int, args.pages.split('-'))
        pages_to_process = list(range(start, end + 1))
    else:
        pages_to_process = [int(p) for p in args.pages.split(',')]
    
    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)
    
    print(f"Processing: {args.pdf.name}")
    print(f"Output: {args.output}")
    print(f"DPI: {args.dpi}")
    print(f"Pages: {pages_to_process}")
    print("="*60)
    
    # Open PDF and process pages
    doc = fitz.open(args.pdf)
    
    try:
        for page_num in pages_to_process:
            if page_num < 1 or page_num > len(doc):
                print(f"Skipping page {page_num} (out of range)")
                continue
            
            page = doc[page_num - 1]  # 0-indexed
            debug_visualize_page(page, page_num, args.output, args.dpi)
    
    finally:
        doc.close()
    
    print("\n" + "="*60)
    print(f"✓ Debug visualization complete!")
    print(f"  Check images in: {args.output}")
    print("\nLegend:")
    print("  - Green circles with red centers: Detected + markers")
    print("  - Magenta boxes: Marker detection region")
    print("  - Yellow numbers: Confidence scores")
    print("  - Light blue lines: Edge contours")
    print("\nEdge files show the Canny edge detection used for marker matching")


if __name__ == '__main__':
    main()
