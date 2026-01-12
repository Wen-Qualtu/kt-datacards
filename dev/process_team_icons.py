#!/usr/bin/env python3
"""
Process team icon images to create clean icons and custom card backsides.

The downloaded images (500x500) contain the team icon and name.
This script extracts just the icon portion (centered circle).
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import json


def analyze_icon(img_path):
    """Analyze an icon to understand its structure."""
    img = Image.open(img_path)
    print(f"\n{img_path.name}")
    print(f"  Size: {img.size}")
    print(f"  Mode: {img.mode}")
    
    # Sample some pixels to see the structure
    width, height = img.size
    center_x, center_y = width // 2, height // 2
    
    print(f"  Center pixel: {img.getpixel((center_x, center_y))}")
    print(f"  Top pixel: {img.getpixel((center_x, 10))}")
    print(f"  Bottom pixel: {img.getpixel((center_x, height - 10))}")


def extract_icon_circle(img_path, output_path, icon_size=400):
    """
    Extract the circular icon from the 500x500 image.
    
    The icon appears to be centered in the image. We'll crop to the
    center circular region.
    """
    img = Image.open(img_path)
    width, height = img.size
    
    # The icon is likely in the upper portion (team name at bottom)
    # Estimate icon center and radius
    center_x = width // 2
    center_y = int(height * 0.4)  # Icon likely in upper 40%
    radius = min(icon_size // 2, min(center_x, center_y))
    
    # Crop to square around icon
    left = center_x - radius
    top = center_y - radius
    right = center_x + radius
    bottom = center_y + radius
    
    icon = img.crop((left, top, right, bottom))
    icon.save(output_path)
    
    return icon.size


def create_custom_backside(icon_path, team_name, output_path, card_width=750, card_height=1050):
    """
    Create a custom card backside using the team icon.
    
    Design:
    - Background: Dark/themed color
    - Centered team icon
    - Optional: Team name text
    - Optional: Decorative border
    """
    # Create card background
    card = Image.new('RGB', (card_width, card_height), color=(20, 20, 25))
    
    # Load and resize icon
    icon = Image.open(icon_path)
    icon_size = min(card_width // 2, card_height // 3)
    icon = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
    
    # Center icon on card
    icon_x = (card_width - icon_size) // 2
    icon_y = (card_height - icon_size) // 2
    
    # Paste icon (with alpha if available)
    if icon.mode == 'RGBA':
        card.paste(icon, (icon_x, icon_y), icon)
    else:
        card.paste(icon, (icon_x, icon_y))
    
    # Save
    card.save(output_path, 'JPEG', quality=95)
    
    return card.size


def main():
    """Process all downloaded team icons."""
    project_root = Path(__file__).parent.parent
    raw_icons_dir = project_root / "config" / "team-icons-raw"
    processed_icons_dir = project_root / "config" / "team-icons"
    backsides_dir = project_root / "config" / "card-backside" / "team-generated"
    
    # Create output directories
    processed_icons_dir.mkdir(parents=True, exist_ok=True)
    backsides_dir.mkdir(parents=True, exist_ok=True)
    
    # Load metadata
    metadata_file = raw_icons_dir / "teams_metadata.json"
    with open(metadata_file, 'r', encoding='utf-8') as f:
        teams = json.load(f)
    
    print("Processing Team Icons")
    print("=" * 60)
    print(f"\nAnalyzing first icon to understand structure...")
    
    # Analyze first icon
    first_icon = raw_icons_dir / f"{teams[0]['slug']}.png"
    analyze_icon(first_icon)
    
    print(f"\n\nProcessing {len(teams)} team icons...")
    print("\nExtracting icon circles...")
    
    for team in teams:
        slug = team['slug']
        name = team['name']
        
        raw_path = raw_icons_dir / f"{slug}.png"
        if not raw_path.exists():
            print(f"  ⚠ Missing: {slug}")
            continue
        
        # Extract icon
        icon_path = processed_icons_dir / f"{slug}-icon.png"
        try:
            size = extract_icon_circle(raw_path, icon_path)
            print(f"  ✓ {name:<30} -> {icon_path.name}")
        except Exception as e:
            print(f"  ✗ {name:<30} Error: {e}")
    
    print(f"\n✓ Icons extracted to {processed_icons_dir}")
    
    print("\nNote: Creating custom backsides requires manual design.")
    print("The extracted icons can now be used to design custom card backsides")
    print("using image editing software or additional Python scripts.")


if __name__ == "__main__":
    main()
