"""Apply KTUI tags to all tokens based on team-config.yaml types.

This script reads the type field from team-config.yaml and applies:
- type: token → ['KTUIStackable', 'KTUIToken']
- type: marker → ['KTUIToken', 'KTUIMarker']
- type: custom → ['KTUIToken'] + any additional tags from config
"""

import json
import yaml
from pathlib import Path
from typing import Dict


def load_team_config() -> dict:
    """Load the team configuration YAML file."""
    config_path = Path("config/team-config.yaml")
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_token_info_by_team(config: dict) -> Dict[str, Dict[str, dict]]:
    """Extract token information (type and tags) by team from config.
    
    Returns:
        Dict mapping team_slug -> {token_name_lower: {'type': str, 'tags': list}}
    """
    token_info_by_team = {}
    
    teams_dict = config.get('teams', {})
    for team_slug, team_data in teams_dict.items():
        tokens = team_data.get('tokens', [])
        if not tokens:
            continue
        
        token_info = {}
        for token in tokens:
            token_name = token.get('name', '').strip().lower()
            token_type = token.get('type', 'token')
            custom_tags = token.get('tags', [])
            
            if token_name:
                token_info[token_name] = {
                    'type': token_type,
                    'custom_tags': custom_tags if isinstance(custom_tags, list) else []
                }
        
        if token_info:
            token_info_by_team[team_slug] = token_info
    
    return token_info_by_team


def get_tags_for_token(token_type: str, custom_tags: list = None) -> list:
    """Get the correct KTUI tags based on token type.
    
    Args:
        token_type: 'token', 'marker', or 'custom'
        custom_tags: Additional tags for custom tokens
    
    Returns:
        List of KTUI tag strings
    """
    if token_type == 'marker':
        return ['KTUIToken', 'KTUIMarker', 'KTUITokenSimple']
    elif token_type == 'custom':
        base_tags = ['KTUIToken', 'KTUITokenSimple']
        if custom_tags:
            base_tags.extend(custom_tags)
        return base_tags
    else:  # token or default
        return ['KTUIStackable', 'KTUIToken', 'KTUITokenSimple']


def _strip_ktui_tags(tags: list) -> list:
    return [tag for tag in (tags or []) if not tag.startswith('KTUI')]


def fix_token_bag(token_bag_path: Path, token_info: Dict[str, dict]) -> bool:
    """Fix KTUI tags in a standalone token bag file."""
    with open(token_bag_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    modified = False
    
    if not data.get('ObjectStates') or len(data['ObjectStates']) == 0:
        return False
    
    token_bag = data['ObjectStates'][0]
    token_bag_tags = token_bag.get('Tags', [])
    cleaned_token_bag_tags = _strip_ktui_tags(token_bag_tags)
    if token_bag_tags != cleaned_token_bag_tags:
        token_bag['Tags'] = cleaned_token_bag_tags
        modified = True
    infinite_bags = token_bag.get('ContainedObjects', [])
    
    for infinite_bag in infinite_bags:
        if infinite_bag.get('Name') != 'Custom_Model_Infinite_Bag':
            continue
        
        bag_nickname = infinite_bag.get('Nickname', '')
        if not bag_nickname:
            continue
        
        # Normalize token name for lookup
        token_name_normalized = bag_nickname.strip().lower()
        token_data = token_info.get(token_name_normalized)

        if not token_data:
            print(f"    ⚠ Token '{bag_nickname}' not found in config")
            correct_tags = ['KTUITokenSimple']
        else:
            # Get correct tags based on type
            correct_tags = get_tags_for_token(token_data['type'], token_data.get('custom_tags'))
        
        # Remove KTUI tags from the bag itself
        current_bag_tags = infinite_bag.get('Tags', [])
        cleaned_bag_tags = _strip_ktui_tags(current_bag_tags)
        if current_bag_tags != cleaned_bag_tags:
            infinite_bag['Tags'] = cleaned_bag_tags
            modified = True
        
        # Update tags on contained tokens
        for token in infinite_bag.get('ContainedObjects', []):
            token_current_tags = token.get('Tags', [])
            if token_current_tags != correct_tags:
                token['Tags'] = correct_tags
                modified = True
                print(f"    {bag_nickname}: {token_current_tags} → {correct_tags}")
        
        # Update tags on child tokens
        for token in infinite_bag.get('ChildObjects', []):
            token_current_tags = token.get('Tags', [])
            if token_current_tags != correct_tags:
                token['Tags'] = correct_tags
                modified = True
    
    if modified:
        with open(token_bag_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    return modified


def fix_single_token_json(token_json_path: Path, token_info: Dict[str, dict]) -> bool:
    """Fix KTUI tags in a standalone single-token infinite bag JSON file."""
    with open(token_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not data.get('ObjectStates') or len(data['ObjectStates']) == 0:
        return False

    modified = False
    bag = data['ObjectStates'][0]

    bag_nickname = bag.get('Nickname', '')
    token_name_normalized = bag_nickname.strip().lower() if bag_nickname else ''
    token_data = token_info.get(token_name_normalized)

    if not token_data:
        print(f"    ⚠ Token '{bag_nickname}' not found in config")
        correct_tags = ['KTUITokenSimple']
    else:
        correct_tags = get_tags_for_token(token_data['type'], token_data.get('custom_tags'))

    # Remove KTUI tags from the dispenser bag itself
    current_bag_tags = bag.get('Tags', [])
    cleaned_bag_tags = _strip_ktui_tags(current_bag_tags)
    if current_bag_tags != cleaned_bag_tags:
        bag['Tags'] = cleaned_bag_tags
        modified = True

    # Update tags on contained tokens
    for token in bag.get('ContainedObjects', []):
        token_current_tags = token.get('Tags', [])
        if token_current_tags != correct_tags:
            token['Tags'] = correct_tags
            modified = True
            print(f"    {bag_nickname}: {token_current_tags} → {correct_tags}")

    # Update tags on child tokens
    for token in bag.get('ChildObjects', []):
        token_current_tags = token.get('Tags', [])
        if token_current_tags != correct_tags:
            token['Tags'] = correct_tags
            modified = True

    if modified:
        with open(token_json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    return modified


def fix_cardbox(cardbox_path: Path, token_info: Dict[str, dict]) -> bool:
    """Fix KTUI tags for token bags inside card box files."""
    with open(cardbox_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    modified = False
    
    if not data.get('ObjectStates') or len(data['ObjectStates']) == 0:
        return False
    
    card_box = data['ObjectStates'][0]
    contained_objects = card_box.get('ContainedObjects', [])
    
    # Find the token bag
    for obj in contained_objects:
        nickname = obj.get('Nickname', '').lower()
        
        if 'token' in nickname and obj.get('Name') == 'Custom_Model_Bag':
            # Remove KTUI tags from the team token bag (dispenser container)
            current_bag_tags = obj.get('Tags', [])
            cleaned_bag_tags = _strip_ktui_tags(current_bag_tags)
            if current_bag_tags != cleaned_bag_tags:
                obj['Tags'] = cleaned_bag_tags
                modified = True
            # Process all infinite bags inside the token bag
            infinite_bags = obj.get('ContainedObjects', [])
            for infinite_bag in infinite_bags:
                if infinite_bag.get('Name') != 'Custom_Model_Infinite_Bag':
                    continue
                
                bag_nickname = infinite_bag.get('Nickname', '')
                if not bag_nickname:
                    continue
                
                # Normalize token name for lookup
                token_name_normalized = bag_nickname.strip().lower()
                token_data = token_info.get(token_name_normalized)

                if not token_data:
                    print(f"    ⚠ Token '{bag_nickname}' not found in config")
                    correct_tags = ['KTUITokenSimple']
                else:
                    # Get correct tags based on type
                    correct_tags = get_tags_for_token(token_data['type'], token_data.get('custom_tags'))
                
                # Remove KTUI tags from the bag itself
                current_bag_tags = infinite_bag.get('Tags', [])
                cleaned_bag_tags = _strip_ktui_tags(current_bag_tags)
                if current_bag_tags != cleaned_bag_tags:
                    infinite_bag['Tags'] = cleaned_bag_tags
                    modified = True
                
                # Update tags on contained tokens
                for token in infinite_bag.get('ContainedObjects', []):
                    token_current_tags = token.get('Tags', [])
                    if token_current_tags != correct_tags:
                        token['Tags'] = correct_tags
                        modified = True
                        print(f"    {bag_nickname}: {token_current_tags} → {correct_tags}")
                
                # Update tags on child tokens
                for token in infinite_bag.get('ChildObjects', []):
                    token_current_tags = token.get('Tags', [])
                    if token_current_tags != correct_tags:
                        token['Tags'] = correct_tags
                        modified = True
            
            break
    
    if modified:
        with open(cardbox_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    return modified


def main():
    """Main function to apply KTUI tags based on config."""
    print("Loading team configuration...")
    config = load_team_config()
    token_info_by_team = get_token_info_by_team(config)
    
    print(f"Found token info for {len(token_info_by_team)} teams\n")
    print("="*60)
    
    tts_objects_dir = Path("tts_objects")
    
    # Process standalone token JSONs
    print("\nProcessing standalone token bags...")
    token_json_files = list(tts_objects_dir.glob("*/tokens/*.json"))
    token_json_files = [f for f in token_json_files if f.parent.parent.name != 'tts_objects']

    modified_count = 0
    for token_json_path in sorted(token_json_files):
        team_slug = token_json_path.parent.parent.name
        print(f"\n{team_slug}:")

        team_tokens = token_info_by_team.get(team_slug, {})
        if not team_tokens:
            print(f"  ✓ No tokens configured")
            continue

        if token_json_path.name.endswith('-tokenbag.json'):
            was_modified = fix_token_bag(token_json_path, team_tokens)
        else:
            was_modified = fix_single_token_json(token_json_path, team_tokens)

        if was_modified:
            modified_count += 1
            print(f"  ✓ Modified {token_json_path.name}")
        else:
            print(f"  ✓ No changes needed")

    print(f"\nModified {modified_count} standalone token JSONs")
    
    # Process card boxes
    print("\n" + "="*60)
    print("Processing card box token bags...")
    cardbox_files = list(tts_objects_dir.glob("*/*Cards.json"))
    cardbox_files = [f for f in cardbox_files if f.parent.name != 'tts_objects']
    
    modified_count = 0
    for cardbox_path in sorted(cardbox_files):
        team_slug = cardbox_path.parent.name
        print(f"\n{team_slug}:")
        
        team_tokens = token_info_by_team.get(team_slug, {})
        if not team_tokens:
            print(f"  ✓ No tokens configured")
            continue
        
        was_modified = fix_cardbox(cardbox_path, team_tokens)
        if was_modified:
            modified_count += 1
            print(f"  ✓ Modified {cardbox_path.name}")
        else:
            print(f"  ✓ No changes needed")
    
    print(f"\nModified {modified_count} card boxes")
    print("\n" + "="*60)
    print("Complete! All tokens now have correct KTUI tags based on config.")


if __name__ == '__main__':
    main()
