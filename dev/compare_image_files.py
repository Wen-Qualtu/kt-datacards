#!/usr/bin/env python3
"""Compare two image files to show differences in dimensions, file size, and format."""

from PIL import Image
import os
import sys

def compare_images(new_path: str, old_path: str):
    """Compare two image files and print their properties."""
    
    # Load images
    img_new = Image.open(new_path)
    img_old = Image.open(old_path)
    
    # Get file sizes
    size_new = os.path.getsize(new_path)
    size_old = os.path.getsize(old_path)
    
    print("=" * 80)
    print("IMAGE COMPARISON")
    print("=" * 80)
    
    print("\nNEW (Warcom Pipeline):")
    print(f"  Path: {new_path}")
    print(f"  Dimensions: {img_new.size[0]}x{img_new.size[1]} pixels")
    print(f"  File size: {size_new:,} bytes ({size_new/1024:.1f} KB)")
    print(f"  Format: {img_new.format}")
    print(f"  Mode: {img_new.mode}")
    print(f"  Has alpha: {img_new.mode == 'RGBA'}")
    
    print("\nOLD (KT-App Pipeline):")
    print(f"  Path: {old_path}")
    print(f"  Dimensions: {img_old.size[0]}x{img_old.size[1]} pixels")
    print(f"  File size: {size_old:,} bytes ({size_old/1024:.1f} KB)")
    print(f"  Format: {img_old.format}")
    print(f"  Mode: {img_old.mode}")
    print(f"  Has alpha: {img_old.mode == 'RGBA'}")
    
    print("\n" + "=" * 80)
    print("DIFFERENCES")
    print("=" * 80)
    
    width_diff = img_new.size[0] - img_old.size[0]
    height_diff = img_new.size[1] - img_old.size[1]
    size_diff = size_new - size_old
    
    print(f"\nDimensions:")
    print(f"  Width: {width_diff:+d} pixels ({img_new.size[0]} vs {img_old.size[0]})")
    print(f"  Height: {height_diff:+d} pixels ({img_new.size[1]} vs {img_old.size[1]})")
    
    print(f"\nFile Size:")
    print(f"  Difference: {size_diff:+,} bytes ({size_diff/1024:+.1f} KB)")
    print(f"  Ratio: {size_new/size_old:.2f}x")
    print(f"  Percent change: {((size_new/size_old - 1) * 100):+.1f}%")
    
    print(f"\nFormat:")
    print(f"  New: {img_new.format} ({img_new.mode})")
    print(f"  Old: {img_old.format} ({img_old.mode})")
    
    if img_new.mode == 'RGBA' and img_old.mode != 'RGBA':
        print(f"\n  ⚠️  New image has transparency (alpha channel), old does not")
        print(f"      This adds ~33% overhead for the alpha channel data")


if __name__ == "__main__":
    new_path = "output/angels-of-death/cards/datacards/angels-of-death-assault-intercessor-grenadier-front.jpg"
    old_path = "output_v2/imperium/angels-of-death/datacards/angels-of-death-assault-intercessor-grenadier_front.jpg"
    
    if not os.path.exists(new_path):
        print(f"ERROR: New file not found: {new_path}")
        sys.exit(1)
    
    if not os.path.exists(old_path):
        print(f"ERROR: Old file not found: {old_path}")
        sys.exit(1)
    
    compare_images(new_path, old_path)
