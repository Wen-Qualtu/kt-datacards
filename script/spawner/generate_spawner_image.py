#!/usr/bin/env python3
"""
Generate a simple image for the Kill Team Spawner token.
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

def generate_spawner_image():
    """Generate a simple green button image for the spawner."""
    
    # Create 512x512 image
    size = (512, 512)
    
    # Create green gradient background
    img = Image.new('RGB', size, color='#33cc66')
    draw = ImageDraw.Draw(img)
    
    # Draw border
    border_width = 20
    draw.rectangle(
        [(border_width, border_width), (size[0]-border_width, size[1]-border_width)],
        outline='#ffffff',
        width=border_width
    )
    
    # Add text
    try:
        # Try to use a larger font if available
        font = ImageFont.truetype("arial.ttf", 80)
        font_small = ImageFont.truetype("arial.ttf", 40)
    except:
        # Fallback to default font
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Main text
    text1 = "SPAWN"
    text2 = "TEAM"
    
    # Calculate text positions (centered)
    bbox1 = draw.textbbox((0, 0), text1, font=font)
    bbox2 = draw.textbbox((0, 0), text2, font=font)
    
    text1_width = bbox1[2] - bbox1[0]
    text2_width = bbox2[2] - bbox2[0]
    text_height = bbox1[3] - bbox1[1]
    
    x1 = (size[0] - text1_width) // 2
    y1 = (size[1] - text_height * 2.5) // 2
    x2 = (size[0] - text2_width) // 2
    y2 = y1 + text_height + 20
    
    # Draw text with shadow
    shadow_offset = 4
    draw.text((x1 + shadow_offset, y1 + shadow_offset), text1, fill='#000000', font=font)
    draw.text((x1, y1), text1, fill='#ffffff', font=font)
    
    draw.text((x2 + shadow_offset, y2 + shadow_offset), text2, fill='#000000', font=font)
    draw.text((x2, y2), text2, fill='#ffffff', font=font)
    
    # Save
    output_path = Path(__file__).parent.parent / "config" / "defaults" / "tts-image" / "spawner-token.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, 'PNG')
    
    print(f"✓ Generated spawner image: {output_path}")
    print(f"  Size: {size[0]}x{size[1]}")

if __name__ == "__main__":
    generate_spawner_image()
