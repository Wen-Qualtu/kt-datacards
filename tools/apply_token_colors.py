#!/usr/bin/env python3
"""
Apply pre-extracted token colors to team-config.yaml.
Uses hardcoded values from extract_token_colors.py run.
"""

import yaml
from pathlib import Path

# Pre-extracted token colors from contrast-aware extraction
TOKEN_COLORS = {
    'battleclade': ([135, 97, 92], [255, 255, 255]),
    'blades-of-khaine': ([255, 255, 255], [110, 152, 148]),
    'blooded': ([70, 36, 41], [255, 255, 255]),
    'brood-brothers': ([120, 97, 128], [255, 255, 255]),
    'canoptek-circle': ([110, 144, 100], [255, 255, 255]),
    'celestian-insidiants': ([66, 65, 66], [255, 255, 255]),
    'corsair-voidscarred': ([17, 116, 123], [255, 255, 255]),
    'death-korps': ([74, 64, 54], [255, 255, 255]),
    'deathwatch': ([69, 69, 71], [255, 255, 255]),
    'exaction-squad': ([194, 167, 102], [21, 24, 23]),
    'farstalker-kinband': ([196, 176, 152], [255, 255, 255]),
    'fellgor-ravagers': ([129, 102, 101], [255, 255, 255]),
    'goremongers': ([193, 153, 147], [84, 55, 4]),
    'hand-of-the-archon': ([50, 42, 56], [255, 255, 255]),
    'hearthkyn-salvagers': ([224, 199, 171], [25, 23, 20]),
    'hernkyn-yaegirs': ([121, 145, 159], [255, 255, 255]),
    'hierotek-circle': ([57, 62, 64], [124, 188, 88]),
    'imperial-navy-breachers': ([134, 118, 98], [255, 255, 255]),
    'inquisitorial-agents': ([102, 66, 69], [255, 255, 255]),
    'kasrkin': ([80, 95, 62], [255, 255, 255]),
    'kommandos': ([92, 77, 66], [43, 78, 22]),
    'legionaries': ([255, 255, 255], [68, 89, 54]),
    'mandrakes': ([121, 155, 148], [255, 255, 255]),
    'novitiates': ([187, 172, 144], [255, 255, 255]),
    'pathfinders': ([255, 255, 255], [231, 191, 178]),
    'phobos-strike-team': ([93, 108, 142], [255, 255, 255]),
    'ratlings': ([146, 118, 110], [255, 255, 255]),
    'raveners': ([50, 42, 63], [255, 255, 255]),
    'sanctifiers': ([181, 153, 132], [255, 255, 255]),
    'scout-squad': ([83, 87, 88], [0, 1, 1]),
    'tempestus-aquilons': ([101, 131, 132], [255, 255, 255]),
    'vespid-stingwings': ([93, 130, 139], [1, 0, 1]),
    'wolf-scouts': ([110, 128, 145], [255, 255, 255]),
    'xv26-stealth-battlesuits': ([255, 255, 255], [163, 116, 119]),
}


class InlineDumper(yaml.SafeDumper):
    pass

def represent_list_inline(dumper, data):
    """Represent lists inline for RGB values."""
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

InlineDumper.add_representer(list, represent_list_inline)


def apply_token_colors():
    """Apply pre-extracted token colors to team-config.yaml."""
    
    config_path = Path("config/team-config.yaml")
    
    print("Applying token colors to team-config.yaml...\n")
    
    # Load existing config
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    teams_updated = 0
    
    for team_slug, (back_color, front_color) in TOKEN_COLORS.items():
        if team_slug in config['teams']:
            config['teams'][team_slug]['dice_back_color'] = back_color
            config['teams'][team_slug]['dice_front_color'] = front_color
            teams_updated += 1
            print(f"✓ {team_slug:30} - back: rgb({back_color[0]:3}, {back_color[1]:3}, {back_color[2]:3})  front: rgb({front_color[0]:3}, {front_color[1]:3}, {front_color[2]:3})")
        else:
            print(f"⚠ {team_slug} not found in config")
    
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
    teams_updated = apply_token_colors()
    
    if teams_updated > 0:
        print("Now regenerating dice with new colors...")
        print("Run: poetry run python pipelines/warcom/steps/4a_generate_dice.py")
