"""
Add transparency to extracted token images by removing white/light backgrounds.

This converts RGB token images to RGBA with transparent backgrounds,
which is required for TTS to properly cut out token shapes.

Updated version uses flood fill from corners to detect background.
"""

import argparse
from pathlib import Path
from PIL import Image
import numpy as np
import cv2


def add_transparency(image_path: Path, threshold: int = 50, output_path: Path = None, aggressive: bool = True):
    """
    Add transparency to a token image by removing background.
    Uses flood fill from corners to detect and remove background areas.
    Preserves original RGB colors - only modifies alpha channel.
    
    Args:
        image_path: Path to input image
        threshold: Color distance threshold (0-255). Higher = more aggressive removal.
        output_path: Path to save output (defaults to overwriting input)
        aggressive: If True, uses flood fill from corners. If False, uses brightness threshold.
    """
    # Load image
    img = Image.open(image_path)
    
    # Store original RGB to prevent color changes
    original_img = img.convert('RGB')
    original_rgb = np.array(original_img)
    
    # Convert to RGBA if needed
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Convert to numpy array
    data = np.array(img).copy()
    height, width = data.shape[:2]
    
    if aggressive:
        # Use flood fill from corners to detect background
        # Sample corner colors (background is usually in corners)
        corners = [
            (0, 0), (0, width-1), 
            (height-1, 0), (height-1, width-1),
            (0, width//2), (height//2, 0),
            (height-1, width//2), (height//2, width-1)
        ]
        
        # Get average corner color
        corner_colors = []
        for y, x in corners:
            if 0 <= y < height and 0 <= x < width:
                corner_colors.append(data[y, x, :3])
        
        if corner_colors:
            avg_corner_color = np.mean(corner_colors, axis=0)
            
            # Calculate color distance from background color
            r, g, b = data[:,:,0], data[:,:,1], data[:,:,2]
            color_distance = np.sqrt(
                (r - avg_corner_color[0])**2 + 
                (g - avg_corner_color[1])**2 + 
                (b - avg_corner_color[2])**2
            )
            
            # Pixels close to background color become transparent
            # Use adaptive threshold based on image
            adaptive_threshold = min(threshold, color_distance[color_distance > 0].std() * 2) if (color_distance > 0).any() else threshold
            
            # Create alpha based on color distance
            # Smooth transition using gradient
            gradient_range = 30
            
            fully_transparent = color_distance < adaptive_threshold
            in_gradient = (color_distance >= adaptive_threshold) & (color_distance < adaptive_threshold + gradient_range)
            
            # Calculate gradient alpha
            gradient_alpha = np.zeros_like(color_distance, dtype=np.uint8)
            gradient_alpha[in_gradient] = ((color_distance[in_gradient] - adaptive_threshold) / gradient_range * 255).astype(np.uint8)
            
            # Combine: transparent for background, gradient at edges, opaque for token
            new_alpha = np.where(fully_transparent, 0,
                        np.where(in_gradient, gradient_alpha, 255))
            
            # Clean up isolated pixels and small artifacts
            # Erode slightly to remove stray pixels, then dilate back
            kernel = np.ones((3, 3), np.uint8)
            
            # Only process the binary mask (fully transparent vs not)
            binary_mask = (new_alpha > 0).astype(np.uint8) * 255
            
            # Remove small isolated transparent regions (holes in token)
            binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            
            # Remove small isolated opaque regions (stray pixels outside token)
            binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel, iterations=2)  # More aggressive
            
            # Apply cleaned mask while preserving gradient values
            cleaned_alpha = np.where(binary_mask > 0, new_alpha, 0)
            
            # CRITICAL: Restore original RGB to prevent color changes
            data[:,:,0:3] = original_rgb
            data[:,:,3] = cleaned_alpha
    else:
        # Simple brightness-based transparency (original method)
        r, g, b = data[:,:,0], data[:,:,1], data[:,:,2]
        brightness = (r.astype(int) + g.astype(int) + b.astype(int)) / 3
        
        gradient_range = 20
        fully_transparent = brightness > threshold
        in_gradient = (brightness > (threshold - gradient_range)) & (brightness <= threshold)
        
        gradient_alpha = np.zeros_like(brightness, dtype=np.uint8)
        gradient_alpha[in_gradient] = ((threshold - brightness[in_gradient]) / gradient_range * 255).astype(np.uint8)
        
        new_alpha = np.where(fully_transparent, 0, 
                    np.where(in_gradient, gradient_alpha, 255))
        
        data[:,:,3] = new_alpha
    
    # Create new image
    result = Image.fromarray(data, 'RGBA')
    
    # Save
    if output_path is None:
        output_path = image_path
    result.save(output_path, 'PNG')
    
    return result


def process_team_tokens(team_name: str, 
                       tokens_dir: Path = Path('dev/extracted-tokens'),
                       threshold: int = 50,
                       aggressive: bool = True):
    """
    Process all token images for a team.
    
    Args:
        team_name: Team name (e.g., 'farstalker-kinband')
        tokens_dir: Base directory containing extracted tokens
        threshold: Color distance threshold for transparency
        aggressive: Use flood fill method (True) or brightness method (False)
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
    print(f"Method: {'Flood fill (aggressive)' if aggressive else 'Brightness threshold'}")
    print(f"Threshold: {threshold}")
    print("=" * 60)
    
    for png_file in png_files:
        try:
            # Always reprocess to ensure clean transparency
            add_transparency(png_file, threshold=threshold, aggressive=aggressive)
            print(f"  ✓ {png_file.name}")
            
        except Exception as e:
            print(f"  ✗ Error processing {png_file.name}: {e}")
    
    print(f"\n✓ Completed processing tokens for {team_name}")


def main():
    parser = argparse.ArgumentParser(description='Add transparency to extracted token images')
    parser.add_argument('--team', type=str, required=True,
                       help='Team name (e.g., farstalker-kinband)')
    parser.add_argument('--tokens-dir', type=str, default='dev/extracted-tokens',
                       help='Directory with extracted token images')
    parser.add_argument('--threshold', type=int, default=50,
                       help='Color distance threshold (0-255) for transparency (default: 50)')
    parser.add_argument('--simple', action='store_true',
                       help='Use simple brightness method instead of flood fill')
    
    args = parser.parse_args()
    
    tokens_dir = Path(args.tokens_dir)
    
    process_team_tokens(
        team_name=args.team,
        tokens_dir=tokens_dir,
        threshold=args.threshold,
        aggressive=not args.simple
    )


if __name__ == '__main__':
    main()
