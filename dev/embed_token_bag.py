"""
Simple script to embed token bag into Farstalker Kinband Cards.json
"""
import json
from pathlib import Path

# Paths
token_bag_path = Path('output_v2/xenos/farstalker-kinband/tts/token/farstalker-kinband-tokens.json')
farstalker_tts_path = Path('tts_objects/Farstalker Kinband Cards.json')

# Load token bag
with open(token_bag_path, 'r', encoding='utf-8') as f:
    token_data = json.load(f)
    token_bag = token_data['ObjectStates'][0]  # Get the bag object

# Load Farstalker TTS object
with open(farstalker_tts_path, 'r', encoding='utf-8') as f:
    farstalker_data = json.load(f)

# Get the main bag
main_bag = farstalker_data['ObjectStates'][0]

# Insert token bag at the beginning of ContainedObjects
if 'ContainedObjects' not in main_bag:
    main_bag['ContainedObjects'] = []

# Remove any existing token bag (in case we run this multiple times)
main_bag['ContainedObjects'] = [
    obj for obj in main_bag['ContainedObjects'] 
    if 'token' not in obj.get('Nickname', '').lower()
]

# Add token bag at the start
main_bag['ContainedObjects'].insert(0, token_bag)

# Save back to file
with open(farstalker_tts_path, 'w', encoding='utf-8') as f:
    json.dump(farstalker_data, f, indent=2)

print(f"✓ Token bag embedded into {farstalker_tts_path}")
print(f"  Main bag now has {len(main_bag['ContainedObjects'])} objects")
print(f"  Token bag has {len(token_bag.get('ContainedObjects', []))} tokens")
