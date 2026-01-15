"""
Generate TTS infinite token bags from extracted token images.

Creates infinite bags that spawn individual tokens. Each bag is a separate object
that can spawn unlimited copies of a specific token.

Based on the Hearthkyn Salvagers token system structure.
"""

import argparse
from pathlib import Path
import json
import random
import shutil
import yaml
from typing import Dict, List


class InfiniteBagGenerator:
    """Generate infinite token bags for TTS."""
    
    # GitHub repo base URL
    GITHUB_BASE = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"
    
    # Bag mesh URL (from Hearthkyn Salvagers example)
    # This is a simple invisible container mesh
    BAG_MESH_URL = "https://steamusercontent-a.akamaihd.net/ugc/1666858152071990826/9AD455F2CBAEC01B2CBCDDB8B6DC4CE48D14B545/"
    
    # Template mesh paths
    TEMPLATE_MESH_PATHS = {
        'operative': Path('dev/token-meshes/token-operative.obj'),
        'round': Path('dev/token-meshes/token-round.obj')
    }
    
    def __init__(self, team_config_path: Path = Path('config/team-config.yaml')):
        self.team_config_path = team_config_path
        self.team_config = self._load_team_config()
    
    def _load_team_config(self) -> Dict:
        """Load team configuration to get faction information."""
        if not self.team_config_path.exists():
            print(f"Warning: Team config not found: {self.team_config_path}")
            return {}
        
        with open(self.team_config_path) as f:
            config = yaml.safe_load(f)
            return config.get('teams', {})
    
    def get_faction(self, team_name: str) -> str:
        """Get faction for a team from config."""
        team_data = self.team_config.get(team_name, {})
        return team_data.get('faction', 'unknown')
    
    def generate_guid(self) -> str:
        """Generate a random 6-character hexadecimal GUID."""
        return ''.join(random.choices('0123456789abcdef', k=6))
    
    def copy_mesh_to_output(self, shape: str, team_name: str, token_name: str, output_token_dir: Path) -> Path:
        """Copy template mesh file to output directory (all tokens of same shape use same mesh)."""
        template_mesh = self.TEMPLATE_MESH_PATHS[shape]
        
        if not template_mesh.exists():
            raise FileNotFoundError(f"Template mesh not found: {template_mesh}\nCreate a good mesh manually at this location!")
        
        # Use same mesh file for all tokens of this shape
        output_mesh = output_token_dir / f"{team_name}-{token_name}.obj"
        output_mesh.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_mesh, output_mesh)
        
        return output_mesh
    
    def create_token_object(self, 
                           token_name: str,
                           token_texture_url: str,
                           token_mesh_url: str,
                           shape: str = 'operative',
                           scale: float = None) -> Dict:
        """
        Create a single token object using Custom_Model with mesh.
        
        Args:
            token_name: Display name for the token
            token_texture_url: URL to the token PNG image
            token_mesh_url: URL to the token mesh .obj file
            shape: 'operative' or 'round'
            scale: Custom scale (defaults based on shape)
        
        Returns:
            Token object dict
        """
        # Default scales by shape
        if scale is None:
            scale = 0.228 if shape == 'round' else 0.24
        
        # Tags based on shape
        if shape == 'round':
            tags = ["KTUIMarker", "KTUIToken"]
        else:
            tags = ["KTUIToken", "KTUITokenSimple"]
        
        return {
            "GUID": self.generate_guid(),
            "Name": "Custom_Model",
            "Transform": {
                "posX": 0.0,
                "posY": 0.0,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 270.0,
                "rotZ": 0.0,
                "scaleX": scale,
                "scaleY": scale,
                "scaleZ": scale
            },
            "Nickname": token_name,
            "Description": token_name,
            "GMNotes": "",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
            "Tags": tags,
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": False,
            "Grid": True,
            "Snap": False,
            "IgnoreFoW": False,
            "MeasureMovement": False,
            "DragSelectable": True,
            "Autoraise": True,
            "Sticky": False,
            "Tooltip": False,
            "GridProjection": False,
            "HideWhenFaceDown": False,
            "Hands": False,
            "MaterialIndex": -1,
            "MeshIndex": -1,
            "CustomMesh": {
                "MeshURL": token_mesh_url,
                "DiffuseURL": token_texture_url,
                "NormalURL": "",
                "ColliderURL": "",
                "Convex": True,
                "MaterialIndex": 3,
                "TypeIndex": 4,
                "CustomShader": {
                    "SpecularColor": {"r": 1.0, "g": 1.0, "b": 1.0},
                    "SpecularIntensity": 0.0,
                    "SpecularSharpness": 2.0,
                    "FresnelStrength": 0.0
                },
                "CastShadows": True
            },
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        }
    
    def create_infinite_bag(self,
                          token_name: str,
                          token_obj: Dict) -> Dict:
        """
        Create an infinite bag that spawns a specific token type.
        
        Args:
            token_name: Name of the token
            token_obj: Token object that will be spawned
        
        Returns:
            Infinite bag object dict
        """
        return {
            "GUID": self.generate_guid(),
            "Name": "Custom_Model_Infinite_Bag",
            "Transform": {
                "posX": 0.0,
                "posY": 3.5,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 270.0,
                "rotZ": 0.0,
                "scaleX": 1.25,
                "scaleY": 0.1,
                "scaleZ": 1.25
            },
            "Nickname": f"{token_name}",
            "Description": f"Infinite {token_name} tokens",
            "GMNotes": f"_{token_name.lower().replace(' ', '_')}_tokens_infi",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 0.0},
            "Tags": [f"_{token_name.lower().replace(' ', '_')}_tokens"],
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": False,
            "Grid": True,
            "Snap": True,
            "IgnoreFoW": False,
            "MeasureMovement": False,
            "DragSelectable": True,
            "Autoraise": True,
            "Sticky": True,
            "Tooltip": True,
            "GridProjection": False,
            "HideWhenFaceDown": False,
            "Hands": False,
            "MaterialIndex": -1,
            "MeshIndex": -1,
            "CustomMesh": {
                "MeshURL": self.BAG_MESH_URL,
                "DiffuseURL": "",
                "NormalURL": "",
                "ColliderURL": "",
                "Convex": True,
                "MaterialIndex": 0,
                "TypeIndex": 7,
                "CastShadows": True
            },
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": "",
            "ContainedObjects": [token_obj],
            "ChildObjects": [token_obj]
        }
    
    def generate_team_token_bags(self,
                                team_name: str,
                                metadata_file: Path,
                                token_images_dir: Path,
                                output_dir: Path) -> List[Dict]:
        """
        Generate all token bags for a team.
        
        Args:
            team_name: Team name
            metadata_file: extraction-metadata.json path
            token_images_dir: Directory with extracted token images
            output_dir: Base output directory
        
        Returns:
            List of bag data dicts
        """
        # Load metadata
        with open(metadata_file) as f:
            metadata = json.load(f)
        
        faction = self.get_faction(team_name)
        
        # Create output directories
        output_team_dir = output_dir / faction / team_name / 'tts' / 'token'
        output_team_dir.mkdir(parents=True, exist_ok=True)
        
        bags = []
        
        for token_data in metadata['tokens']:
            filename = token_data['filename']
            token_name = token_data['name']
            shape = token_data['shape']
            
            # Handle unknown names
            if token_name == 'unknown':
                clean_name = filename.replace('.png', '').replace('-', ' ').title()
                token_name = clean_name
            
            clean_filename = filename.replace('.png', '')
            
            # Copy token image to output
            source_image = token_images_dir / team_name / filename
            dest_image = output_team_dir / f"{team_name}-{clean_filename}.png"
            
            if source_image.exists():
                shutil.copy2(source_image, dest_image)
            else:
                print(f"  ⚠ Warning: Token image not found: {source_image}")
                continue
            
            # Generate texture URL
            texture_url = f"{self.GITHUB_BASE}/output_v2/{faction}/{team_name}/tts/token/{dest_image.name}"
            
            # Copy mesh file to output
            mesh_file = self.copy_mesh_to_output(shape, team_name, clean_filename, output_team_dir)
            mesh_url = f"{self.GITHUB_BASE}/output_v2/{faction}/{team_name}/tts/token/{mesh_file.name}"
            
            # Create token object
            token_obj = self.create_token_object(
                token_name=token_name,
                token_texture_url=texture_url,
                token_mesh_url=mesh_url,
                shape=shape
            )
            
            # Create infinite bag
            bag = self.create_infinite_bag(
                token_name=token_name,
                token_obj=token_obj
            )
            
            bags.append({
                'bag': bag,
                'token_name': token_name,
                'shape': shape,
                'filename': f"{clean_filename}.json",
                'image_path': dest_image
            })
        
        return bags
    
    def create_master_bag(self,
                         team_name: str,
                         token_bags: List[Dict]) -> Dict:
        """
        Create a master bag that contains all individual token bags.
        
        Args:
            team_name: Team name
            token_bags: List of token bag objects
        
        Returns:
            Master bag object
        """
        # Extract just the bag objects
        bag_objects = [b['bag'] for b in token_bags]
        
        # Adjust positions in a grid layout
        cols = 4
        spacing = 2.5
        
        for i, bag_obj in enumerate(bag_objects):
            row = i // cols
            col = i % cols
            
            bag_obj['Transform']['posX'] = col * spacing - (cols - 1) * spacing / 2
            bag_obj['Transform']['posZ'] = row * spacing
            bag_obj['Transform']['posY'] = 1.0
        
        return {
            "GUID": self.generate_guid(),
            "Name": "Bag",
            "Transform": {
                "posX": 0.0,
                "posY": 2.0,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 0.0,
                "rotZ": 0.0,
                "scaleX": 1.0,
                "scaleY": 1.0,
                "scaleZ": 1.0
            },
            "Nickname": f"{team_name.replace('-', ' ').title()} Tokens",
            "Description": f"All token bags for {team_name}",
            "GMNotes": "",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 0.7, "g": 0.7, "b": 0.7},
            "Tags": ["KTUITokenBag"],
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": False,
            "Grid": True,
            "Snap": True,
            "IgnoreFoW": False,
            "MeasureMovement": False,
            "DragSelectable": True,
            "Autoraise": True,
            "Sticky": True,
            "Tooltip": True,
            "GridProjection": False,
            "HideWhenFaceDown": False,
            "Hands": False,
            "MaterialIndex": 0,
            "MeshIndex": -1,
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": "",
            "ContainedObjects": bag_objects
        }


def main():
    parser = argparse.ArgumentParser(description='Generate infinite token bags for TTS')
    parser.add_argument('--team', type=str, required=True,
                       help='Team name (e.g., farstalker-kinband)')
    parser.add_argument('--metadata', type=str, default='dev/extracted-tokens/{team}/extraction-metadata.json',
                       help='Path to extraction metadata file')
    parser.add_argument('--tokens-dir', type=str, default='dev/extracted-tokens',
                       help='Directory with extracted token images')
    parser.add_argument('--output-dir', type=str, default='output_v2',
                       help='Output directory')
    parser.add_argument('--tts-json-dir', type=str, default='tts_objects/tokens',
                       help='Directory for TTS JSON output files')
    parser.add_argument('--create-master-bag', action='store_true',
                       help='Create a master bag containing all token bags')
    
    args = parser.parse_args()
    
    generator = InfiniteBagGenerator()
    
    print(f"\n🎲 Generating infinite token bags for: {args.team}")
    print("=" * 60)
    
    try:
        metadata_path = Path(args.metadata.replace('{team}', args.team))
        
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
        
        # Generate bags
        bags_data = generator.generate_team_token_bags(
            team_name=args.team,
            metadata_file=metadata_path,
            token_images_dir=Path(args.tokens_dir),
            output_dir=Path(args.output_dir)
        )
        
        faction = generator.get_faction(args.team)
        output_token_dir = Path(args.output_dir) / faction / args.team / 'tts' / 'token'
        
        # Create TTS JSON output directory
        team_json_dir = Path(args.tts_json_dir) / args.team
        team_json_dir.mkdir(exist_ok=True, parents=True)
        
        print(f"\nFaction: {faction}")
        print(f"\n📦 Generated {len(bags_data)} token bags:")
        
        # Save individual bags
        for bag_data in bags_data:
            json_file = team_json_dir / bag_data['filename']
            
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
                "ObjectStates": [bag_data['bag']]
            }
            
            with open(json_file, 'w') as f:
                json.dump(tts_save, f, indent=2)
            
            print(f"  ✓ {bag_data['token_name']:30} ({bag_data['shape']:8}) → {bag_data['filename']}")
        
        # Create master bag if requested
        if args.create_master_bag:
            master_bag = generator.create_master_bag(args.team, bags_data)
            
            master_json_file = team_json_dir / f"{args.team}-all-tokens.json"
            
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
                "ObjectStates": [master_bag]
            }
            
            with open(master_json_file, 'w') as f:
                json.dump(tts_save, f, indent=2)
            
            print(f"\n🎒 Master bag created: {master_json_file.name}")
            print(f"   Contains all {len(bags_data)} token bags")
        
        print(f"\n✓ Success!")
        print(f"\nOutput locations:")
        print(f"  Token images: {output_token_dir}")
        print(f"  TTS JSON:     {team_json_dir}")
        print(f"\n💡 To use in TTS:")
        print(f"   1. Objects → Saved Objects → Import")
        print(f"   2. Select any .json file from: {team_json_dir}")
        print(f"   3. Right-click bag → Place to spawn tokens")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == '__main__':
    main()
