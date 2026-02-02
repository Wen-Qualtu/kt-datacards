"""
Make all non-transparent pixels fully white.
"""
import cv2
import numpy as np
from pathlib import Path
import sys

def make_opaque_white(image_path: Path, output_path: Path = None):
    """
    Make all non-transparent (opaque) pixels fully white.
    
    Args:
        image_path: Path to input image
        output_path: Path to save output (if None, overwrites input)
    """
    # Read image with alpha channel
    img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"Failed to load image: {image_path}")
        return False
    
    # Ensure image has alpha channel
    if img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    
    # Create mask for non-transparent pixels (alpha > 0)
    opaque_mask = img[:, :, 3] > 0
    
    # Set RGB to white (255, 255, 255) for all non-transparent pixels
    img[opaque_mask, 0] = 255  # B
    img[opaque_mask, 1] = 255  # G
    img[opaque_mask, 2] = 255  # R
    
    # Save
    output = output_path if output_path else image_path
    cv2.imwrite(str(output), img)
    print(f"Made opaque pixels white: {output}")
    print(f"  Modified {np.sum(opaque_mask)} pixels to white")
    
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python make_opaque_white.py <image_path>")
        print("  image_path: Path to image file")
        sys.exit(1)
    
    image_path = Path(sys.argv[1])
    
    if not image_path.exists():
        print(f"Error: Image not found: {image_path}")
        sys.exit(1)
    
    success = make_opaque_white(image_path)
    sys.exit(0 if success else 1)
