"""Generate a minimal JSON file containing only TTS card box object URLs."""

import json
from pathlib import Path


def generate_tts_boxes_json():
    """Generate tts-card-boxes.json with only TTS box objects."""
    
    # Read the full datacards-urls.json
    urls_file = Path(__file__).parent.parent.parent.parent / 'output_v2' / 'datacards-urls.json'
    
    with open(urls_file, 'r', encoding='utf-8') as f:
        all_entries = json.load(f)
    
    # Filter for tts_card_box_object entries only
    tts_boxes = []
    seen_teams = set()
    
    for entry in all_entries:
        if entry.get('type') == 'tts_card_box_object':
            team = entry.get('team', '')
            # Skip duplicates
            if team not in seen_teams:
                seen_teams.add(team)
                tts_boxes.append({
                    'team': team,
                    'name': entry.get('name', ''),
                    'url': entry.get('url', '')
                })
    
    # Write minimal JSON
    output_file = Path(__file__).parent.parent.parent.parent / 'output_v2' / 'tts-card-boxes.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tts_boxes, f, indent=2)
    
    print(f"✓ Generated {output_file.name}")
    print(f"  - {len(tts_boxes)} TTS card boxes")
    print(f"  - Original: {len(all_entries)} entries")
    print(f"  - Reduced to: {len(tts_boxes)} entries ({len(tts_boxes)/len(all_entries)*100:.1f}%)")


if __name__ == '__main__':
    generate_tts_boxes_json()
