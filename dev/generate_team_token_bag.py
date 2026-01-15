"""
Generate a team token bag with Setup/Place/Recall functionality.

Creates a Custom_Model_Bag containing all team tokens with a Lua script
for setup, placement, and recall of tokens.
"""

import argparse
from pathlib import Path
import json
import random
import shutil
import yaml
from typing import Dict, List


class TeamTokenBagGenerator:
    """Generate team token bags with Lua script controls."""
    
    # Bag mesh template
    BAG_MESH_URL = "https://steamusercontent-a.akamaihd.net/ugc/1666858152071990826/9AD455F2CBAEC01B2CBCDDB8B6DC4CE48D14B545/"
    
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
        """Load Lua script from example file."""
        lua_file = Path('dev/examples/token-bag-script.lua')
        if lua_file.exists():
            with open(lua_file) as f:
                return f.read()
        
        # Fallback: return empty string if file doesn't exist
        return ""
    
    def generate_lua_script_state(self, tokens: List[Dict]) -> str:
        """
        Generate LuaScriptState with preset token positions.
        Arranges tokens in two areas: round tokens on left, operative tokens on right.
        Tokens are arranged in rows of 3.
        """
        memory_list = {}
        
        # Separate tokens by shape
        round_tokens = []
        operative_tokens = []
        
        for token in tokens:
            # Determine shape by scale (round=0.228, operative=0.24)
            scale = token['Transform']['scaleX']
            if abs(scale - 0.228) < 0.01:  # round token
                round_tokens.append(token)
            else:  # operative token
                operative_tokens.append(token)
        
        # Layout parameters
        token_spacing_x = 1.3  # Horizontal spacing between tokens
        token_spacing_z = 1.3  # Vertical spacing between tokens
        tokens_per_row = 3
        
        # Round tokens on the left side
        round_start_x = -3.5
        round_start_z = -4.5
        
        for i, token in enumerate(round_tokens):
            row = i // tokens_per_row
            col = i % tokens_per_row
            
            guid = token.get('GUID', 'unknown')
            print(f"    Round token {i}: {token.get('Nickname', 'unknown')} GUID={guid}")
            
            memory_list[guid] = {
                "lock": True,
                "pos": {
                    "x": round(round_start_x + (col * token_spacing_x), 4),
                    "y": 0.0213,
                    "z": round(round_start_z + (row * token_spacing_z), 4)
                },
                "rot": {
                    "x": 0.0,
                    "y": 180.0,  # Right-side up
                    "z": 0.0
                }
            }
        
        # Operative tokens on the right side
        operative_start_x = 1.0
        operative_start_z = -4.5
        
        for i, token in enumerate(operative_tokens):
            row = i // tokens_per_row
            col = i % tokens_per_row
            
            guid = token.get('GUID', 'unknown')
            print(f"    Operative token {i}: {token.get('Nickname', 'unknown')} GUID={guid}")
            
            memory_list[guid] = {
                "lock": True,
                "pos": {
                    "x": round(operative_start_x + (col * token_spacing_x), 4),
                    "y": 0.0213,
                    "z": round(operative_start_z + (row * token_spacing_z), 4)
                },
                "rot": {
                    "x": 0.0,
                    "y": 180.0,  # Right-side up
                    "z": 0.0
                }
            }
        
        print(f"  Generated LuaScriptState with {len(memory_list)} tokens")
        
        # Create Lua script state
        lua_state = {
            "ml": memory_list,
            "rr": 270  # Relative rotation of bag
        }
        
        return json.dumps(lua_state)
    
    def get_faction(self, team_name: str) -> str:
        """Get faction for a team from config."""
        team_data = self.team_config.get(team_name, {})
        return team_data.get('faction', 'unknown')
    
    def generate_guid(self) -> str:
        """Generate a random 6-character hexadecimal GUID."""
        return ''.join(random.choices('0123456789abcdef', k=6))
    
    def generate_team_icon_tile(self, team_name: str, faction: str) -> Dict:
        """Generate the Custom_Tile showing team icon."""
        icon_url = f"{self.GITHUB_BASE}/config/teams/{team_name}/tts-image/{team_name}-preview.png"
        
        return {
            "GUID": self.generate_guid(),
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
                "scaleZ": 0.5
            },
            "Nickname": "",
            "Description": "",
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
            "Locked": True,
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
                    "Stretch": True
                }
            }
        }
    
    def generate_team_bag(self,
                         team_name: str,
                         token_bags: List[Dict]) -> Dict:
        """Generate a team token bag containing all token infinite bags."""
        
        faction = self.get_faction(team_name)
        team_display = team_name.replace('-', ' ').title()
        
        # Generate team icon tile
        icon_tile = self.generate_team_icon_tile(team_name, faction)
        
        # Generate preset Lua script state with token positions
        lua_script_state = self.generate_lua_script_state(token_bags)
        
        # Create bag with token infinite bags as contained objects
        bag = {
            "GUID": self.generate_guid(),
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
                "scaleZ": 1.47
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
                "MeshURL": self.BAG_MESH_URL,
                "DiffuseURL": "",
                "NormalURL": "",
                "ColliderURL": "",
                "Convex": True,
                "MaterialIndex": 0,
                "TypeIndex": 6,
                "CastShadows": True
            },
            "Bag": {
                "Order": 0
            },
            "LuaScript": self.lua_script,
            "LuaScriptState": lua_script_state,
            "ContainedObjects": token_bags,
            "ChildObjects": [icon_tile]
        }
        
        return bag


def main():
    parser = argparse.ArgumentParser(description='Generate team token bag with all tokens')
    parser.add_argument('--team', type=str, required=True,
                       help='Team name (e.g., farstalker-kinband)')
    parser.add_argument('--tokens-dir', type=str, default='tts_objects/tokens',
                       help='Directory with individual token JSON files')
    parser.add_argument('--output-dir', type=str, default='output_v2',
                       help='Output directory (default: output_v2)')
    
    args = parser.parse_args()
    
    tokens_dir = Path(args.tokens_dir) / args.team
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
    
    generator = TeamTokenBagGenerator()
    
    print(f"\nGenerating team token bag for: {args.team}")
    print("=" * 60)
    
    # Load all token bag objects
    token_bags = []
    if not tokens_dir.exists():
        print(f"Error: Token directory not found: {tokens_dir}")
        return
    
    for json_file in sorted(tokens_dir.glob('*.json')):
        with open(json_file) as f:
            data = json.load(f)
            # Extract the token from inside the bag (ContainedObjects)
            if 'ObjectStates' in data and len(data['ObjectStates']) > 0:
                bag_obj = data['ObjectStates'][0]
                if 'ContainedObjects' in bag_obj and len(bag_obj['ContainedObjects']) > 0:
                    # Get the actual token (not the infinite bag wrapper)
                    token = bag_obj['ContainedObjects'][0]
                    # Generate unique GUID for each token
                    token['GUID'] = generator.generate_guid()
                    # Add team tag to the token
                    token['Tags'] = token.get('Tags', []) + [f"_{args.team}_tokens"]
                    token_bags.append(token)
                    print(f"  ✓ Loaded {json_file.stem}")
    
    if not token_bags:
        print("Error: No token bags found")
        return
    
    # Generate team bag
    team_bag = generator.generate_team_bag(args.team, token_bags)
    
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
        "ObjectStates": [team_bag]
    }
    
    # Save team bag to output_v2
    output_file = team_output_dir / f"{args.team}-tokens.json"
    with open(output_file, 'w') as f:
        json.dump(tts_save, f, indent=2)
    
    print(f"\n✓ Generated team bag with {len(token_bags)} tokens")
    print(f"Output: {output_file.absolute()}")


if __name__ == '__main__':
    main()
