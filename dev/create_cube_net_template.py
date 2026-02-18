"""
Simple script to create a cube net template image for manual testing.
Shows the layout with labeled regions and grid lines.
"""
import cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Texture dimensions
FACE_SIZE = 512
WIDTH = FACE_SIZE * 4  # 2048
HEIGHT = FACE_SIZE * 3  # 1536

# Create white canvas
canvas = np.ones((HEIGHT, WIDTH, 3), dtype=np.uint8) * 255

# Define face regions with labels
faces = {
    'top': (FACE_SIZE, 0, FACE_SIZE * 2, FACE_SIZE),
    'left': (0, FACE_SIZE, FACE_SIZE, FACE_SIZE * 2),
    'front': (FACE_SIZE, FACE_SIZE, FACE_SIZE * 2, FACE_SIZE * 2),
    'right': (FACE_SIZE * 2, FACE_SIZE, FACE_SIZE * 3, FACE_SIZE * 2),
    'back': (FACE_SIZE * 3, FACE_SIZE, FACE_SIZE * 4, FACE_SIZE * 2),
    'bottom': (FACE_SIZE, FACE_SIZE * 2, FACE_SIZE * 2, FACE_SIZE * 3),
}

# Draw grid and labels
pil_img = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
draw = ImageDraw.Draw(pil_img)

try:
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 40)
    small_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
except:
    font = ImageFont.load_default()
    small_font = ImageFont.load_default()

# Draw face regions
for face_name, (x1, y1, x2, y2) in faces.items():
    # Draw border
    draw.rectangle([x1, y1, x2-1, y2-1], outline=(200, 200, 200), width=2)
    
    # Draw label in center
    bbox = draw.textbbox((0, 0), face_name.upper(), font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_x = x1 + (x2 - x1 - text_w) // 2
    text_y = y1 + (y2 - y1 - text_h) // 2
    
    # Draw text with shadow
    draw.text((text_x + 2, text_y + 2), face_name.upper(), fill=(0, 0, 0), font=font)
    draw.text((text_x, text_y), face_name.upper(), fill=(100, 100, 255), font=font)
    
    # Draw coordinates
    coord_text = f"{x1},{y1} to {x2},{y2}"
    draw.text((x1 + 10, y1 + 10), coord_text, fill=(150, 150, 150), font=small_font)

# Draw dimension labels
draw.text((10, HEIGHT - 40), f"Total: {WIDTH}x{HEIGHT} (2048x1536)", fill=(0, 0, 0), font=small_font)
draw.text((10, HEIGHT - 20), f"Each face: {FACE_SIZE}x{FACE_SIZE} (512x512)", fill=(0, 0, 0), font=small_font)

# Convert back to BGR
canvas = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

# Save template
output_path = Path(__file__).parent / 'box-cube-net-template.png'
cv2.imwrite(str(output_path), canvas)

print(f"✓ Created template: {output_path}")
print(f"  Size: {WIDTH}x{HEIGHT} pixels")
print(f"  Face size: {FACE_SIZE}x{FACE_SIZE} pixels each")
print("\nLayout:")
print("                 TOP")
print("    LEFT | FRONT | RIGHT | BACK")
print("               BOTTOM")
