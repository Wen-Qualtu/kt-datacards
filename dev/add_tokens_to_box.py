"""
Add token bag to the main TTS box object.

Reads the team token bag JSON and adds it to the ContainedObjects
of the main box JSON file.
"""

import argparse
from pathlib import Path
import json


def add_tokens_to_box(box_file: Path, token_bag_file: Path):
    """
    Add token bag to the main box's ContainedObjects and LuaScriptState.
    
    Args:
        box_file: Path to main box JSON (e.g., tts_objects/Farstalker Kinband Cards.json)
        token_bag_file: Path to token bag JSON
    """
    
    if not box_file.exists():
        print(f"Error: Box file not found: {box_file}")
        return False
    
    if not token_bag_file.exists():
        print(f"Error: Token bag file not found: {token_bag_file}")
        return False
    
    # Load box JSON
    print(f"Loading box: {box_file}")
    with open(box_file) as f:
        box_data = json.load(f)
    
    # Load token bag JSON
    print(f"Loading token bag: {token_bag_file}")
    with open(token_bag_file) as f:
        token_bag_data = json.load(f)
    
    # Extract the token bag object
    if 'ObjectStates' not in token_bag_data or len(token_bag_data['ObjectStates']) == 0:
        print("Error: Token bag JSON has no ObjectStates")
        return False
    
    token_bag_obj = token_bag_data['ObjectStates'][0]
    
    # Get the box object
    if 'ObjectStates' not in box_data or len(box_data['ObjectStates']) == 0:
        print("Error: Box JSON has no ObjectStates")
        return False
    
    box_obj = box_data['ObjectStates'][0]
    
    # Check if ContainedObjects exists
    if 'ContainedObjects' not in box_obj:
        box_obj['ContainedObjects'] = []
    
    # Check if token bag already exists (by name)
    token_bag_name = token_bag_obj.get('Nickname', '')
    existing_idx = None
    for i, obj in enumerate(box_obj['ContainedObjects']):
        if obj.get('Nickname', '') == token_bag_name:
            existing_idx = i
            break
    
    # Add or replace token bag
    if existing_idx is not None:
        print(f"Replacing existing token bag at index {existing_idx}")
        box_obj['ContainedObjects'][existing_idx] = token_bag_obj
    else:
        print(f"Adding new token bag to ContainedObjects")
        box_obj['ContainedObjects'].append(token_bag_obj)
    
    # Add token bag to LuaScriptState
    lua_state = box_obj.get('LuaScriptState', '')
    if lua_state:
        try:
            state_data = json.loads(lua_state)
        except:
            state_data = {"ml": {}, "rr": 270}
    else:
        state_data = {"ml": {}, "rr": 270}
    
    # Position token bag: right side, aligned with bottom of other cards
    # Cards are at z=-7.39 (bottom row), token bag should be at similar z
    # Right side at x=5.5, slightly lower (z=-8.5 to align bottom)
    token_bag_guid = token_bag_obj.get('GUID', 'unknown')
    state_data['ml'][token_bag_guid] = {
        "lock": False,
        "pos": {
            "x": 5.5,  # Right side, next to cards
            "y": -2.46,  # Same height as cards
            "z": -8.5  # Lower to align bottom with card bottoms
        },
        "rot": {
            "x": 0.0169,
            "y": 179.9995,
            "z": 0.0799
        }
    }
    
    # Update LuaScriptState
    box_obj['LuaScriptState'] = json.dumps(state_data)
    print(f"Added token bag to LuaScriptState at position x=5.5, z=-8.5")
    
    # Save updated box
    with open(box_file, 'w') as f:
        json.dump(box_data, f, indent=2)
    
    print(f"✓ Updated box with token bag")
    print(f"  Total objects in box: {len(box_obj['ContainedObjects'])}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Add token bag to main TTS box')
    parser.add_argument('--team', type=str, required=True,
                       help='Team name (e.g., farstalker-kinband)')
    parser.add_argument('--box-dir', type=str, default='tts_objects',
                       help='Directory containing box JSON files')
    parser.add_argument('--output-dir', type=str, default='output_v2',
                       help='Output directory with token bags')
    
    args = parser.parse_args()
    
    # Find box file (search for matching team name)
    box_dir = Path(args.box_dir)
    output_dir = Path(args.output_dir)
    
    # Try to find box file by team name (with proper casing)
    team_display = args.team.replace('-', ' ').title()
    box_file = box_dir / f"{team_display} Cards.json"
    
    if not box_file.exists():
        # Try alternate naming patterns
        box_file = box_dir / f"{args.team}.json"
    
    if not box_file.exists():
        print(f"Error: Could not find box file for team: {args.team}")
        print(f"Tried: {box_dir / f'{team_display} Cards.json'}")
        print(f"Tried: {box_dir / f'{args.team}.json'}")
        return
    
    # Find token bag file
    # Need to determine faction first
    import yaml
    team_config_path = Path('config/team-config.yaml')
    if team_config_path.exists():
        with open(team_config_path) as f:
            config = yaml.safe_load(f)
            teams = config.get('teams', {})
            faction = teams.get(args.team, {}).get('faction', 'unknown')
    else:
        faction = 'unknown'
    
    token_bag_file = output_dir / faction / args.team / 'tts' / 'token' / f"{args.team}-tokens.json"
    
    if not token_bag_file.exists():
        print(f"Error: Token bag not found: {token_bag_file}")
        return
    
    # Add tokens to box
    success = add_tokens_to_box(box_file, token_bag_file)
    
    if success:
        print(f"\n✓ Successfully added token bag to box")
    else:
        print(f"\n✗ Failed to add token bag to box")


if __name__ == '__main__':
    main()
