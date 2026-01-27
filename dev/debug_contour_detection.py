"""
Debug script to visualize contour detection on PDF tokens.
"""

import cv2
import numpy as np
import fitz
from pathlib import Path
import sys

def debug_contours(pdf_path: str, threshold: int = 200):
    """Debug contour detection."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        return
    
    print(f"Analyzing: {pdf_path}")
    print(f"Threshold: {threshold}")
    
    # Extract last page
    doc = fitz.open(str(pdf_path))
    page = doc[-1]
    
    # Render at 300 DPI
    mat = fitz.Matrix(300 / 72, 300 / 72)
    pix = page.get_pixmap(matrix=mat)
    
    # Convert to numpy
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    elif pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    
    doc.close()
    
    # Skip header (15%)
    skip_pixels = int(img.shape[0] * 0.15)
    img_crop = img[skip_pixels:, :]
    
    # Convert to grayscale
    gray = cv2.cvtColor(img_crop, cv2.COLOR_BGR2GRAY)
    
    print(f"\nGray values:")
    print(f"  Min: {gray.min()}, Max: {gray.max()}, Mean: {gray.mean():.1f}")
    
    # Try different approaches
    results = {}
    
    # 1. Current approach: threshold BINARY_INV
    _, binary1 = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binary1 = cv2.morphologyEx(binary1, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours1, _ = cv2.findContours(binary1, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    results['Current_BINARY_INV'] = (binary1, contours1)
    
    # 2. Detect non-white areas (white page = 255)
    _, binary2 = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    binary2 = cv2.morphologyEx(binary2, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours2, _ = cv2.findContours(binary2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    results['High_threshold_250'] = (binary2, contours2)
    
    # 3. Canny edge detection
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours3, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    results['Canny_edges'] = (edges, contours3)
    
    # Show results
    print(f"\n{'='*60}")
    for name, (binary, contours) in results.items():
        # Filter by area
        filtered = [c for c in contours if cv2.contourArea(c) > 1000]
        print(f"\n{name}:")
        print(f"  Total contours: {len(contours)}")
        print(f"  Filtered (>1000px²): {len(filtered)}")
        
        # Show bounding boxes
        for i, c in enumerate(filtered[:5]):  # Show first 5
            x, y, w, h = cv2.boundingRect(c)
            area = cv2.contourArea(c)
            print(f"    [{i+1}] Pos=({x},{y}) Size={w}x{h} Area={area:.0f}")
        
        # Save debug image
        output = cv2.cvtColor(img_crop.copy(), cv2.COLOR_BGR2RGB)
        for c in filtered:
            x, y, w, h = cv2.boundingRect(c)
            cv2.rectangle(output, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
        output_path = f"dev/debug_{name}.png"
        cv2.imwrite(output_path, cv2.cvtColor(output, cv2.COLOR_RGB2BGR))
        print(f"  Saved: {output_path}")

if __name__ == "__main__":
    team = sys.argv[1] if len(sys.argv) > 1 else "kasrkin"
    threshold = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    
    pdf_path = f"processed/{team}/{team}-faction-rules.pdf"
    debug_contours(pdf_path, threshold)
