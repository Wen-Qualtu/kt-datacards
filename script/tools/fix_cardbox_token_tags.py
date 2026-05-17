#!/usr/bin/env python3
"""
Fix KTUI tags for token bags and tokens inside main card box files.

Rules:
- Tokens with type="marker": ["KTUIToken", "KTUIMarker"]
- Tokens with type="token": ["KTUIStackable", "KTUIToken"]
- Bags/dispensers should NOT have KTUI tags
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List


def load_team_config() -> Dict:
    """Load team configuration to get token types."""
    config_path = Path("config/team-config.yaml")
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_token_types(team_config: Dict) -> Dict[str, Dict[str, str]]:
    """Extract token types for all teams from config.
    
    Returns:
        Dict mapping team slug to dict of token_name: type
    """
    token_types = {}
    
    teams = team_config.get('teams', {})
    for team_slug, team_info in teams.items():
        tokens = team_info.get('tokens', [])
        
        if not tokens:
            continue
            
        team_tokens = {}
        for token in tokens:
            token_name = token.get('name', '')
            token_type = token.get('type', 'token')  # default to token if not specified
            if token_name:
                team_tokens[token_name] = token_type
        
        token_types[team_slug] = team_tokens
    
    return token_types


def get_tags_for_token_type(token_type: str) -> List[str]:
    """Get the correct KTUI tags based on token type from config.
    
    Args:
        token_type: The token type from config ('marker' or 'token')
    
    Returns:
        List of KTUI tag strings
    """
    # Marker tokens get marker tags, all others get stackable token tags
    if token_type == 'marker':
        return ["KTUIToken", "KTUIMarker"]
    else:
        return ["KTUIStackable", "KTUIToken"]


def normalize_token_name(name: str) -> str:
    """Normalize token name for matching (lowercase, replace spaces/hyphens)."""
    return name.lower().replace(' ', '-').replace('_', '-')


def fix_token_bag_in_cardbox(cardbox_path: Path) -> bool:
    """Fix KTUI tags for token bag inside a card box file - sets all to default stackable tags.
    
    Args:
        cardbox_path: Path to the card box JSON file
    
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
                
                # Set all tokens to default stackable tags
                correct_tags = ['KTUIStackable', 'KTUIToken']
                
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
    """Main function to fix token tags in card box files - sets all to default stackable tags."""
    # Find all card box files
    tts_objects_dir = Path("tts_objects")
    cardbox_files = list(tts_objects_dir.glob("*/*Cards.json"))
    # Filter to only team subfolders (exclude root level if any exist)
    cardbox_files = [f for f in cardbox_files if f.parent.name != 'tts_objects']
    
    print(f"Processing {len(cardbox_files)} card box files...")
    print("Setting all tokens to default stackable tags: ['KTUIStackable', 'KTUIToken']\n")
    
    modified_count = 0
    for cardbox_path in sorted(cardbox_files):
        team_slug = cardbox_path.parent.name
        
        print(f"{team_slug}:")
        
        # Fix tags
        was_modified = fix_token_bag_in_cardbox(cardbox_path)
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
