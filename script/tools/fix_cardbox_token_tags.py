#!/usr/bin/env python3
"""
Fix KTUI tags for token bags and tokens inside main card box files.

Rules:
- operative, octagon, diamond tokens: ["KTUIStackable", "KTUIToken"]
- round tokens: ["KTUIToken", "KTUIMarker"]
- Bags/dispensers should NOT have KTUI tags
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


def get_tags_for_shape(shape: str) -> List[str]:
    """Get the correct KTUI tags for a given token shape.
    
    Args:
        shape: Token shape (operative, octagon, diamond, or round)
    
    Returns:
        List of KTUI tag strings
    """
    if shape in ['operative', 'octagon', 'diamond']:
        return ["KTUIStackable", "KTUIToken"]
    else:  # round or any other shape
        return ["KTUIToken", "KTUIMarker"]


def normalize_token_name(name: str) -> str:
    """Normalize token name for matching (lowercase, replace spaces/hyphens)."""
    return name.lower().replace(' ', '-').replace('_', '-')


def fix_token_bag_in_cardbox(cardbox_path: Path, token_shapes: Dict[str, str]) -> bool:
    """Fix KTUI tags for token bag inside a card box file.
    
    Args:
        cardbox_path: Path to the card box JSON file
        token_shapes: Dict mapping token names to shapes for this team
    
    Returns:
        True if file was modified, False otherwise
    """
    with open(cardbox_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    modified = False
    
    # Navigate to ObjectStates[0].ContainedObjects
    if not data.get('ObjectStates') or len(data['ObjectStates']) == 0:
        print(f"  Warning: No ObjectStates in {cardbox_path.name}")
        return False
    
    card_box = data['ObjectStates'][0]
    contained_objects = card_box.get('ContainedObjects', [])
    
    # Find the token bag (looks for "tokens" in the nickname)
    for obj in contained_objects:
        nickname = obj.get('Nickname', '').lower()
        
        # Check if this is the token bag
        if 'token' in nickname and obj.get('Name') == 'Custom_Model_Bag':
            print(f"  Found token bag: {obj.get('Nickname')}")
            
            # Process all infinite bags inside the token bag
            infinite_bags = obj.get('ContainedObjects', [])
            for infinite_bag in infinite_bags:
                if infinite_bag.get('Name') != 'Custom_Model_Infinite_Bag':
                    continue
                
                bag_nickname = infinite_bag.get('Nickname', '')
                if not bag_nickname:
                    continue
                
                # Normalize for matching
                normalized_name = normalize_token_name(bag_nickname)
                
                # Find matching shape in config
                shape = None
                for config_name, config_shape in token_shapes.items():
                    if normalize_token_name(config_name) == normalized_name:
                        shape = config_shape
                        break
                
                if shape is None:
                    print(f"    Warning: No shape configured for token '{bag_nickname}' - defaulting to round")
                    shape = 'round'
                
                # Get correct tags for this shape
                correct_tags = get_tags_for_shape(shape)
                
                # Remove KTUI tags from the infinite bag itself
                current_bag_tags = infinite_bag.get('Tags', [])
                cleaned_bag_tags = [tag for tag in current_bag_tags if not tag.startswith('KTUI')]
                if current_bag_tags != cleaned_bag_tags:
                    infinite_bag['Tags'] = cleaned_bag_tags
                    modified = True
                    print(f"    Removed KTUI tags from {bag_nickname} bag: {current_bag_tags} -> {cleaned_bag_tags}")
                
                # Update tags on contained tokens (ContainedObjects)
                contained_tokens = infinite_bag.get('ContainedObjects', [])
                for token in contained_tokens:
                    token_current_tags = token.get('Tags', [])
                    if token_current_tags != correct_tags:
                        token['Tags'] = correct_tags
                        modified = True
                        print(f"    Updated {bag_nickname} token (ContainedObjects): {token_current_tags} -> {correct_tags}")
                
                # Update tags on child tokens (ChildObjects)
                child_tokens = infinite_bag.get('ChildObjects', [])
                for token in child_tokens:
                    token_current_tags = token.get('Tags', [])
                    if token_current_tags != correct_tags:
                        token['Tags'] = correct_tags
                        modified = True
                        print(f"    Updated {bag_nickname} token (ChildObjects): {token_current_tags} -> {correct_tags}")
            
            break  # Found the token bag, no need to continue
    
    # Save if modified
    if modified:
        with open(cardbox_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    
    return False


def main():
    """Main function to fix token tags in card box files."""
    print("Loading team configuration...")
    team_config = load_team_config()
    token_shapes = get_token_shapes(team_config)
    
    print(f"\nFound token shapes for {len(token_shapes)} teams")
    
    # Find all card box files
    tts_objects_dir = Path("tts_objects")
    cardbox_files = list(tts_objects_dir.glob("*/*Cards.json"))
    # Filter to only team subfolders (exclude root level if any exist)
    cardbox_files = [f for f in cardbox_files if f.parent.name != 'tts_objects']
    
    print(f"\nProcessing {len(cardbox_files)} card box files...")
    
    modified_count = 0
    for cardbox_path in sorted(cardbox_files):
        team_slug = cardbox_path.parent.name
        
        print(f"\n{team_slug}:")
        
        # Get token shapes for this team
        team_tokens = token_shapes.get(team_slug, {})
        if not team_tokens:
            print(f"  ✓ No tokens configured for {team_slug}")
            continue
        
        # Fix tags
        was_modified = fix_token_bag_in_cardbox(cardbox_path, team_tokens)
        if was_modified:
            modified_count += 1
            print(f"  ✓ Modified {cardbox_path.name}")
        else:
            print(f"  ✓ No changes needed")
    
    print(f"\n{'='*60}")
    print(f"Complete! Modified {modified_count} card box files")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
