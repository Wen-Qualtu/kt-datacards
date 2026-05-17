#!/usr/bin/env python3
"""
Update team-config.yaml with colors extracted from tokens, then regenerate dice.
"""

import sys
from pathlib import Path
import yaml
import numpy as np
from PIL import Image

# Import the extraction function from the same directory
sys.path.insert(0, str(Path(__file__).parent))
from extract_token_colors import extract_color_families_from_tokens

# Safe YAML dumper that preserves inline list formatting
class InlineDumper(yaml.SafeDumper):
    pass

def represent_list_inline(dumper, data):
    """Represent lists inline for RGB values."""
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

InlineDumper.add_representer(list, represent_list_inline)


def update_team_config_with_token_colors():
    """Extract token colors and update team-config.yaml."""
    
    config_path = Path("config/team-config.yaml")
    output_dir = Path("output")
    
    print("Extracting token colors from teams with tokens...\n")
    
    # Load existing config
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    teams_updated = 0
    
    for team_slug, team_data in config['teams'].items():
        # Check if team has tokens
        token_dir = output_dir / team_slug / "tokens"
        if not token_dir.exists():
            continue
        
        # Get token files (exclude icon files)
        token_files = [f for f in token_dir.glob("*.png") if not f.stem.endswith('-icon')]
        if not token_files:
            continue
        
        # Extract colors from tokens
        colors = extract_color_families_from_tokens(token_files)
        
        if colors:
            back_color = colors['back_color']
            front_color = colors['front_color']
            
            # Convert numpy types to Python ints for YAML serialization
            back_color = [int(c) for c in back_color]
            front_color = [int(c) for c in front_color]
            
            # Update config
            team_data['dice_back_color'] = back_color
            team_data['dice_front_color'] = front_color
            teams_updated += 1
            
            print(f"✓ {team_slug:30} - back: rgb({back_color[0]:3}, {back_color[1]:3}, {back_color[2]:3})  front: rgb({front_color[0]:3}, {front_color[1]:3}, {front_color[2]:3})")
    
    # Write updated config
    print(f"\n{'='*80}")
    print(f"Updated {teams_updated} teams with token colors")
    print(f"Writing to {config_path}...")
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, Dumper=InlineDumper, default_flow_style=False, 
                  allow_unicode=True, sort_keys=False, width=120)
    
    print(f"✓ Config updated successfully\n")
    
    return teams_updated


if __name__ == "__main__":
    teams_updated = update_team_config_with_token_colors()
    
    if teams_updated > 0:
        print("Now regenerating dice with new colors...")
        print("Run: poetry run python pipelines/warcom/steps/4a_generate_dice.py")
