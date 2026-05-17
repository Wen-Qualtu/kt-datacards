"""
Step 4a: Generate Team Dice Textures

Generates Tabletop Simulator dice textures for each team.
Creates both light and dark variants with default colors.

Input:  layers/warcom/extracted/{team}/icons/{team}-icon-token-transparent.png
Output: output/{team}/dice/{team}-dice-light.jpg
        output/{team}/dice/{team}-dice-dark.jpg

Dice Format:
- 2048x2048 texture with 3x2 grid layout
- Top row: faces 2, 4, 5
- Bottom row: faces 1, 3, 6
- Each face: 630x630 with 90% scaled content (567x567) + 32px margins
"""
import argparse
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional
import yaml

import cv2
import numpy as np
from PIL import Image, ImageDraw


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


# Constants
DICE_SIZE = 2048
FACE_SIZE = 630
CONTENT_SIZE = 567  # 90% of face size
CONTENT_OFFSET = (FACE_SIZE - CONTENT_SIZE) // 2  # 32px margins

# Face coordinates (x, y) for 3x2 grid
FACE_COORDS = {
    1: (20, 1403),
    2: (20, 711),
    3: (711, 1403),
    4: (711, 711),
    5: (1399, 711),
    6: (1399, 1403)
}

# Default colors
LIGHT_BACKGROUND = (255, 140, 0)  # Orange
LIGHT_DOTS = (255, 140, 0)  # Orange
DARK_BACKGROUND = (40, 40, 50)  # Dark gray-blue
DARK_DOTS = (255, 255, 255)  # White


def load_team_config() -> Dict:
    """Load team configuration."""
    config_path = Path('config/team-config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config.get('teams', {})


def recolor_image(image_rgba: np.ndarray, target_color: Tuple[int, int, int]) -> np.ndarray:
    """
    Recolor an RGBA image while preserving alpha channel.
    
    Args:
        image_rgba: RGBA image array (H, W, 4)
        target_color: RGB tuple to apply
    
    Returns:
        Recolored RGBA image
    """
    result = image_rgba.copy()
    
    # Apply color to RGB channels where alpha > 0
    for c in range(3):
        result[:, :, c] = np.where(image_rgba[:, :, 3] > 0, target_color[c], 0)
    
    return result


def generate_dice(
    background_path: Path,
    dots_dir: Path,
    icon_path: Optional[Path],
    output_path: Path,
    background_color: Optional[Tuple[int, int, int]] = None,
    dot_color: Optional[Tuple[int, int, int]] = None
):
    """
    Generate a single dice texture.
    
    Args:
        background_path: Path to background texture
        dots_dir: Directory containing dots-1.png through dots-5.png
        icon_path: Optional path to transparent team icon (for face 6)
        output_path: Output path for dice texture
        background_color: Optional RGB color to tint background
        dot_color: Optional RGB color for dots/icon
    """
    # Load background
    background = Image.open(background_path).convert('RGB')
    
    # Recolor background if specified
    if background_color:
        bg_array = np.array(background)
        # Blend: 15% texture + 85% target color (more vibrant colors while keeping subtle texture)
        tinted = (bg_array.astype(np.float32) * 0.15 + np.array(background_color) * 0.85).astype(np.uint8)
        background = Image.fromarray(tinted)
    
    # Process each face
    for face_num in range(1, 6):
        # Load dot pattern
        dots_path = dots_dir / f'dots-{face_num}.png'
        dots = Image.open(dots_path).convert('RGBA')
        dots_array = np.array(dots)
        
        # Recolor dots if specified
        if dot_color:
            dots_array = recolor_image(dots_array, dot_color)
            dots = Image.fromarray(dots_array)
        
        # Scale to content size
        dots_scaled = dots.resize((CONTENT_SIZE, CONTENT_SIZE), Image.Resampling.LANCZOS)
        
        # Paste onto background at face position with offset
        face_x, face_y = FACE_COORDS[face_num]
        paste_x = face_x + CONTENT_OFFSET
        paste_y = face_y + CONTENT_OFFSET
        background.paste(dots_scaled, (paste_x, paste_y), dots_scaled)
    
    # Handle face 6 (team icon or dots-5)
    if icon_path and icon_path.exists():
        # Load transparent icon
        icon_bgra = cv2.imread(str(icon_path), cv2.IMREAD_UNCHANGED)
        if icon_bgra is not None and icon_bgra.shape[2] == 4:
            # Convert BGRA to RGBA
            icon_rgba = cv2.cvtColor(icon_bgra, cv2.COLOR_BGRA2RGBA)
            icon_array = np.array(icon_rgba)
            
            # Recolor icon if specified
            if dot_color:
                icon_array = recolor_image(icon_array, dot_color)
            
            icon = Image.fromarray(icon_array)
            
            # Scale to content size
            icon_scaled = icon.resize((CONTENT_SIZE, CONTENT_SIZE), Image.Resampling.LANCZOS)
            
            # Paste onto background at face 6 position
            face_x, face_y = FACE_COORDS[6]
            paste_x = face_x + CONTENT_OFFSET
            paste_y = face_y + CONTENT_OFFSET
            background.paste(icon_scaled, (paste_x, paste_y), icon_scaled)
        else:
            logger.warning(f"    Icon not found or invalid, using dots for face 6")
            # Fallback to dots-5
            dots_path = dots_dir / 'dots-5.png'
            dots = Image.open(dots_path).convert('RGBA')
            dots_array = np.array(dots)
            
            if dot_color:
                dots_array = recolor_image(dots_array, dot_color)
                dots = Image.fromarray(dots_array)
            
            dots_scaled = dots.resize((CONTENT_SIZE, CONTENT_SIZE), Image.Resampling.LANCZOS)
            face_x, face_y = FACE_COORDS[6]
            paste_x = face_x + CONTENT_OFFSET
            paste_y = face_y + CONTENT_OFFSET
            background.paste(dots_scaled, (paste_x, paste_y), dots_scaled)
    else:
        # Use dots-5 for face 6
        dots_path = dots_dir / 'dots-5.png'
        dots = Image.open(dots_path).convert('RGBA')
        dots_array = np.array(dots)
        
        if dot_color:
            dots_array = recolor_image(dots_array, dot_color)
            dots = Image.fromarray(dots_array)
        
        dots_scaled = dots.resize((CONTENT_SIZE, CONTENT_SIZE), Image.Resampling.LANCZOS)
        face_x, face_y = FACE_COORDS[6]
        paste_x = face_x + CONTENT_OFFSET
        paste_y = face_y + CONTENT_OFFSET
        background.paste(dots_scaled, (paste_x, paste_y), dots_scaled)
    
    # Save output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    background.save(output_path, 'JPEG', quality=95)


def process_team(team_slug: str, team_config: Dict, extracted_dir: Path, output_dir: Path) -> Dict[str, bool]:
    """
    Generate light and dark dice for a single team.
    Team dice are generated separately by script/generate_team_dice.py.

    Returns:
        Dict with 'light' and 'dark' success flags
    """
    results = {'light': False, 'dark': False}

    # Paths
    icon_path = extracted_dir / team_slug / 'icons' / f'{team_slug}-icon-token-transparent.png'
    dice_output_dir = output_dir / team_slug / 'dice'

    light_output = dice_output_dir / f'{team_slug}-dice-light.jpg'
    dark_output = dice_output_dir / f'{team_slug}-dice-dark.jpg'

    # Default asset paths
    light_bg = Path('config/defaults/dice/light/background.jpeg')
    light_dots = Path('config/defaults/dice/light')
    dark_bg = Path('config/defaults/dice/dark/background.jpeg')
    dark_dots = Path('config/defaults/dice/dark')

    # Generate light dice
    try:
        generate_dice(
            background_path=light_bg,
            dots_dir=light_dots,
            icon_path=icon_path if icon_path.exists() else None,
            output_path=light_output,
            background_color=None,  # Use default light background
            dot_color=None  # Use default orange dots
        )
        results['light'] = True
    except Exception as e:
        logger.warning(f"    Error generating light dice: {e}")
    
    # Generate dark dice
    try:
        generate_dice(
            background_path=dark_bg,
            dots_dir=dark_dots,
            icon_path=icon_path if icon_path.exists() else None,
            output_path=dark_output,
            background_color=None,  # Use default dark background
            dot_color=None  # Use default white dots
        )
        results['dark'] = True
    except Exception as e:
        logger.warning(f"    Error generating dark dice: {e}")
    
    # Team dice are now generated by script/generate_team_dice.py using token colors.

    return results


def run(extracted_dir: Path, output_dir: Path) -> Dict:
    """
    Generate dice for all teams.
    
    Returns:
        Dict with processing statistics
    """
    logger.info("Generating team dice textures...\n")
    
    team_config = load_team_config()
    teams = sorted(team_config.keys())
    
    total_teams = len(teams)
    light_count = 0
    dark_count = 0

    for i, team_slug in enumerate(teams, 1):
        team_name = team_config[team_slug].get('canonical_name', team_slug)

        results = process_team(team_slug, team_config[team_slug], extracted_dir, output_dir)

        status_parts = []
        if results['light']:
            status_parts.append('light ✓')
            light_count += 1
        else:
            status_parts.append('light ✗')

        if results['dark']:
            status_parts.append('dark ✓')
            dark_count += 1
        else:
            status_parts.append('dark ✗')

        logger.info(f"[{i}/{total_teams}] {team_name:30s} - {', '.join(status_parts)}")

    logger.info(f"\n{'='*80}")
    logger.info(f"Results:")
    logger.info(f"  Light dice: {light_count}/{total_teams}")
    logger.info(f"  Dark dice:  {dark_count}/{total_teams}")
    logger.info(f"{'='*80}\n")

    return {
        'success': True,
        'total': total_teams,
        'light': light_count,
        'dark': dark_count,
    }


def main():
    parser = argparse.ArgumentParser(description='Generate team dice textures')
    parser.add_argument('--input-dir', type=Path, default=Path('layers/warcom/extracted'),
                       help='Input directory with extracted icons')
    parser.add_argument('--output-dir', type=Path, default=Path('output'),
                       help='Output directory for dice textures')
    
    args = parser.parse_args()
    
    result = run(
        extracted_dir=args.input_dir,
        output_dir=args.output_dir
    )
    
    exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
