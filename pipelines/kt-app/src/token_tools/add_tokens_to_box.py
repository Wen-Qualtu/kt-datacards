"""Add token bag to the main TTS box object.

Reads the team token bag JSON and adds it to the ContainedObjects of the main
box JSON file.

NOTE: This file was moved from dev/ into the production script package so the
pipeline no longer depends on the dev/ folder.
"""

import argparse
from pathlib import Path
import json


def add_tokens_to_box(box_file: Path, token_bag_file: Path):
    """Add token bag to the main box's ContainedObjects and LuaScriptState."""

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
        print("Adding new token bag to ContainedObjects")
        box_obj['ContainedObjects'].append(token_bag_obj)

    # Add token bag to LuaScriptState
    lua_state = box_obj.get('LuaScriptState', '')
    if lua_state:
        try:
            state_data = json.loads(lua_state)
        except Exception:
            state_data = {"ml": {}, "rr": 270}
    else:
        state_data = {"ml": {}, "rr": 270}

    token_bag_guid = token_bag_obj.get('GUID', 'unknown')
    state_data['ml'][token_bag_guid] = {
        "lock": False,
        "pos": {
            "x": 4.0,
            "y": -2.50,
            "z": -8.0,
        },
        "rot": {
            "x": 0.0,
            "y": 270.0,
            "z": 0.0,
        },
    }

    # Update LuaScriptState
    box_obj['LuaScriptState'] = json.dumps(state_data)
    print("Added token bag to LuaScriptState at position x=4.0, z=-8.0")

    # Save updated box
    with open(box_file, 'w') as f:
        json.dump(box_data, f, indent=2)

    print("✓ Updated box with token bag")
    print(f"  Total objects in box: {len(box_obj['ContainedObjects'])}")

    return True


def main():
    parser = argparse.ArgumentParser(description='Add token bag to main TTS box')
    parser.add_argument('--team', type=str, required=True, help='Team name (e.g., farstalker-kinband)')
    parser.add_argument('--box-dir', type=str, default='tts_objects', help='Directory containing box JSON files')
    parser.add_argument('--output-dir', type=str, default='output_v2', help='Output directory with token bags')

    args = parser.parse_args()

    box_dir = Path(args.box_dir)
    output_dir = Path(args.output_dir)

    team_display = args.team.replace('-', ' ').title()
    box_file = box_dir / f"{team_display} Cards.json"

    if not box_file.exists():
        box_file = box_dir / f"{args.team}.json"

    if not box_file.exists():
        print(f"Error: Could not find box file for team: {args.team}")
        print(f"Tried: {box_dir / f'{team_display} Cards.json'}")
        print(f"Tried: {box_dir / f'{args.team}.json'}")
        return

    # Find token bag file
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

    success = add_tokens_to_box(box_file, token_bag_file)

    if success:
        print("\n✓ Successfully added token bag to box")
    else:
        print("\n✗ Failed to add token bag to box")


if __name__ == '__main__':
    main()
