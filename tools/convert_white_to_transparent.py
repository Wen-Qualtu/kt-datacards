"""
Convert white pixels in an image to transparent.
"""
import cv2
import numpy as np
from pathlib import Path
import sys

def convert_white_to_transparent(image_path: Path, output_path: Path = None, threshold: int = 250):
    """
    Convert white (or near-white) pixels to transparent.
    
    Args:
        image_path: Path to input image
        output_path: Path to save output (if None, overwrites input)
        threshold: RGB threshold for "white" (default 250 means R,G,B all >= 250)
    """
    # Read image
    img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"Failed to load image: {image_path}")
        return False
    
    # Convert to BGRA if not already
    if img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    
    # Create mask for white pixels (all RGB channels >= threshold)
    white_mask = (img[:, :, 0] >= threshold) & (img[:, :, 1] >= threshold) & (img[:, :, 2] >= threshold)
    
    # Set alpha channel to 0 for white pixels
    img[white_mask, 3] = 0
    
    # Save
    output = output_path if output_path else image_path
    cv2.imwrite(str(output), img)
    print(f"Converted white to transparent: {output}")
    print(f"  Made {np.sum(white_mask)} pixels transparent")
    
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python convert_white_to_transparent.py <image_path> [threshold]")
        print("  image_path: Path to image file")
        print("  threshold: Optional RGB threshold for 'white' (default: 250)")
        sys.exit(1)
    
    image_path = Path(sys.argv[1])
    threshold = int(sys.argv[2]) if len(sys.argv) > 2 else 250
    
    if not image_path.exists():
        print(f"Error: Image not found: {image_path}")
        sys.exit(1)
    
    success = convert_white_to_transparent(image_path, threshold=threshold)
    sys.exit(0 if success else 1)
