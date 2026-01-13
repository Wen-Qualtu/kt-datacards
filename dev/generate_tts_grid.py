"""
Generate a grid background for TTS table with all Kill Team boxes
Creates a labeled grid where each cell will contain a team's card box
"""
import yaml
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# Configuration
TEAMS_CONFIG = Path('config/team-config.yaml')
OUTPUT_IMAGE = Path('tts_objects/display-table/tts_grid_background.png')

# Grid settings
COLS = 7
ROWS = 7
CELL_WIDTH = 800  # pixels per cell
CELL_HEIGHT = 800

# Colors
BG_COLOR = (20, 20, 25)  # Dark background
GRID_COLOR = (60, 60, 70)  # Subtle grid lines
TEXT_COLOR = (255, 255, 255)  # Bright white text
HIGHLIGHT_COLOR = (80, 80, 100)  # Slightly lighter cell background
NUMBER_COLOR = (255, 200, 0)  # Bright yellow/gold for numbers

# Text settings
FONT_SIZE = 48
PADDING = 20

def load_teams():
    """Load and sort team names alphabetically"""
    with open(TEAMS_CONFIG) as f:
        config = yaml.safe_load(f)
    
    teams = sorted(config['teams'].keys())
    print(f"Loaded {len(teams)} teams")
    return teams

def create_grid_background(teams):
    """Create the grid background image"""
    
    # Calculate image size
    width = COLS * CELL_WIDTH
    height = ROWS * CELL_HEIGHT
    
    print(f"Creating {width}x{height} image ({COLS}x{ROWS} grid)")
    
    # Create image
    img = Image.new('RGB', (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    # Try to load a font, fall back to default if not available
    try:
        font = ImageFont.truetype("arial.ttf", FONT_SIZE)
        font_small = ImageFont.truetype("arial.ttf", FONT_SIZE - 6)
    except:
        print("Using default font (arial.ttf not found)")
        font = ImageFont.load_default()
        font_small = font
    
    # Draw grid and labels
    team_idx = 0
    for row in range(ROWS):
        for col in range(COLS):
            # Calculate cell position
            x = col * CELL_WIDTH
            y = row * CELL_HEIGHT
            
            # Draw cell background (alternating for visual interest)
            if (row + col) % 2 == 0:
                draw.rectangle([x, y, x + CELL_WIDTH, y + CELL_HEIGHT], 
                             fill=HIGHLIGHT_COLOR, outline=None)
            
            # Draw grid lines
            draw.rectangle([x, y, x + CELL_WIDTH, y + CELL_HEIGHT], 
                         outline=GRID_COLOR, width=3)
            
            # Add team name if we have more teams
            if team_idx < len(teams):
                team_name = teams[team_idx]
                
                # Format team name for display (replace hyphens with spaces, title case)
                display_name = team_name.replace('-', ' ').title()
                
                # Draw team name at top of cell
                text_bbox = draw.textbbox((0, 0), display_name, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                
                text_x = x + (CELL_WIDTH - text_width) // 2
                text_y = y + PADDING
                
                # Draw text with shadow for better readability
                draw.text((text_x + 3, text_y + 3), display_name, fill=(0, 0, 0), font=font)
                draw.text((text_x, text_y), display_name, fill=TEXT_COLOR, font=font)
                
                # Draw team index/number at bottom
                index_text = f"#{team_idx + 1}"
                idx_bbox = draw.textbbox((0, 0), index_text, font=font_small)
                idx_width = idx_bbox[2] - idx_bbox[0]
                
                idx_x = x + (CELL_WIDTH - idx_width) // 2
                idx_y = y + CELL_HEIGHT - PADDING - (idx_bbox[3] - idx_bbox[1]) - 10
                
                # Draw number with shadow for standout effect
                draw.text((idx_x + 2, idx_y + 2), index_text, fill=(0, 0, 0), font=font_small)
                draw.text((idx_x, idx_y), index_text, fill=NUMBER_COLOR, font=font_small)
                
                team_idx += 1
    
    # Ensure output directory exists
    OUTPUT_IMAGE.parent.mkdir(parents=True, exist_ok=True)
    
    # Save the image
    img.save(OUTPUT_IMAGE)
    print(f"\n✓ Grid background saved to: {OUTPUT_IMAGE}")
    print(f"  - Grid: {COLS} × {ROWS} = {COLS * ROWS} cells")
    print(f"  - Teams: {len(teams)}")
    print(f"  - Empty cells: {COLS * ROWS - len(teams)}")
    print(f"  - Image size: {width} × {height} pixels")
    print(f"  - Cell size: {CELL_WIDTH} × {CELL_HEIGHT} pixels")

if __name__ == '__main__':
    teams = load_teams()
    create_grid_background(teams)
