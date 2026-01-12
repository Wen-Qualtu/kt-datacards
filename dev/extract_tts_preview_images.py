#!/usr/bin/env python3
"""
Extract TTS preview images from card-box textures.

For TTS saved objects, a .png with the same name as the .json results in
the image shown in the interface. This script extracts the front face of
the card box texture (the same part used in the 3D box) as a preview image.
"""

from pathlib import Path
from PIL import Image
import sys


def extract_box_front(texture_path: Path, output_path: Path):
    """
    Extract the front face of the box from the texture.
    
    The UV mapping for the front face is approximately:
    - U: 0.501 to 0.996 (right side of texture)
    - V: 0.290 to 0.997 (most of the height)
    
    Args:
        texture_path: Path to the card-box-texture.jpg file
        output_path: Path to save the extracted preview image
    """
    # Open the texture
    img = Image.open(texture_path)
    width, height = img.size
    
    # Calculate pixel coordinates from UV coordinates
    # UV coordinates from the .obj file for the front face
    u_min = 0.501027
    u_max = 0.995507
    v_min = 0.290230
    v_max = 0.996630
    
    # Convert to pixel coordinates
    # Note: V coordinates are flipped (0 is top in images, but bottom in UV)
    x_min = int(u_min * width)
    x_max = int(u_max * width)
    y_min = int((1 - v_max) * height)  # Flip V
    y_max = int((1 - v_min) * height)  # Flip V
    
    # Extract the region
    front_img = img.crop((x_min, y_min, x_max, y_max))
    
    # Save as PNG
    output_path.parent.mkdir(parents=True, exist_ok=True)
    front_img.save(output_path, 'PNG')
    
    print(f"  ✓ Extracted {front_img.size[0]}x{front_img.size[1]} preview: {output_path.name}")


def main():
    """Extract preview images for all teams that have card-box textures."""
    project_root = Path(__file__).parent.parent
    config_dir = project_root / "config"
    
    # Process team-specific boxes
    teams_dir = config_dir / "teams"
    if teams_dir.exists():
        print("Extracting team-specific preview images...")
        for team_folder in sorted(teams_dir.iterdir()):
            if not team_folder.is_dir():
                continue
            
            texture_path = team_folder / "box" / "card-box-texture.jpg"
            if not texture_path.exists():
                print(f"  ⚠ Skipping {team_folder.name}: no texture found")
                continue
            
            # Output to config/teams/{team}/tts-image/
            output_dir = team_folder / "tts-image"
            output_path = output_dir / f"{team_folder.name}-preview.png"
            
            print(f"\n{team_folder.name}:")
            extract_box_front(texture_path, output_path)
    
    # Process default box
    defaults_dir = config_dir / "defaults" / "box"
    default_texture = defaults_dir / "card-box-texture.jpg"
    if default_texture.exists():
        print("\ndefault:")
        output_dir = config_dir / "defaults" / "tts-image"
        output_path = output_dir / "default-preview.png"
        extract_box_front(default_texture, output_path)
    
    print("\n✓ All preview images extracted!")
    print("\nNext steps:")
    print("- Review the extracted images in config/teams/{team}/tts-image/")
    print("- Add a step to generate_tts_objects.py to copy these images")
    print("  with the correct name matching the TTS JSON object")


if __name__ == "__main__":
    main()
