#!/usr/bin/env python3
"""Debug extraction to see all color families found."""

import sys
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from extract_token_colors import rgb_to_hsv

def debug_team(team_slug):
    """Debug color extraction for a specific team."""
    output_dir = Path("output")
    token_dir = output_dir / team_slug / "tokens"
    
    if not token_dir.exists():
        print(f"❌ {team_slug}: No tokens directory")
        return
    
    token_files = [f for f in token_dir.glob("*.png") if not f.stem.endswith('-icon')][:3]
    
    print(f"\n{'='*80}")
    print(f"Analyzing {team_slug}")
    print(f"{'='*80}")
    
    all_families = {}
    total_white_weight = 0.0
    
    for token_path in token_files:
        print(f"\nToken: {token_path.name}")
        img = Image.open(token_path).convert('RGB')
        img = img.resize((200, 200), Image.Resampling.LANCZOS)
        img_array = np.array(img)
        
        # Create center-weighted mask
        h, w = img_array.shape[:2]
        y, x = np.ogrid[:h, :w]
        center_y, center_x = h // 2, w // 2
        distance = np.sqrt((x - center_x)**2 + (y - center_y)**2)
        max_dist = np.sqrt(center_x**2 + center_y**2)
        weights = 1.0 - (distance / max_dist) * 0.8
        
        pixels = img_array.reshape(-1, 3)
        pixel_weights = weights.flatten()
        
        # Track white
        is_white = np.all(pixels >= 240, axis=1)
        white_w = np.sum(pixel_weights[is_white])
        total_white_weight += white_w
        print(f"  White weight: {white_w:.2f}")
        
        # Filter
        not_border = np.any(pixels < 250, axis=1)
        filtered_pixels = pixels[not_border]
        filtered_weights = pixel_weights[not_border]
        
        # Sample some colors
        for pixel, weight in list(zip(filtered_pixels, filtered_weights))[:10]:
            rgb = tuple(pixel)
            h_hsv, s, v = rgb_to_hsv(rgb)
            print(f"  Sample: rgb{rgb}  hsv({h_hsv:.0f}, {s:.2f}, {v:.2f})  weight={weight:.3f}")
    
    # Show top color families
    print(f"\nWhite total weight: {total_white_weight:.2f}")

if __name__ == "__main__":
    debug_team("celestian-insidiants")
