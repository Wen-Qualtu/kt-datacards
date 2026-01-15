"""
Generate 3D mesh (.obj) files from token PNG images.

Traces the alpha channel outline and creates a flat mesh matching the token shape.
"""

import argparse
from pathlib import Path
import cv2
import numpy as np
from PIL import Image


def generate_mesh_from_png(png_path: Path, output_path: Path, simplify: float = 2.0):
    """
    Generate an OBJ mesh file from a PNG's alpha channel.
    
    Args:
        png_path: Path to input PNG with alpha channel
        output_path: Path to output .obj file
        simplify: Contour simplification factor (higher = simpler mesh)
    """
    # Load image
    img = Image.open(png_path)
    img_array = np.array(img)
    
    if img_array.shape[2] < 4:
        raise ValueError(f"Image must have alpha channel: {png_path}")
    
    # Extract alpha channel
    alpha = img_array[:, :, 3]
    
    # Find contours
    contours, _ = cv2.findContours(
        (alpha > 10).astype(np.uint8) * 255,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )
    
    if not contours:
        raise ValueError(f"No contours found in image: {png_path}")
    
    # Use largest contour
    contour = max(contours, key=cv2.contourArea)
    
    # Simplify contour
    epsilon = simplify * cv2.arcLength(contour, True) / 100
    contour = cv2.approxPolyDP(contour, epsilon, True)
    
    # Normalize coordinates to -1 to 1 range
    h, w = alpha.shape
    max_dim = max(h, w)
    
    vertices = []
    tex_coords = []
    
    # Center point for fan triangulation
    center_x = w / 2.0
    center_y = h / 2.0
    
    # Normalized center
    norm_cx = (center_x / max_dim) * 2 - (w / max_dim)
    norm_cy = -((center_y / max_dim) * 2 - (h / max_dim))
    
    vertices.append((norm_cx, norm_cy, 0.0))
    tex_coords.append((0.5, 0.5))
    
    # Add contour points
    for point in contour:
        x, y = point[0]
        
        # Normalize to -1 to 1 range, centered
        norm_x = (x / max_dim) * 2 - (w / max_dim)
        norm_y = -((y / max_dim) * 2 - (h / max_dim))
        
        vertices.append((norm_x, norm_y, 0.0))
        
        # Texture coordinates (0 to 1)
        tex_x = x / w
        tex_y = y / h
        tex_coords.append((tex_x, tex_y))
    
    # Write OBJ file
    with open(output_path, 'w') as f:
        f.write(f"# Token mesh generated from {png_path.name}\n")
        f.write(f"# Vertices: {len(vertices)}\n\n")
        
        # Write vertices
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        
        f.write("\n")
        
        # Write texture coordinates
        for vt in tex_coords:
            f.write(f"vt {vt[0]:.6f} {vt[1]:.6f}\n")
        
        f.write("\n")
        
        # Write faces (fan triangulation from center)
        num_points = len(vertices) - 1  # Excluding center
        for i in range(num_points):
            next_i = (i + 1) % num_points
            # Face indices (1-based)
            f.write(f"f 1/1 {i+2}/{i+2} {next_i+2}/{next_i+2}\n")
    
    print(f"  Generated mesh: {len(vertices)} vertices, {num_points} faces")


def main():
    parser = argparse.ArgumentParser(description='Generate mesh files from token PNGs')
    parser.add_argument('--team', required=True, help='Team name')
    parser.add_argument('--simplify', type=float, default=2.0, 
                       help='Contour simplification (default: 2.0)')
    
    args = parser.parse_args()
    
    # Paths
    token_dir = Path('dev/extracted-tokens') / args.team
    output_dir = Path('output_v2')
    metadata_file = token_dir / 'extraction-metadata.json'
    
    if not metadata_file.exists():
        print(f"❌ Metadata not found: {metadata_file}")
        return
    
    import json
    with open(metadata_file) as f:
        metadata = json.load(f)
    
    # Determine faction
    import yaml
    with open('config/team-config.yaml') as f:
        config = yaml.safe_load(f)
        faction = config.get('teams', {}).get(args.team, {}).get('faction', 'unknown')
    
    output_token_dir = output_dir / faction / args.team / 'tts' / 'token'
    output_token_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🔧 Generating meshes for: {args.team}")
    print("=" * 60)
    
    for token_data in metadata['tokens']:
        filename = token_data['filename']
        shape = token_data['shape']
        
        # Only generate meshes for tokens (skip if already using template round mesh)
        png_path = token_dir / filename
        
        if not png_path.exists():
            print(f"  ⚠ Skipping {filename}: PNG not found")
            continue
        
        clean_name = filename.replace('.png', '')
        output_mesh = output_token_dir / f"{args.team}-{clean_name}.obj"
        
        try:
            print(f"  {token_data['name']:30} ({shape:8}) → {output_mesh.name}")
            generate_mesh_from_png(png_path, output_mesh, args.simplify)
        except Exception as e:
            print(f"    ✗ Failed: {e}")
    
    print(f"\n✓ Mesh generation complete!")
    print(f"  Output: {output_token_dir}")


if __name__ == '__main__':
    main()
