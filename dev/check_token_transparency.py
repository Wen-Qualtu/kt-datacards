"""
Visual checker for token transparency.
Shows token with transparency and statistics.
"""

import sys
from pathlib import Path
from PIL import Image
import numpy as np

def check_token(team_name: str, token_name: str):
    """Check a specific token's transparency."""
    
    # Check in extracted tokens
    extracted_path = Path(f'dev/extracted-tokens/{team_name}/{token_name}.png')
    # Check in output
    output_path = Path(f'output_v2') / '*' / team_name / 'tts' / 'token' / f'{team_name}-{token_name}.png'
    
    paths_to_check = []
    if extracted_path.exists():
        paths_to_check.append(('Extracted', extracted_path))
    
    # Find output path
    from glob import glob
    output_files = glob(str(output_path))
    if output_files:
        paths_to_check.append(('Output', Path(output_files[0])))
    
    if not paths_to_check:
        print(f"❌ Token not found: {token_name}")
        return
    
    for location, path in paths_to_check:
        print(f"\n{'='*60}")
        print(f"{location}: {path.name}")
        print('='*60)
        
        img = Image.open(path)
        data = np.array(img)
        
        print(f"Mode: {img.mode}")
        print(f"Size: {img.size}")
        
        if img.mode == 'RGBA':
            alpha = data[:,:,3]
            total_pixels = alpha.size
            
            transparent = np.sum(alpha == 0)
            semi_trans = np.sum((alpha > 0) & (alpha < 255))
            opaque = np.sum(alpha == 255)
            
            print(f"\nAlpha Statistics:")
            print(f"  Transparent:     {transparent:6} ({transparent/total_pixels*100:5.1f}%)")
            print(f"  Semi-transparent:{semi_trans:6} ({semi_trans/total_pixels*100:5.1f}%)")
            print(f"  Opaque:          {opaque:6} ({opaque/total_pixels*100:5.1f}%)")
            
            # Check corners
            h, w = data.shape[:2]
            print(f"\nCorner Alpha Values:")
            corners = {
                'Top-Left':     (0, 0),
                'Top-Right':    (0, w-1),
                'Bottom-Left':  (h-1, 0),
                'Bottom-Right': (h-1, w-1)
            }
            
            for name, (y, x) in corners.items():
                a = alpha[y, x]
                status = 'transparent' if a == 0 else ('opaque' if a == 255 else f'semi ({a})')
                print(f"  {name:15}: {status}")
        else:
            print("❌ No alpha channel!")

def main():
    if len(sys.argv) < 3:
        print("Usage: python check_token_transparency.py <team-name> <token-name>")
        print("Example: python check_token_transparency.py farstalker-kinband meat")
        sys.exit(1)
    
    team_name = sys.argv[1]
    token_name = sys.argv[2]
    
    check_token(team_name, token_name)

if __name__ == '__main__':
    main()
