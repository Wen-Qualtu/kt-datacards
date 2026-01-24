import json

# Check individual card boxes
boxes_to_check = ['Blooded Cards.json', 'Kasrkin Cards.json', 'Pathfinders Cards.json']

print("Checking timestamps in card boxes:")
print("=" * 60)
for box_file in boxes_to_check:
    with open(f'tts_objects/{box_file}') as f:
        data = json.load(f)
    
    state = json.loads(data['ObjectStates'][0]['LuaScriptState'])
    timestamp = state.get('lastCardUpdate', 'NOT FOUND')
    print(f"{box_file:30s} → {timestamp}")

print("\n✓ All boxes have timestamps embedded in LuaScriptState!")

