"""
Generate a team token bag with Setup/Place/Recall functionality.

Creates a Custom_Model_Bag containing all team tokens with a Lua script
for setup, placement, and recall of tokens.

NOTE: This file was moved from dev/ into the production script package so the
pipeline no longer depends on the dev/ folder.
"""

import argparse
from pathlib import Path
import json
import yaml
import hashlib
from typing import Dict, List


class TeamTokenBagGenerator:
    """Generate team token bags with Lua script controls."""

    # Source mesh paths (copied to output_v2 per team for modularity)
    # Using square-bag-mesh.obj - a simple 1x1 square for the bag
    BAG_MESH_SOURCE = "config/defaults/tts-token/square-bag-mesh.obj"

    # GitHub repo base URL
    GITHUB_BASE = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"

    def __init__(self, team_config_path: Path = Path('config/team-config.yaml')):
        self.team_config_path = team_config_path
        self.team_config = self._load_team_config()
        self.lua_script = self._load_lua_script()

    def _load_team_config(self) -> Dict:
        """Load team configuration."""
        if not self.team_config_path.exists():
            return {}

        with open(self.team_config_path) as f:
            config = yaml.safe_load(f)
            return config.get('teams', {})

    def _load_lua_script(self) -> str:
        """Load Lua script from default location."""
        lua_file = Path('config/defaults/tts-token/token-bag-script.lua')
        if lua_file.exists():
            with open(lua_file) as f:
                return f.read()

        # Fallback: return empty string if file doesn't exist
        return ""

    def generate_lua_script_state(self, tokens: List[Dict]) -> str:
        """Generate LuaScriptState with preset token positions."""
        memory_list = {}

        # Single grid layout with 5 tokens per row
        token_spacing_x = 1.5  # Horizontal spacing between tokens
        token_spacing_z = 1.5  # Vertical spacing between tokens
        tokens_per_row = 5

        # Center the grid
        grid_start_x = -3.0
        grid_start_z = -3.0  # Moved closer to bag (was -4.5)

        for i, token in enumerate(tokens):
            row = i // tokens_per_row
            col = i % tokens_per_row

            guid = token.get('GUID', 'unknown')
            nickname = token.get('Nickname', 'unknown')
            print(f"    Token {i}: {nickname} GUID={guid}")

            memory_list[guid] = {
                "lock": False,
                "pos": {
                    "x": round(grid_start_x + (col * token_spacing_x), 4),
                    "y": 0.0213,
                    "z": round(grid_start_z - (row * token_spacing_z), 4),
                },
                "rot": {
                    "x": 0.0,
                    "y": 180.0,
                    "z": 0.0,
                },
            }

        print(f"  Generated LuaScriptState with {len(memory_list)} tokens")

        lua_state = {
            "ml": memory_list,
            "rr": 270,  # Relative rotation of bag
        }

        return json.dumps(lua_state)

    def get_faction(self, team_name: str) -> str:
        """Get faction for a team from config."""
        team_data = self.team_config.get(team_name, {})
        return team_data.get('faction', 'unknown')

    def generate_guid(self, seed: str) -> str:
        """Generate a deterministic 6-character hexadecimal GUID from a seed."""
        return hashlib.md5(seed.encode('utf-8')).hexdigest()[:6]

    def _copy_bag_mesh(self, team_name: str, faction: str, output_dir: Path) -> str:
        """Copy bag mesh to output_v2/{faction}/{team}/tts/ and return URL.
        
        Each team gets its own mesh copy for future customization.
        Always overwrites to ensure updates are applied.
        """
        import shutil
        
        source = Path(self.BAG_MESH_SOURCE)
        dest_dir = output_dir / faction / team_name / 'tts'
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{team_name}-token-bag.obj"
        
        # Always overwrite to ensure updates are applied
        shutil.copy2(source, dest)
        
        return f"{self.GITHUB_BASE}/output_v2/{faction}/{team_name}/tts/{dest.name}"

    def _get_icon_image_url(self, team_name: str, faction: str, output_dir: Path) -> str:
        """Resolve and copy team icon image to output, return URL.

        Copies from config/teams/{team}/tts-image/ to output_v2/{faction}/{team}/tts/
        """
        team_dir = Path('config/teams') / team_name / 'tts-image'
        icon_source = None
        
        if team_dir.exists():
            exact = team_dir / f"{team_name}-icon.png"
            if exact.exists():
                icon_source = exact
            else:
                matches = sorted(team_dir.glob('*icon*.png'))
                if matches:
                    icon_source = matches[0]

        if not icon_source:
            icon_source = Path('config/defaults/tts-image/default-icon.png')

        # Copy to output_v2/{faction}/{team}/tts/
        dest_dir = output_dir / faction / team_name / 'tts'
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / f"{team_name}-icon.png"
        
        import shutil
        shutil.copy2(icon_source, dest_file)
        
        return f"{self.GITHUB_BASE}/output_v2/{faction}/{team_name}/tts/{dest_file.name}"

    def generate_team_icon_tile(self, team_name: str, faction: str, output_dir: Path) -> Dict:
        """Generate the Custom_Tile showing team icon."""
        icon_url = self._get_icon_image_url(team_name, faction, output_dir)

        return {
            "GUID": self.generate_guid(f"{team_name}:icon_tile"),
            "Name": "Custom_Tile",
            "Transform": {
                "posX": 0.0,
                "posY": -0.5,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 270.0,
                "rotZ": 0.0,
                "scaleX": 0.5,
                "scaleY": 10.0,
                "scaleZ": 0.5,
            },
            "Nickname": "",
            "Description": "",
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
            "Locked": False,
            "Grid": True,
            "Snap": True,
            "Autoraise": True,
            "Sticky": True,
            "Tooltip": True,
            "Hands": False,
            "CustomImage": {
                "ImageURL": icon_url,
                "ImageSecondaryURL": icon_url,
                "ImageScalar": 1.0,
                "WidthScale": 0.0,
                "CustomTile": {
                    "Type": 0,
                    "Thickness": 0.1,
                    "Stackable": False,
                    "Stretch": True,
                },
            },
        }

    def generate_team_bag(self, team_name: str, token_bags: List[Dict], output_dir: Path) -> Dict:
        """Generate a team token bag containing all token infinite bags."""
        faction = self.get_faction(team_name)
        team_display = team_name.replace('-', ' ').title()

        # Copy bag mesh and icon to output_v2 and get URLs
        bag_mesh_url = self._copy_bag_mesh(team_name, faction, output_dir)
        icon_url = self._get_icon_image_url(team_name, faction, output_dir)

        # Generate team icon tile
        icon_tile = self.generate_team_icon_tile(team_name, faction, output_dir)

        # Generate preset Lua script state with token positions
        lua_script_state = self.generate_lua_script_state(token_bags)

        bag = {
            "GUID": self.generate_guid(f"{team_name}:team_token_bag"),
            "Name": "Custom_Model_Bag",
            "Transform": {
                "posX": 0.0,
                "posY": 1.01,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 270.0,
                "rotZ": 0.0,
                "scaleX": 1.47,
                "scaleY": 0.1,
                "scaleZ": 1.47,
            },
            "Nickname": f"{team_display} tokens",
            "Description": "If errors pop up, just wait for few sec and try again",
            "GMNotes": f"_{team_name}_tokens",
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 0.0},
            "Tags": [f"_{team_name}"],
            "Locked": False,
            "Grid": True,
            "Snap": True,
            "Autoraise": True,
            "Sticky": True,
            "Tooltip": True,
            "Hands": False,
            "Number": 0,
            "CustomMesh": {
                "MeshURL": bag_mesh_url,
                "DiffuseURL": "",
                "NormalURL": "",
                "ColliderURL": "",
                "Convex": True,
                "MaterialIndex": 0,
                "TypeIndex": 6,
                "CastShadows": True,
            },
            "Bag": {"Order": 0},
            "LuaScript": self.lua_script,
            "LuaScriptState": lua_script_state,
            "ContainedObjects": token_bags,
            "ChildObjects": [icon_tile],
        }

        return bag


def main():
    parser = argparse.ArgumentParser(description='Generate team token bag with all tokens')
    parser.add_argument('--team', type=str, required=True, help='Team name (e.g., farstalker-kinband)')
    parser.add_argument(
        '--tokens-dir',
        type=str,
        default='tts_objects',
        help='Directory with individual token JSON files',
    )
    parser.add_argument('--output-dir', type=str, default='output_v2', help='Output directory (default: output_v2)')

    args = parser.parse_args()

    tokens_dir = Path(args.tokens_dir) / args.team / 'tokens'
    output_dir = Path(args.output_dir)

    generator = TeamTokenBagGenerator()

    print(f"\nGenerating team token bag for: {args.team}")
    print("=" * 60)

    # Get faction for output path
    faction = generator.get_faction(args.team)
    if faction == 'unknown':
        print(f"Warning: Faction not found for {args.team}, using 'unknown'")

    # Output to output_v2/{faction}/{team}/tts/token/
    team_output_dir = output_dir / faction / args.team / 'tts' / 'token'
    team_output_dir.mkdir(exist_ok=True, parents=True)

    # Load all token bag objects
    token_bags = []
    if not tokens_dir.exists():
        print(f"Error: Token directory not found: {tokens_dir}")
        return

    for json_file in sorted(tokens_dir.glob('*.json')):
        # Skip the tokenbag file itself
        if json_file.name.endswith('-tokenbag.json'):
            continue
        with open(json_file) as f:
            data = json.load(f)
            # Extract the infinite bag object itself (so users can take infinite tokens)
            if 'ObjectStates' in data and len(data['ObjectStates']) > 0:
                bag_obj = data['ObjectStates'][0]
                nickname = bag_obj.get('Nickname', json_file.stem)

                # Deterministic GUID per token bag (stable across reruns)
                bag_obj['GUID'] = generator.generate_guid(f"{args.team}:{nickname}:token_infinite_bag")

                # Add team tag to the bag so the bag script can target them
                bag_obj['Tags'] = (bag_obj.get('Tags') or []) + [f"_{args.team}_tokens"]

                token_bags.append(bag_obj)
                print(f"  ✓ Loaded {json_file.stem}")

    if not token_bags:
        print("Error: No token bags found")
        return

    # Generate team bag
    team_bag = generator.generate_team_bag(args.team, token_bags, output_dir)

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
        "ObjectStates": [team_bag],
    }

    # Save team bag to output_v2
    output_file = team_output_dir / f"{args.team}-tokens.json"
    with open(output_file, 'w') as f:
        json.dump(tts_save, f, indent=2)

    print(f"\n✓ Generated team bag with {len(token_bags)} tokens")
    print(f"Output: {output_file.absolute()}")


if __name__ == '__main__':
    main()
