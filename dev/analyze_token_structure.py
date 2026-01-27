"""
Analyze the structure of working tokens from output_v2 to understand what we need to replicate.
"""

import cv2
import numpy as np
from PIL import Image
from pathlib import Path

def analyze_token(path: str):
    """Analyze a token's structure."""
    p = Path(path)
    if not p.exists():
        print(f"❌ Not found: {path}")
        return
    
    print(f"\n{'='*60}")
    print(f"Analyzing: {p.name}")
    print(f"{'='*60}")
    
    # Load with PIL
    pil_img = Image.open(path)
    print(f"PIL Mode: {pil_img.mode}")
    print(f"PIL Size: {pil_img.size}")
    
    # Load with OpenCV
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    print(f"OpenCV Shape: {img.shape}")
    
    if img.shape[2] == 4:
        # BGRA
        b, g, r, a = cv2.split(img)
        
        print(f"\nAlpha channel stats:")
        print(f"  Min: {a.min()}, Max: {a.max()}")
        print(f"  Mean: {a.mean():.2f}")
        print(f"  Transparent pixels (0): {(a == 0).sum()}")
        print(f"  Opaque pixels (255): {(a == 255).sum()}")
        print(f"  Semi-transparent: {((a > 0) & (a < 255)).sum()}")
        
        print(f"\nColor channel stats (where alpha > 0):")
        mask = a > 0
        if mask.sum() > 0:
            print(f"  R: min={r[mask].min()}, max={r[mask].max()}, mean={r[mask].mean():.2f}")
            print(f"  G: min={g[mask].min()}, max={g[mask].max()}, mean={g[mask].mean():.2f}")
            print(f"  B: min={b[mask].min()}, max={b[mask].max()}, mean={b[mask].mean():.2f}")
        
        # Find the content bounding box (where alpha > 0)
        coords = np.column_stack(np.where(a > 0))
        if len(coords) > 0:
            y_min, x_min = coords.min(axis=0)
            y_max, x_max = coords.max(axis=0)
            content_width = x_max - x_min + 1
            content_height = y_max - y_min + 1
            print(f"\nContent bounding box:")
            print(f"  Position: ({x_min}, {y_min}) to ({x_max}, {y_max})")
            print(f"  Size: {content_width}x{content_height}")
            print(f"  Center: ({(x_min + x_max) / 2:.1f}, {(y_min + y_max) / 2:.1f})")
            
            # Border sizes
            border_left = x_min
            border_right = img.shape[1] - x_max - 1
            border_top = y_min
            border_bottom = img.shape[0] - y_max - 1
            print(f"  Borders: L={border_left}, R={border_right}, T={border_top}, B={border_bottom}")

if __name__ == "__main__":
    # Analyze a few working tokens
    tokens = [
        "output_v2/imperium/kasrkin/tts/token/kasrkin-medic.png",
        "output_v2/imperium/kasrkin/tts/token/kasrkin-auspex-scan.png",
        "output_v2/imperium/kasrkin/tts/token/kasrkin-clearance-sweep.png",
        "output_v2/xenos/farstalker-kinband/tts/token/farstalker-kinband-call-the-kill.png",
    ]
    
    for token in tokens:
        analyze_token(token)
