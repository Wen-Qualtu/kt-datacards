#!/usr/bin/env python3
"""
Generate team-spawner-image.png with all team names listed in 4 columns.
This image shows all available teams for the spawner token.
"""

import yaml
import math
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path


def generate_team_list_image():
    """Generate an image with all team names in 4-column layout."""
    
    # Load team configuration
    config_path = Path("config/team-config.yaml")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Get all team names sorted alphabetically
    teams = config.get('teams', {})
    team_names = sorted([v['canonical_name'] for k, v in teams.items()])
    
    print(f"Generating team list image with {len(team_names)} teams in 4 columns")
    
    # Image settings
    width = 1400
    num_columns = 4
    line_height = 22
    padding_top = 60
    padding_side = 50
    padding_bottom = 80
    header_height = 100
    
    # Calculate teams per column
    teams_per_column = math.ceil(len(team_names) / num_columns)
    
    # Calculate height
    list_height = teams_per_column * line_height
    height = header_height + list_height + padding_top + padding_bottom
    
    # Create image with dark blue background
    img = Image.new('RGB', (width, height), color='#14141e')
    draw = ImageDraw.Draw(img)
    
    # Try to load fonts
    try:
        header_font = ImageFont.truetype("arial.ttf", 32)
        team_font = ImageFont.truetype("arial.ttf", 16)
        note_font = ImageFont.truetype("arial.ttf", 15)
    except:
        try:
            header_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 32)
            team_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 16)
            note_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 15)
        except:
            header_font = ImageFont.load_default()
            team_font = ImageFont.load_default()
            note_font = ImageFont.load_default()
    
    # Draw header
    header_text = f"🎯 KILL TEAM SPAWNER - ALL {len(team_names)} TEAMS 🎯"
    header_bbox = draw.textbbox((0, 0), header_text, font=header_font)
    header_width = header_bbox[2] - header_bbox[0]
    header_x = (width - header_width) // 2
    
    draw.text((header_x, 30), header_text, fill='#dcdcea', font=header_font)
    
    # Draw separator line
    line_y = header_height - 10
    draw.line([(padding_side, line_y), (width - padding_side, line_y)], fill='#3c3c4a', width=2)
    
    # Calculate column width
    column_width = (width - (padding_side * 2)) / num_columns
    
    # Draw team list in columns
    y_start = header_height + padding_top
    for i, team_name in enumerate(team_names, 1):
        col = (i - 1) // teams_per_column
        row = (i - 1) % teams_per_column
        
        x_position = padding_side + (col * column_width)
        y_position = y_start + (row * line_height)
        
        team_text = f"{i:2d}. {team_name}"
        draw.text((x_position, y_position), team_text, fill='#dcdcea', font=team_font)
    
    # Draw note at the bottom
    note_y = height - padding_bottom + 20
    note_lines = [
        "Click the 'Spawn Team' button above to select a team",
        f"Enter team number (1-{len(team_names)}) or partial name (e.g., 'kasrkin', 'death')"
    ]
    
    for i, note_line in enumerate(note_lines):
        note_bbox = draw.textbbox((0, 0), note_line, font=note_font)
        note_width = note_bbox[2] - note_bbox[0]
        note_x = (width - note_width) // 2
        draw.text((note_x, note_y + (i * 20)), note_line, fill='#64b4ff', font=note_font)
    
    # Save
    output_path = Path("output_v2/team-spawner-image.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, 'PNG')
    
    print(f"✓ Generated team list image: {output_path}")
    print(f"  Size: {width}x{height}")
    print(f"  Teams: {len(team_names)} in {num_columns} columns")
    print(f"  Teams per column: {teams_per_column}")


if __name__ == "__main__":
    generate_team_list_image()
