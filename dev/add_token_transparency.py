"""
Add transparency to extracted token images by removing white/light backgrounds.

This converts RGB token images to RGBA with transparent backgrounds,
which is required for TTS to properly cut out token shapes.
"""

import argparse
from pathlib import Path
from PIL import Image
import numpy as np


def add_transparency(image_path: Path, threshold: int = 240, output_path: Path = None):
    """
    Add transparency to a token image by making white/light pixels transparent.
    
    Args:
        image_path: Path to input image
        threshold: Pixel brightness threshold (0-255). Pixels brighter than this become transparent.
        output_path: Path to save output (defaults to overwriting input)
    """
    # Load image
    img = Image.open(image_path)
    
    # Convert to RGBA if needed
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Convert to numpy array
    data = np.array(img)
    
    # Get RGB channels
    r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
    
    # Calculate brightness (average of RGB)
    brightness = (r.astype(int) + g.astype(int) + b.astype(int)) / 3
    
    # Make bright pixels transparent
    # Pixels brighter than threshold become fully transparent
    mask = brightness > threshold
    data[:,:,3] = np.where(mask, 0, 255)
    
    # Create new image
    result = Image.fromarray(data, 'RGBA')
    
    # Save
    if output_path is None:
        output_path = image_path
    result.save(output_path, 'PNG')
    
    return result


def process_team_tokens(team_name: str, 
                       tokens_dir: Path = Path('dev/extracted-tokens'),
                       threshold: int = 240):
    """
    Process all token images for a team.
    
    Args:
        team_name: Team name (e.g., 'farstalker-kinband')
        tokens_dir: Base directory containing extracted tokens
        threshold: Brightness threshold for transparency
    """
    team_dir = tokens_dir / team_name
    
    if not team_dir.exists():
        print(f"✗ Team directory not found: {team_dir}")
        return
    
    # Find all PNG files
    png_files = list(team_dir.glob('*.png'))
    
    if not png_files:
        print(f"✗ No PNG files found in {team_dir}")
        return
    
    print(f"\nProcessing {len(png_files)} tokens for {team_name}")
    print("=" * 60)
    
    for png_file in png_files:
        try:
            # Check if already has transparency
            img = Image.open(png_file)
            if img.mode == 'RGBA':
                # Check if it actually has transparent pixels
                data = np.array(img)
                if np.any(data[:,:,3] < 255):
                    print(f"  ⊘ Skipping {png_file.name} (already has transparency)")
                    continue
            
            # Add transparency
            add_transparency(png_file, threshold=threshold)
            print(f"  ✓ Added transparency: {png_file.name}")
            
        except Exception as e:
            print(f"  ✗ Error processing {png_file.name}: {e}")
    
    print(f"\n✓ Completed processing tokens for {team_name}")


def main():
    parser = argparse.ArgumentParser(description='Add transparency to extracted token images')
    parser.add_argument('--team', type=str, required=True,
                       help='Team name (e.g., farstalker-kinband)')
    parser.add_argument('--tokens-dir', type=str, default='dev/extracted-tokens',
                       help='Directory with extracted token images')
    parser.add_argument('--threshold', type=int, default=240,
                       help='Brightness threshold (0-255) for transparency')
    
    args = parser.parse_args()
    
    tokens_dir = Path(args.tokens_dir)
    
    process_team_tokens(
        team_name=args.team,
        tokens_dir=tokens_dir,
        threshold=args.threshold
    )


if __name__ == '__main__':
    main()
