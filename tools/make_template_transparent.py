"""
Make white parts of template images transparent.

This script processes template-card-*.png files to convert pure white (#FFFFFF)
pixels to transparent, while keeping all other pixels as solid white.
This creates rounded corner masks where white = cut out (transparent).
"""

from pathlib import Path
from PIL import Image
import numpy as np


def make_white_transparent(image_path: Path, output_path: Path = None):
    """
    Convert pure white pixels to transparent in an image.
    Then convert all remaining non-transparent pixels to full white.
    
    Args:
        image_path: Path to input image
        output_path: Path to save output (defaults to overwriting input)
    """
    if output_path is None:
        output_path = image_path
    
    # Load image
    img = Image.open(image_path).convert('RGBA')
    data = np.array(img)
    
    # Find pure white pixels (R=255, G=255, B=255)
    white_pixels = (data[:, :, 0] == 255) & (data[:, :, 1] == 255) & (data[:, :, 2] == 255)
    
    # Set alpha channel to 0 (transparent) for white pixels
    data[white_pixels, 3] = 0
    
    # Find all non-transparent pixels (alpha > 0)
    non_transparent = data[:, :, 3] > 0
    
    # Set all non-transparent pixels to full white with full opacity
    data[non_transparent, 0] = 255  # R
    data[non_transparent, 1] = 255  # G
    data[non_transparent, 2] = 255  # B
    data[non_transparent, 3] = 255  # A
    
    # Convert back to image and save
    result = Image.fromarray(data, 'RGBA')
    result.save(output_path)
    print(f"Processed: {output_path.name}")
    print(f"  - Made {white_pixels.sum():,} white pixels transparent")
    print(f"  - Set {non_transparent.sum():,} non-transparent pixels to full white")


if __name__ == '__main__':
    config_dir = Path('config/pipelines/warcom')
    
    # Process both template files
    for template_file in config_dir.glob('template-card-*.png'):
        print(f"\nProcessing {template_file.name}...")
        make_white_transparent(template_file)
    
    print("\n✓ All templates processed!")
