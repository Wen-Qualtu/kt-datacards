"""
Visualize the exact coordinates provided by user.
"""
import cv2
import numpy as np
from pathlib import Path


def visualize_extraction_areas():
    """Draw the extraction areas on clean images."""
    
    # Coordinates provided by user
    # Page 1 (1191x1684)
    portrait = {'x1': 29, 'y1': 1, 'x2': 193, 'y2': 223}
    landscape = {'x1': 1, 'y1': 39, 'x2': 219, 'y2': 173}
    
    # Page 12 (1219x1588) 
    token = {'x1': 157, 'y1': 258, 'x2': 332, 'y2': 415}
    
    # Initialize percentage variables
    port_x1_pct = port_y1_pct = port_x2_pct = port_y2_pct = 0
    land_x1_pct = land_y1_pct = land_x2_pct = land_y2_pct = 0
    tok_x1_pct = tok_y1_pct = tok_x2_pct = tok_y2_pct = 0
    
    print("=" * 60)
    print("Visualizing Extraction Areas")
    print("=" * 60)
    
    # Process page 1
    print("\nPage 1 (card backsides):")
    img_path = Path('dev/angels-of-death_page1_clean.png')
    if img_path.exists():
        img = cv2.imread(str(img_path))
        height, width = img.shape[:2]
        print(f"  Image size: {width}x{height}")
        
        # Draw portrait (green)
        cv2.rectangle(img, (portrait['x1'], portrait['y1']), 
                     (portrait['x2'], portrait['y2']), (0, 255, 0), 3)
        cv2.putText(img, "Portrait", (portrait['x1'], portrait['y1'] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
        
        # Draw landscape (blue)
        cv2.rectangle(img, (landscape['x1'], landscape['y1']), 
                     (landscape['x2'], landscape['y2']), (255, 0, 0), 3)
        cv2.putText(img, "Landscape", (landscape['x1'], landscape['y2'] + 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 0, 0), 3)
        
        # Calculate percentages for code
        port_x1_pct = portrait['x1'] / width
        port_y1_pct = portrait['y1'] / height
        port_x2_pct = portrait['x2'] / width
        port_y2_pct = portrait['y2'] / height
        
        land_x1_pct = landscape['x1'] / width
        land_y1_pct = landscape['y1'] / height
        land_x2_pct = landscape['x2'] / width
        land_y2_pct = landscape['y2'] / height
        
        print(f"  Portrait: {portrait['x2']-portrait['x1']}x{portrait['y2']-portrait['y1']} pixels")
        print(f"    Percentages: x1={port_x1_pct:.4f} y1={port_y1_pct:.4f} x2={port_x2_pct:.4f} y2={port_y2_pct:.4f}")
        
        print(f"  Landscape: {landscape['x2']-landscape['x1']}x{landscape['y2']-landscape['y1']} pixels")
        print(f"    Percentages: x1={land_x1_pct:.4f} y1={land_y1_pct:.4f} x2={land_x2_pct:.4f} y2={land_y2_pct:.4f}")
        
        # Save visualization
        output_path = Path('dev/page1_extraction_preview.png')
        cv2.imwrite(str(output_path), img)
        print(f"  ✓ Saved: {output_path.name}")
    
    # Process page 12
    print("\nPage 12 (token bag icon):")
    img_path = Path('dev/angels-of-death_page12_clean.png')
    if img_path.exists():
        img = cv2.imread(str(img_path))
        height, width = img.shape[:2]
        print(f"  Image size: {width}x{height}")
        
        # Draw token bag area (green)
        cv2.rectangle(img, (token['x1'], token['y1']), 
                     (token['x2'], token['y2']), (0, 255, 0), 3)
        cv2.putText(img, "Token Bag", (token['x1'], token['y1'] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
        
        # Add corner dots
        cv2.circle(img, (token['x1'], token['y1']), 8, (255, 0, 0), -1)
        cv2.circle(img, (token['x2'], token['y1']), 8, (255, 0, 0), -1)
        cv2.circle(img, (token['x1'], token['y2']), 8, (255, 0, 0), -1)
        cv2.circle(img, (token['x2'], token['y2']), 8, (255, 0, 0), -1)
        
        # Calculate percentages for code
        tok_x1_pct = token['x1'] / width
        tok_y1_pct = token['y1'] / height
        tok_x2_pct = token['x2'] / width
        tok_y2_pct = token['y2'] / height
        
        print(f"  Token bag: {token['x2']-token['x1']}x{token['y2']-token['y1']} pixels")
        print(f"    Percentages: x1={tok_x1_pct:.4f} y1={tok_y1_pct:.4f} x2={tok_x2_pct:.4f} y2={tok_y2_pct:.4f}")
        
        # Save visualization
        output_path = Path('dev/page12_extraction_preview.png')
        cv2.imwrite(str(output_path), img)
        print(f"  ✓ Saved: {output_path.name}")
    
    print("\n" + "=" * 60)
    print("Code-ready coordinates:")
    print("=" * 60)
    print(f"""
# Page 1 - Card backside icons
PORTRAIT_ICON_X1 = {port_x1_pct:.4f}
PORTRAIT_ICON_Y1 = {port_y1_pct:.4f}
PORTRAIT_ICON_X2 = {port_x2_pct:.4f}
PORTRAIT_ICON_Y2 = {port_y2_pct:.4f}

LANDSCAPE_ICON_X1 = {land_x1_pct:.4f}
LANDSCAPE_ICON_Y1 = {land_y1_pct:.4f}
LANDSCAPE_ICON_X2 = {land_x2_pct:.4f}
LANDSCAPE_ICON_Y2 = {land_y2_pct:.4f}

# Token bag icon page
TOKEN_ICON_X1 = {tok_x1_pct:.4f}
TOKEN_ICON_Y1 = {tok_y1_pct:.4f}
TOKEN_ICON_X2 = {tok_x2_pct:.4f}
TOKEN_ICON_Y2 = {tok_y2_pct:.4f}
""")


if __name__ == '__main__':
    visualize_extraction_areas()
