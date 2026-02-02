#!/usr/bin/env python3
"""Compare dimensions of cards between output and output_v2."""

from pathlib import Path
import cv2
from collections import defaultdict

def analyze_dimensions(base_path: Path, label: str):
    """Analyze all image dimensions in a directory."""
    dims = defaultdict(int)
    
    for img_path in base_path.rglob('*.jpg'):
        img = cv2.imread(str(img_path))
        if img is not None:
            h, w = img.shape[:2]
            dims[f'{w}x{h}'] += 1
    
    print(f"\n{label} dimensions:")
    print("=" * 60)
    for dim, count in sorted(dims.items()):
        print(f"  {dim}: {count} cards")
    
    return dims

def main():
    output_new = Path('output')
    output_old = Path('output_v2')
    
    print("\nANALYZING IMAGE DIMENSIONS")
    print("=" * 60)
    
    dims_new = analyze_dimensions(output_new, "NEW (output)")
    dims_old = analyze_dimensions(output_old, "OLD (output_v2)")
    
    print("\n\nDIMENSION COMPARISON:")
    print("=" * 60)
    
    all_dims = set(dims_new.keys()) | set(dims_old.keys())
    
    for dim in sorted(all_dims):
        count_new = dims_new.get(dim, 0)
        count_old = dims_old.get(dim, 0)
        
        if count_new > 0 and count_old > 0:
            if count_new != count_old:
                print(f"  {dim}: NEW={count_new}, OLD={count_old} (DIFFERENT COUNTS)")
            else:
                print(f"  {dim}: {count_new} cards (MATCH)")
        elif count_new > 0:
            print(f"  {dim}: ONLY in NEW ({count_new} cards)")
        else:
            print(f"  {dim}: ONLY in OLD ({count_old} cards)")

if __name__ == "__main__":
    main()
