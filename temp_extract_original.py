#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

# Extract the original image from git
result = subprocess.run(
    ['git', 'show', 'fb66b034:output_v2/team-spawner-image.png'],
    capture_output=True
)

if result.returncode == 0:
    output_path = Path('temp_original_spawner.png')
    output_path.write_bytes(result.stdout)
    print(f"Extracted original to: {output_path}")
    
    # Analyze it
    from PIL import Image
    img = Image.open(output_path)
    print(f"Size: {img.size}")
    print(f"Mode: {img.mode}")
    
    # Sample some colors
    px = img.load()
    print("\nSample colors from different areas:")
    print(f"  Background (10,10): {px[10,10]}")
    print(f"  Header area (500,50): {px[500,50]}")
    print(f"  Text area (100,150): {px[100,150]}")
    print(f"  Bottom area (500,img.height-50): {px[500, img.height-50]}")
else:
    print(f"Error: {result.stderr.decode()}")
