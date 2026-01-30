"""Sync team-config.yaml tokens with actual tokens in TTS output files.

This script:
1. Scans all token bag JSON files to find actual token names
2. Updates team-config.yaml to match (adds missing, removes non-existent)
3. Leaves type and shape empty for manual correction
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Set


def load_team_config() -> dict:
    """Load the team configuration YAML file."""
    config_path = Path("config/team-config.yaml")
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_team_config(config: dict):
    """Save the team configuration YAML file."""
    config_path = Path("config/team-config.yaml")
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def get_tokens_from_json(json_path: Path) -> Set[str]:
    """Extract token names from a token bag or card box JSON file."""
    tokens = set()
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not data.get('ObjectStates') or len(data['ObjectStates']) == 0:
        return tokens
    
    # For card boxes, we need to find the token bag inside
    if json_path.name.endswith('Cards.json'):
        card_box = data['ObjectStates'][0]
        contained_objects = card_box.get('ContainedObjects', [])
        
        # Find the token bag
        for obj in contained_objects:
            nickname = obj.get('Nickname', '').lower()
            if 'token' in nickname and obj.get('Name') == 'Custom_Model_Bag':
                infinite_bags = obj.get('ContainedObjects', [])
                break
        else:
            return tokens
    else:
        # Standalone token bag
        token_bag = data['ObjectStates'][0]
        infinite_bags = token_bag.get('ContainedObjects', [])
    
    # Extract token names from infinite bags
    for infinite_bag in infinite_bags:
        if infinite_bag.get('Name') == 'Custom_Model_Infinite_Bag':
            nickname = infinite_bag.get('Nickname', '').strip()
            if nickname:
                tokens.add(nickname.lower())
    
    return tokens


def get_all_tokens_from_output() -> Dict[str, Set[str]]:
    """Scan all TTS output files and return tokens by team."""
    tts_objects_dir = Path("tts_objects")
    tokens_by_team = {}
    
    # Get all team directories
    team_dirs = [d for d in tts_objects_dir.iterdir() if d.is_dir()]
    
    for team_dir in team_dirs:
        team_slug = team_dir.name
        tokens = set()
        
        # Check for standalone token bag
        tokenbag_files = list(team_dir.glob("*tokenbag.json"))
        for tokenbag_file in tokenbag_files:
            tokens.update(get_tokens_from_json(tokenbag_file))
        
        # Check for card box
        cardbox_files = list(team_dir.glob("*Cards.json"))
        for cardbox_file in cardbox_files:
            tokens.update(get_tokens_from_json(cardbox_file))
        
        if tokens:
            tokens_by_team[team_slug] = tokens
    
    return tokens_by_team


def sync_config_with_output():
    """Sync team-config.yaml with actual tokens in output files."""
    print("Scanning TTS output files for actual tokens...")
    actual_tokens = get_all_tokens_from_output()
    
    print(f"Found tokens in {len(actual_tokens)} teams")
    
    print("\nLoading team configuration...")
    config = load_team_config()
    
    teams_modified = 0
    tokens_added = 0
    tokens_removed = 0
    
    teams_dict = config.get('teams', {})
    
    for team_slug, team_data in teams_dict.items():
        # Get actual tokens for this team
        actual = actual_tokens.get(team_slug, set())
        
        # Get config tokens for this team
        config_tokens = team_data.get('tokens', [])
        config_token_names = {t.get('name', '').lower() for t in config_tokens if t.get('name')}
        
        if actual == config_token_names:
            print(f"{team_slug}: ✓ Already in sync ({len(actual)} tokens)")
            continue
        
        teams_modified += 1
        print(f"\n{team_slug}:")
        
        # Find tokens to add
        to_add = actual - config_token_names
        if to_add:
            print(f"  Adding {len(to_add)} tokens: {sorted(to_add)}")
            for token_name in sorted(to_add):
                config_tokens.append({
                    'name': token_name,
                    'shape': '',
                    'type': ''
                })
                tokens_added += 1
        
        # Find tokens to remove
        to_remove = config_token_names - actual
        if to_remove:
            print(f"  Removing {len(to_remove)} tokens: {sorted(to_remove)}")
            config_tokens[:] = [t for t in config_tokens if t.get('name', '').lower() not in to_remove]
            tokens_removed += len(to_remove)
        
        # Update team tokens
        team_data['tokens'] = config_tokens
    
    if teams_modified > 0:
        print(f"\n{'='*60}")
        print(f"Saving updated configuration...")
        save_team_config(config)
        print(f"✓ Modified {teams_modified} teams")
        print(f"  Added: {tokens_added} tokens")
        print(f"  Removed: {tokens_removed} tokens")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print("All teams already in sync!")
        print(f"{'='*60}")


if __name__ == '__main__':
    sync_config_with_output()
