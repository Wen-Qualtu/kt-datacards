#!/usr/bin/env python3
"""Convert and crop card backside images to match existing aspect ratios."""

from PIL import Image
from pathlib import Path

# Paths
config_dir = Path(__file__).parent.parent / "config" / "card-backside" / "default"
avif_path = config_dir / "6ca08603d0eda63caa881249627f1b22_c8fe1a18ce59bb6447939117c3aeac4d.avif"
webp_path = config_dir / "kill-team-beginners-guide-v0-cy1vfrmtgw3f1.webp"

# Output paths
portrait_output = config_dir / "default-backside-portrait.jpg"
landscape_output = config_dir / "default-backside-landscape.jpg"

# Target aspect ratios (from existing files)
PORTRAIT_RATIO = 407 / 645  # width / height ≈ 0.631
LANDSCAPE_RATIO = 645 / 407  # width / height ≈ 1.585

# Target sizes
PORTRAIT_SIZE = (407, 645)
LANDSCAPE_SIZE = (645, 407)

def center_crop_to_ratio(img, target_ratio):
    """Crop image from all sides equally to match target aspect ratio."""
    current_ratio = img.width / img.height
    
    if abs(current_ratio - target_ratio) < 0.001:
        return img
    
    if current_ratio > target_ratio:
        # Image is too wide, crop width
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        return img.crop((left, 0, left + new_width, img.height))
    else:
        # Image is too tall, crop height
        new_height = int(img.width / target_ratio)
        top = (img.height - new_height) // 2
        return img.crop((0, top, img.width, top + new_height))

print("Processing portrait backside (AVIF)...")
# Load AVIF
avif_img = Image.open(avif_path)
print(f"  Original size: {avif_img.size}, ratio: {avif_img.width/avif_img.height:.3f}")

# Convert to RGB if needed
if avif_img.mode in ('RGBA', 'LA', 'P'):
    background = Image.new('RGB', avif_img.size, (255, 255, 255))
    if avif_img.mode == 'P':
        avif_img = avif_img.convert('RGBA')
    if avif_img.mode in ('RGBA', 'LA'):
        background.paste(avif_img, mask=avif_img.split()[-1])
    avif_img = background

# Crop to portrait ratio
cropped = center_crop_to_ratio(avif_img, PORTRAIT_RATIO)
print(f"  Cropped size: {cropped.size}, ratio: {cropped.width/cropped.height:.3f}")

# Resize to target size
final = cropped.resize(PORTRAIT_SIZE, Image.Resampling.LANCZOS)
final.save(portrait_output, 'JPEG', quality=95)
print(f"  ✓ Saved to {portrait_output.name}")

print("\nProcessing landscape backside (WEBP)...")
# Load WEBP
webp_img = Image.open(webp_path)
print(f"  Original size: {webp_img.size}, ratio: {webp_img.width/webp_img.height:.3f}")

# Convert to RGB if needed
if webp_img.mode in ('RGBA', 'LA', 'P'):
    background = Image.new('RGB', webp_img.size, (255, 255, 255))
    if webp_img.mode == 'P':
        webp_img = webp_img.convert('RGBA')
    if webp_img.mode in ('RGBA', 'LA'):
        background.paste(webp_img, mask=webp_img.split()[-1])
    webp_img = background

# Crop to landscape ratio
cropped = center_crop_to_ratio(webp_img, LANDSCAPE_RATIO)
print(f"  Cropped size: {cropped.size}, ratio: {cropped.width/cropped.height:.3f}")

# Resize to target size
final = cropped.resize(LANDSCAPE_SIZE, Image.Resampling.LANCZOS)
final.save(landscape_output, 'JPEG', quality=95)
print(f"  ✓ Saved to {landscape_output.name}")

print("\n✓ Done!")
