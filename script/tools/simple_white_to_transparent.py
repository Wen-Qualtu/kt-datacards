"""Simple script to make white/near-white pixels transparent in token images."""

import argparse
from pathlib import Path
import cv2
import numpy as np


def make_white_transparent(image_path: Path, output_path: Path, threshold: int = 240):
    """Make white/near-white pixels transparent.
    
    Args:
        image_path: Input image path
        output_path: Output image path
        threshold: Brightness threshold (0-255). Pixels with all RGB values >= this become transparent.
    """
    # Read image
    img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"  ✗ Failed to read: {image_path}")
        return False
    
    # Convert to BGRA if needed
    if len(img.shape) == 2:  # Grayscale
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:  # BGR
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    elif img.shape[2] == 4:  # Already BGRA
        pass
    else:
        print(f"  ✗ Unexpected image format: {img.shape}")
        return False
    
    # Split channels
    b, g, r, a = cv2.split(img)
    
    # Create mask: pixels where all RGB channels are >= threshold
    white_mask = (r >= threshold) & (g >= threshold) & (b >= threshold)
    
    # Set alpha to 0 for white pixels
    a[white_mask] = 0
    
    # Merge channels
    result = cv2.merge([b, g, r, a])
    
    # Save
    success = cv2.imwrite(str(output_path), result)
    if not success:
        print(f"  ✗ Failed to write: {output_path}")
        return False
    
    transparent_count = white_mask.sum()
    total_pixels = white_mask.size
    print(f"  ✓ {image_path.name}: {transparent_count}/{total_pixels} pixels made transparent ({100*transparent_count/total_pixels:.1f}%)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Make white pixels transparent in token images")
    parser.add_argument("--team", type=str, required=True, help="Team name")
    parser.add_argument("--tokens-dir", type=str, default="processed", help="Base tokens directory")
    parser.add_argument("--threshold", type=int, default=240, help="Brightness threshold (0-255, default: 240)")
    parser.add_argument("--output-suffix", type=str, default="-cut", help="Output folder suffix (default: -cut)")
    
    args = parser.parse_args()
    
    # Input and output paths
    input_dir = Path(args.tokens_dir) / args.team / "token"
    output_dir = Path(args.tokens_dir) / args.team / f"token{args.output_suffix}"
    
    if not input_dir.exists():
        print(f"✗ Input directory not found: {input_dir}")
        return 1
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process all PNG files
    png_files = list(input_dir.glob("*.png"))
    if not png_files:
        print(f"✗ No PNG files found in {input_dir}")
        return 1
    
    print(f"Processing {len(png_files)} tokens from {input_dir}...")
    print(f"Threshold: {args.threshold}")
    
    success_count = 0
    for png_path in png_files:
        # Skip debug files
        if png_path.name.startswith("_"):
            continue
        
        output_path = output_dir / png_path.name
        if make_white_transparent(png_path, output_path, args.threshold):
            success_count += 1
    
    print(f"\nDone! Processed {success_count}/{len(png_files)} files")
    print(f"Output: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
