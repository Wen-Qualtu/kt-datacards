"""
Analyze operative token images to extract geometric measurements for mesh generation.
"""

import cv2
import numpy as np
from PIL import Image
import sys

def analyze_operative_token(image_path):
    """Analyze an operative token image to get shape measurements."""
    
    # Load image with alpha channel
    img_pil = Image.open(image_path)
    
    # Convert to numpy array
    img_array = np.array(img_pil)
    
    print(f"Image shape: {img_array.shape}")
    print(f"Image mode: {img_pil.mode}")
    
    # If RGBA, use alpha channel to get the token shape
    if img_array.shape[2] == 4:
        alpha = img_array[:, :, 3]
        # Non-transparent pixels are the token
        binary = (alpha > 10).astype(np.uint8) * 255
    else:
        # Convert to grayscale
        gray = cv2.cvtColor(img_array[:, :, :3], cv2.COLOR_RGB2GRAY)
        _, binary = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    
    height, width = binary.shape
    print(f"\nImage dimensions: {width}x{height} pixels")
    print(f"Aspect ratio (w/h): {width/height:.3f}")
    
    # Find all non-zero (token) pixels
    coords = np.column_stack(np.where(binary > 0))
    
    if len(coords) == 0:
        print("No token pixels found!")
        return
    
    # coords are in (y, x) format from np.where
    y_coords = coords[:, 0]
    x_coords = coords[:, 1]
    
    # Overall bounds
    top_y = np.min(y_coords)
    bottom_y = np.max(y_coords)
    left_x = np.min(x_coords)
    right_x = np.max(x_coords)
    
    token_width = right_x - left_x
    token_height = bottom_y - top_y
    
    print(f"\nToken bounds:")
    print(f"  Full width: {token_width} pixels")
    print(f"  Full height: {token_height} pixels")
    print(f"  Aspect ratio: {token_width/token_height:.3f}")
    
    # Analyze top region (characteristic two circles)
    top_threshold = top_y + int(token_height * 0.25)  # Top 25%
    top_mask = y_coords < top_threshold
    top_x = x_coords[top_mask]
    top_y_vals = y_coords[top_mask]
    
    if len(top_x) > 0:
        # Split into left and right halves
        mid_x = (left_x + right_x) / 2
        
        left_top = top_x[top_x < mid_x]
        right_top = top_x[top_x >= mid_x]
        
        if len(left_top) > 0 and len(right_top) > 0:
            left_center = np.mean(left_top)
            left_min = np.min(left_top)
            left_max = np.max(left_top)
            left_width = left_max - left_min
            
            right_center = np.mean(right_top)
            right_min = np.min(right_top)
            right_max = np.max(right_top)
            right_width = right_max - right_min
            
            gap_between = right_min - left_max
            center_distance = right_center - left_center
            
            print(f"\nTop circles analysis (top 25%):")
            print(f"  Left circle: center={left_center:.1f}, width={left_width:.1f} ({left_width/token_width:.3f} of total)")
            print(f"  Right circle: center={right_center:.1f}, width={right_width:.1f} ({right_width/token_width:.3f} of total)")
            print(f"  Gap between circles: {gap_between:.1f} pixels ({gap_between/token_width:.3f} of total)")
            print(f"  Center-to-center distance: {center_distance:.1f} pixels ({center_distance/token_width:.3f} of total)")
            
            # Normalize to -1 to 1 coordinate space
            print(f"\nNormalized coordinates (for OBJ, width = 2.0 units):")
            norm_left_center = ((left_center - left_x) / token_width) * 2.0 - 1.0
            norm_right_center = ((right_center - left_x) / token_width) * 2.0 - 1.0
            norm_left_radius = (left_width / token_width) * 1.0  # radius in normalized space
            norm_right_radius = (right_width / token_width) * 1.0
            norm_gap = (gap_between / token_width) * 2.0
            
            print(f"  Left circle center X: {norm_left_center:.3f}")
            print(f"  Right circle center X: {norm_right_center:.3f}")
            print(f"  Circle radius (approx): {norm_left_radius:.3f}")
            print(f"  Gap between: {norm_gap:.3f}")
    
    # Analyze width at different heights
    print(f"\nWidth profile (at different heights):")
    for pct in [10, 25, 40, 50, 60, 75, 90]:
        y_pos = top_y + int(token_height * (pct / 100))
        row_mask = y_coords == y_pos
        if np.any(row_mask):
            row_x = x_coords[row_mask]
            row_width = np.max(row_x) - np.min(row_x)
            print(f"  At {pct}% height: width={row_width} ({row_width/token_width:.3f} of max)")

if __name__ == "__main__":
    import sys
    token_path = sys.argv[1] if len(sys.argv) > 1 else "dev/extracted-tokens/farstalker-kinband/victory-shriek.png"
    analyze_operative_token(token_path)
