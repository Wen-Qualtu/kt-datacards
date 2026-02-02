#!/usr/bin/env python3
"""Convert white pixels to transparent in overlay templates."""

import cv2
import numpy as np
from pathlib import Path

def make_white_transparent(image_path: Path):
    """Convert white pixels to transparent in an image."""
    
    # Read image
    img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    
    if img is None:
        print(f"ERROR: Could not load {image_path}")
        return False
    
    # Convert to BGRA if needed
    if img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    
    # Get dimensions
    height, width = img.shape[:2]
    
    # Create mask for white pixels (and near-white)
    # White is BGR(255, 255, 255), we'll use a threshold to catch near-white too
    threshold = 250  # Pixels with all channels >= 250 are considered white
    
    white_mask = (img[:, :, 0] >= threshold) & \
                 (img[:, :, 1] >= threshold) & \
                 (img[:, :, 2] >= threshold)
    
    # Set alpha channel to 0 (transparent) where pixels are white
    img[:, :, 3] = np.where(white_mask, 0, 255)
    
    # Count how many pixels were made transparent
    transparent_pixels = np.sum(white_mask)
    total_pixels = width * height
    percent = (transparent_pixels / total_pixels) * 100
    
    # Save result
    cv2.imwrite(str(image_path), img)
    
    print(f"✓ {image_path.name}")
    print(f"  Dimensions: {width}×{height}")
    print(f"  Made transparent: {transparent_pixels:,} pixels ({percent:.1f}%)")
    
    return True


def main():
    config_dir = Path('config/pipelines/warcom')
    
    templates = [
        config_dir / 'corner-overlay-portrait.png',
        config_dir / 'corner-overlay-landscape.png'
    ]
    
    print("=" * 60)
    print("CONVERTING WHITE TO TRANSPARENT IN OVERLAY TEMPLATES")
    print("=" * 60)
    print()
    
    for template_path in templates:
        if not template_path.exists():
            print(f"⚠ SKIPPED: {template_path.name} (not found)")
            print()
            continue
        
        make_white_transparent(template_path)
        print()
    
    print("=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
