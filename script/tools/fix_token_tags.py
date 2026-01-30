#!/usr/bin/env python3
"""
Fix KTUI tags for tokens in TTS token bag files.

Rules:
- Tokens with names ending in "marker": ["KTUIToken", "KTUIMarker"]
- All other tokens: ["KTUIStackable", "KTUIToken"]
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List


def load_team_config() -> Dict:
    """Load team configuration to get token shapes."""
    config_path = Path("config/team-config.yaml")
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_token_shapes(team_config: Dict) -> Dict[str, Dict[str, str]]:
    """Extract token shapes for all teams from config.
    
    Returns:
        Dict mapping team slug to dict of token_name: shape
    """
    token_shapes = {}
    
    teams = team_config.get('teams', {})
    for team_slug, team_info in teams.items():
        tokens = team_info.get('tokens', [])
        
        if not tokens:
            continue
            
        team_tokens = {}
        for token in tokens:
            token_name = token.get('name', '')
            shape = token.get('shape', 'round')  # default to round if not specified
            if token_name:
                team_tokens[token_name] = shape
        
        token_shapes[team_slug] = team_tokens
    
    return token_shapes


def get_tags_for_token_name(token_name: str) -> List[str]:
    """Get the correct KTUI tags based on the token name.
    
    Args:
        token_name: The full token name (e.g., "Medic", "Vantage Point Marker")
    
    Returns:
        List of KTUI tag strings
    """
    # Check if the name ends with "marker" (case-insensitive)
    if token_name.lower().endswith('marker'):
        return ["KTUIToken", "KTUIMarker"]
    else:
        return ["KTUIStackable", "KTUIToken"]


def normalize_token_name(name: str) -> str:
    """Normalize token name for matching (lowercase, replace spaces/hyphens)."""
    return name.lower().replace(' ', '-').replace('_', '-')


def fix_token_tags(tokenbag_path: Path, token_shapes: Dict[str, str]) -> bool:
    """Fix KTUI tags in a token bag file.
    
    Args:
        tokenbag_path: Path to the token bag JSON file
        token_shapes: Dict mapping token names to shapes for this team
    
    Returns:
        True if file was modified, False otherwise
    """
    with open(tokenbag_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    modified = False
    
    # The token bag structure has ObjectStates[0].ContainedObjects
    # Each ContainedObject is an infinite bag for a specific token
    if not data.get('ObjectStates') or len(data['ObjectStates']) == 0:
        print(f"  Warning: No ObjectStates in {tokenbag_path.name}")
        return False
    
    token_bag = data['ObjectStates'][0]
    contained_objects = token_bag.get('ContainedObjects', [])
    
    for infinite_bag in contained_objects:
        # Get the token nickname (e.g., "Medic", "Vantage Point Marker")
        nickname = infinite_bag.get('Nickname', '')
        if not nickname:
            continue
        
        # Get correct tags based on the token name
        correct_tags = get_tags_for_token_name(nickname)
        
        # Remove KTUI tags from the infinite bag itself (bags should not have these tags)
        current_bag_tags = infinite_bag.get('Tags', [])
        # Remove any KTUI tags from the bag
        cleaned_bag_tags = [tag for tag in current_bag_tags if not tag.startswith('KTUI')]
        if current_bag_tags != cleaned_bag_tags:
            infinite_bag['Tags'] = cleaned_bag_tags
            modified = True
            print(f"  Removed KTUI tags from {nickname} bag: {current_bag_tags} -> {cleaned_bag_tags}")
        
        # Update tags on the contained token template (ContainedObjects)
        contained_tokens = infinite_bag.get('ContainedObjects', [])
        for token in contained_tokens:
            token_current_tags = token.get('Tags', [])
            if token_current_tags != correct_tags:
                token['Tags'] = correct_tags
                modified = True
                print(f"  Updated {nickname} token (ContainedObjects): {token_current_tags} -> {correct_tags}")
        
        # Update tags on child token templates (ChildObjects) - some bags have these too
        child_tokens = infinite_bag.get('ChildObjects', [])
        for token in child_tokens:
            token_current_tags = token.get('Tags', [])
            if token_current_tags != correct_tags:
                token['Tags'] = correct_tags
                modified = True
                print(f"  Updated {nickname} token (ChildObjects): {token_current_tags} -> {correct_tags}")
    
    # Save if modified
    if modified:
        with open(tokenbag_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    
    return False


def main():
    """Main function to fix token tags across all teams."""
    print("Loading team configuration...")
    team_config = load_team_config()
    token_shapes = get_token_shapes(team_config)
    
    print(f"\nFound token shapes for {len(token_shapes)} teams")
    
    # Find all token bag files
    tts_objects_dir = Path("tts_objects")
    tokenbag_files = list(tts_objects_dir.glob("*/tokens/*-tokenbag.json"))
    
    print(f"\nProcessing {len(tokenbag_files)} token bag files...")
    
    modified_count = 0
    for tokenbag_path in sorted(tokenbag_files):
        team_slug = tokenbag_path.parent.parent.name
        
        print(f"\n{team_slug}:")
        
        # Get token shapes for this team
        team_tokens = token_shapes.get(team_slug, {})
        if not team_tokens:
            print(f"  Warning: No token configuration found for {team_slug}")
            continue
        
        # Fix tags
        was_modified = fix_token_tags(tokenbag_path, team_tokens)
        if was_modified:
            modified_count += 1
            print(f"  ✓ Modified {tokenbag_path.name}")
        else:
            print(f"  ✓ No changes needed")
    
    print(f"\n{'='*60}")
    print(f"Complete! Modified {modified_count} token bag files")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
