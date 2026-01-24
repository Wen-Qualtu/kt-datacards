"""
Extract token dispenser bags from card box JSON files and save them as separate files.

This script:
1. Reads each card box JSON file
2. Finds the token dispenser bag (Custom_Model_Bag with nickname ending in "tokens")
3. Saves it as a separate JSON file in tts_objects/tokens/{team}/{team}-tokenbag.json
"""

import json
from pathlib import Path
import re


def slugify(text: str) -> str:
    """Convert team name to slug format."""
    return text.lower().replace(' ', '-').replace("'", '')


def extract_token_bag(card_box_file: Path):
    """Extract token dispenser bag from a card box JSON file."""
    print(f"Processing: {card_box_file.name}")
    
    with open(card_box_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if 'ObjectStates' not in data or len(data['ObjectStates']) == 0:
        print(f"  ⚠ No ObjectStates found")
        return
    
    card_box = data['ObjectStates'][0]
    
    if 'ContainedObjects' not in card_box:
        print(f"  ⚠ No ContainedObjects found")
        return
    
    # Find the token dispenser bag
    token_bag = None
    for obj in card_box['ContainedObjects']:
        nickname = obj.get('Nickname', '')
        if nickname.endswith(' tokens') and obj.get('Name') == 'Custom_Model_Bag':
            token_bag = obj
            break
    
    if not token_bag:
        print(f"  ⚠ No token dispenser bag found")
        return
    
    # Extract team name from nickname
    team_name = token_bag['Nickname'].replace(' tokens', '')
    team_slug = slugify(team_name)
    
    # Create output directory
    output_dir = Path('tts_objects') / 'tokens' / team_slug
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Wrap in TTS save format
    tts_save = {
        "SaveName": "",
        "Date": "",
        "VersionNumber": "",
        "GameMode": "",
        "GameType": "",
        "GameComplexity": "",
        "Tags": [],
        "Gravity": 0.5,
        "PlayArea": 0.5,
        "Table": "",
        "Sky": "",
        "Note": "",
        "TabStates": {},
        "LuaScript": "",
        "LuaScriptState": "",
        "XmlUI": "",
        "ObjectStates": [token_bag],
    }
    
    # Save to file
    output_file = output_dir / f"{team_slug}-tokenbag.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tts_save, f, indent=2)
    
    print(f"  ✓ Saved to {output_file}")
    print(f"    Team: {team_name} ({team_slug})")
    print(f"    Contains: {len(token_bag.get('ContainedObjects', []))} token bags")


def main():
    tts_objects_dir = Path('tts_objects')
    
    if not tts_objects_dir.exists():
        print(f"Error: {tts_objects_dir} directory not found")
        return
    
    # Find all card box JSON files
    card_box_files = list(tts_objects_dir.glob('*Cards.json'))
    
    if not card_box_files:
        print("No card box files found")
        return
    
    print(f"Found {len(card_box_files)} card box files\n")
    
    for file_path in sorted(card_box_files):
        try:
            extract_token_bag(file_path)
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    print(f"\n✓ Processed {len(card_box_files)} files")


if __name__ == '__main__':
    main()
