"""
Generate card box texture for teams by compositing:
- Base box template (dev/examples/box-side.png)
- Landscape icon (from extracted icons)
- Portrait icon (from extracted icons)

Output: 1024x1024 texture suitable for TTS card boxes
"""
import cv2
import numpy as np
from pathlib import Path
import argparse


def composite_box_texture(
    template_path: Path,
    landscape_icon_path: Path,
    portrait_icon_path: Path,
    output_path: Path,
    output_size: tuple = (1024, 1024)
) -> bool:
    """
    Create card box texture by compositing template with team icons.
    
    Args:
        template_path: Path to box-side.png template
        landscape_icon_path: Path to team landscape icon
        portrait_icon_path: Path to team portrait icon
        output_path: Path to save output texture
        output_size: Output dimensions (width, height)
    
    Returns:
        True if successful
    """
    try:
        # Load images
        template = cv2.imread(str(template_path))
        landscape = cv2.imread(str(landscape_icon_path))
        portrait = cv2.imread(str(portrait_icon_path))
        
        if template is None:
            print(f"ERROR: Could not load template: {template_path}")
            return False
        if landscape is None:
            print(f"ERROR: Could not load landscape icon: {landscape_icon_path}")
            return False
        if portrait is None:
            print(f"ERROR: Could not load portrait icon: {portrait_icon_path}")
            return False
        
        # Create white canvas at output size
        canvas = np.ones((output_size[1], output_size[0], 3), dtype=np.uint8) * 255
        
        # Layout coordinates (exact placement):
        # Box template:  (0, 0) to (296, 727)
        # Portrait icon: (508, 0) to (1024, 727)
        # Landscape icon: (0, 728) to (508, 1022)
        
        # 1. Place box template at (0, 0) to (296, 727)
        template_resized = cv2.resize(template, (296, 727), interpolation=cv2.INTER_LANCZOS4)
        canvas[0:727, 0:296] = template_resized
        
        # 2. Place portrait icon at (508, 0) to (1024, 727)
        portrait_resized = cv2.resize(portrait, (516, 727), interpolation=cv2.INTER_LANCZOS4)
        canvas[0:727, 508:1024] = portrait_resized
        
        # 3. Place landscape icon at (0, 728) to (508, 1022)
        landscape_resized = cv2.resize(landscape, (508, 294), interpolation=cv2.INTER_LANCZOS4)
        canvas[728:1022, 0:508] = landscape_resized
        
        # Save output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), canvas, [cv2.IMWRITE_JPEG_QUALITY, 95])
        
        print(f"✓ Created box texture: {output_path}")
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to create box texture: {e}")
        return False


def generate_for_team(team_name: str, extracted_dir: Path = None, config_dir: Path = None) -> bool:
    """
    Generate box texture for a specific team.
    
    Args:
        team_name: Team slug name
        extracted_dir: Root of extracted directory (default: layers/warcom/extracted)
        config_dir: Root of config directory (default: config)
    
    Returns:
        True if successful
    """
    if extracted_dir is None:
        extracted_dir = Path('layers/warcom/extracted')
    if config_dir is None:
        config_dir = Path('config')
    
    # Paths
    template_path = Path('dev/examples/box-side.png')
    landscape_icon = extracted_dir / team_name / 'icons' / f'{team_name}-icon-landscape.jpg'
    portrait_icon = extracted_dir / team_name / 'icons' / f'{team_name}-icon-portrait.jpg'
    output_path = config_dir / 'teams' / team_name / 'box' / 'card-box-texture.jpg'
    
    # Check if icons exist
    if not landscape_icon.exists():
        print(f"ERROR: Landscape icon not found: {landscape_icon}")
        return False
    if not portrait_icon.exists():
        print(f"ERROR: Portrait icon not found: {portrait_icon}")
        return False
    if not template_path.exists():
        print(f"ERROR: Template not found: {template_path}")
        return False
    
    return composite_box_texture(template_path, landscape_icon, portrait_icon, output_path)


def main():
    parser = argparse.ArgumentParser(
        description='Generate card box textures for Kill Team datacards'
    )
    parser.add_argument('team', nargs='?', help='Team name (or "all" for all teams)')
    parser.add_argument('--extracted-dir', type=Path, default=Path('layers/warcom/extracted'),
                       help='Extracted directory root')
    parser.add_argument('--config-dir', type=Path, default=Path('config'),
                       help='Config directory root')
    
    args = parser.parse_args()
    
    if args.team == 'all':
        # Process all teams with extracted icons
        teams_processed = 0
        teams_failed = 0
        
        for team_dir in sorted(args.extracted_dir.iterdir()):
            if team_dir.is_dir():
                icons_dir = team_dir / 'icons'
                if icons_dir.exists():
                    team_name = team_dir.name
                    print(f"\n[{team_name}]")
                    if generate_for_team(team_name, args.extracted_dir, args.config_dir):
                        teams_processed += 1
                    else:
                        teams_failed += 1
        
        print("\n" + "="*60)
        print(f"Processed: {teams_processed} teams")
        print(f"Failed: {teams_failed} teams")
        print("="*60)
        
    elif args.team:
        # Process single team
        if not generate_for_team(args.team, args.extracted_dir, args.config_dir):
            exit(1)
    else:
        # No team specified, show usage
        parser.print_help()


if __name__ == '__main__':
    main()
