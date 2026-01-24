#!/usr/bin/env python3
"""Generate spawner token image for config/defaults/tts-image/"""

import json
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Load team data
output_dir = Path("output_v2")
with open(output_dir / "tts-card-boxes.json", "r", encoding="utf-8") as f:
    teams = json.load(f)

# Sort teams alphabetically (same as script does)
teams.sort(key=lambda x: x["name"].lower())

# Dynamic layout calculation
num_teams = len(teams)
num_cols = 4
teams_per_col = (num_teams + num_cols - 1) // num_cols  # Round up

# Image settings
img_width = 1400
title_height = 100
row_height = 32
bottom_padding = 80
img_height = title_height + (teams_per_col * row_height) + bottom_padding

bg_color = (20, 20, 30)  # Dark blue-gray
text_color = (230, 230, 240)  # Light gray-white
title_color = (100, 180, 255)  # Cyan blue

# Create image
img = Image.new('RGB', (img_width, img_height), bg_color)
draw = ImageDraw.Draw(img)

# Try to load fonts, fallback to default
try:
    title_font = ImageFont.truetype("arial.ttf", 48)
    text_font = ImageFont.truetype("arial.ttf", 24)
except:
    title_font = ImageFont.load_default()
    text_font = ImageFont.load_default()

# Draw title
title = f"KILL TEAM SPAWNER ({len(teams)} teams)"
title_bbox = draw.textbbox((0, 0), title, font=title_font)
title_width = title_bbox[2] - title_bbox[0]
draw.text(((img_width - title_width) // 2, 30), title, fill=title_color, font=title_font)

# Draw teams in 4 columns (dynamically calculated)
col_width = img_width // num_cols
start_y = title_height + 20

for col in range(num_cols):
    x_pos = col * col_width + 40
    
    for row in range(teams_per_col):
        team_idx = col * teams_per_col + row
        if team_idx < len(teams):
            team = teams[team_idx]
            text = f"{team_idx + 1:2d}. {team['name'][:18]}"  # Truncate long names
            draw.text((x_pos, start_y + row * row_height), text, fill=text_color, font=text_font)

# Draw instructions at bottom
instructions = "Enter team number or partial name (e.g. '12' or 'brood')"
inst_bbox = draw.textbbox((0, 0), instructions, font=text_font)
inst_width = inst_bbox[2] - inst_bbox[0]
draw.text(((img_width - inst_width) // 2, img_height - 60), instructions, fill=title_color, font=text_font)

# Save image to config/defaults/tts-image/
output_path = Path("config/defaults/tts-image/spawner-token.png")
output_path.parent.mkdir(parents=True, exist_ok=True)
img.save(output_path)
print(f"✓ Created spawner token: {output_path}")
print(f"  Size: {img_width}x{img_height}")
print(f"  Teams: {len(teams)}")
