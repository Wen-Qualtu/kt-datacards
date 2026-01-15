"""
Generate TTS token objects from extracted token images.

Creates individual token infinite bags with proper mesh files copied to output.
Each token gets its own .obj mesh file and TTS JSON object.
"""

import argparse
from pathlib import Path
import json
import random
import shutil
import yaml
from typing import Dict, List, Optional


class TTSTokenGenerator:
    """Generate TTS token objects and infinite bags."""
    
    # Template mesh paths in dev/token-meshes
    TEMPLATE_MESH_PATHS = {
        'operative': Path('dev/token-meshes/token-operative.obj'),
        'round': Path('dev/token-meshes/token-round.obj')
    }
    
    # GitHub repo base URL (from existing project)
    GITHUB_BASE = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"
    
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
        """
        Copy template mesh file to output directory with token-specific name.
        
        Args:
            shape: 'operative' or 'round' (also accepts 'complex' for backwards compatibility)
            team_name: Team name (e.g., 'farstalker-kinband')
            token_name: Name of the token (used for output filename)
            output_token_dir: Output token directory for this team
        
        Returns:
            Path to the copied mesh file
        """
        # Handle legacy 'complex' name
        if shape == 'complex':
            shape = 'operative'
        
        template_mesh = self.TEMPLATE_MESH_PATHS[shape]
        
        if not template_mesh.exists():
            raise FileNotFoundError(f"Template mesh not found: {template_mesh}")
        
        # Create output filename: {team}-{token}.obj
        output_mesh = output_token_dir / f"{team_name}-{token_name}.obj"
        
        # Copy the mesh file
        output_mesh.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_mesh, output_mesh)
        
        return output_mesh
    
    def generate_token_object(self, 
                             token_name: str,
                             token_texture_url: str,
                             shape: str = 'operative',
                             scale: float = 0.24) -> Dict:
        """
        Generate a single token object.
        
        Args:
            token_name: Name/nickname for the token
            token_texture_url: URL to the token texture image
            shape: 'operative' or 'round' 
            scale: Scale factor (default 0.24 for operative, 0.228 for round)
        
        Returns:
            TTS token object dict
        """
        # Adjust scale based on shape
        if shape == 'round' and scale == 0.24:
            scale = 0.228
        
        # Set tags based on shape
        if shape == 'round':
            tags = ["KTUIMarker", "KTUIToken"]
        else:
            tags = ["KTUIToken", "KTUITokenSimple"]
        
        return {
            "GUID": self.generate_guid(),
            "Name": "Custom_Token",
            "Transform": {
                "posX": 0.0,
                "posY": 0.0,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 270.0,
                "rotZ": 0.0,
                "scaleX": scale,
                "scaleY": 1.0,
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
            "CustomImage": {
                "ImageURL": token_texture_url,
                "ImageSecondaryURL": "",
                "ImageScalar": 1.0,
                "WidthScale": 0.0,
                "CustomToken": {
                    "Thickness": 0.1,
                    "MergeDistancePixels": 10.0,
                    "StandUp": False,
                    "Stackable": False
                }
            },
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        }
    
    def generate_infinite_bag(self,
                             token_name: str,
                             token_obj: Dict,
                             bag_mesh_url: str) -> Dict:
        """
        Generate an infinite bag containing a single token type.
        
        Args:
            token_name: Name of the token
            token_obj: Token object to include
            bag_mesh_url: URL for the bag's mesh (container mesh, not token mesh)
        
        Returns:
            TTS infinite bag object
        """
        # Create child token template (defines what spawns)
        child_token_template = token_obj.copy()
        child_token_template["Transform"] = {
            "posX": 0.0, "posY": 0.0, "posZ": 0.0,
            "rotX": 0.0, "rotY": 270.0, "rotZ": 0.0,
            "scaleX": 1.0, "scaleY": 1.0, "scaleZ": 1.0
        }
        
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
            "Nickname": f"{token_name} tokens",
            "Description": "",
            "GMNotes": f"_{token_name}_tokens_infi",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 0.0},
            "Tags": [f"_{token_name}_tokens"],
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": True,
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
                "MeshURL": bag_mesh_url,
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
            "ChildObjects": [child_token_template]
        }
    
    
    def generate_individual_token_bags(self,
                                      team_name: str,
                                      metadata_file: Path,
                                      token_images_dir: Path,
                                      output_dir: Path) -> List[Dict]:
        """
        Generate individual infinite bags for each token with mesh files copied to output.
        
        Args:
            team_name: Team name (e.g., 'farstalker-kinband')
            metadata_file: Path to extraction-metadata.json
            token_images_dir: Directory containing extracted token images
            output_dir: Base output directory (output_v2)
        
        Returns:
            List of generated token data dicts
        """
        # Load extraction metadata
        with open(metadata_file) as f:
            metadata = json.load(f)
        
        # Get faction for this team
        faction = self.get_faction(team_name)
        
        # Create output directories
        output_team_dir = output_dir / faction / team_name
        output_token_dir = output_team_dir / 'tts' / 'token'
        output_token_dir.mkdir(parents=True, exist_ok=True)
        
        tokens = []
        
        for token_data in metadata['tokens']:
            filename = token_data['filename']
            token_name = token_data['name']
            shape = token_data['shape']
            
            # Handle legacy 'complex' shape name
            if shape == 'complex':
                shape = 'operative'
            
            # Create clean token name for files
            clean_name = filename.replace('.png', '')
            
            # Create token nickname
            if token_name != 'unknown':
                nickname = token_name
            else:
                nickname = clean_name.replace('-', ' ').title()
            
            # Copy extracted token image to output and convert to JPG
            source_image = token_images_dir / team_name / filename
            dest_image = output_token_dir / f"{team_name}-{clean_name}.jpg"
            
            if source_image.exists():
                # Convert PNG to JPG
                from PIL import Image
                img = Image.open(source_image)
                # Convert RGBA to RGB if needed
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                img.save(dest_image, 'JPEG', quality=95)
            
            # Copy mesh file to output with token-specific name
            mesh_output_path = self.copy_mesh_to_output(shape, team_name, clean_name, output_token_dir)
            
            # Generate URLs
            texture_url = f"{self.GITHUB_BASE}/output_v2/{faction}/{team_name}/tts/token/{dest_image.name}"
            mesh_url = f"{self.GITHUB_BASE}/output_v2/{faction}/{team_name}/tts/token/{mesh_output_path.name}"
            
            # Use the bag mesh URL from tts_generator_helpers
            bag_mesh_url = f"{self.GITHUB_BASE}/config/defaults/box/card-box.obj"
            
            # Create token object
            token_obj = self.generate_token_object(
                token_name=nickname,
                token_texture_url=texture_url,
                shape=shape
            )
            
            # Update token's mesh URL to point to the copied mesh
            # Note: Custom_Token doesn't have a mesh, the shape comes from the CustomImage
            # The mesh is only used by the bag container
            
            # Create infinite bag for this token
            bag = self.generate_infinite_bag(
                token_name=nickname,
                token_obj=token_obj,
                bag_mesh_url=bag_mesh_url
            )
            
            tokens.append({
                'bag': bag,
                'filename': f"{clean_name}.json",
                'token_name': nickname,
                'shape': shape,
                'mesh_path': mesh_output_path,
                'image_path': dest_image
            })
        
        return tokens


def main():
    parser = argparse.ArgumentParser(description='Generate TTS token objects with mesh files')
    parser.add_argument('--team', type=str, required=True,
                       help='Team name (e.g., farstalker-kinband)')
    parser.add_argument('--metadata', type=str, default='dev/extracted-tokens/{team}/extraction-metadata.json',
                       help='Path to extraction metadata file')
    parser.add_argument('--tokens-dir', type=str, default='dev/extracted-tokens',
                       help='Directory with extracted token images')
    parser.add_argument('--output-dir', type=str, default='output_v2',
                       help='Output directory (default: output_v2)')
    parser.add_argument('--tts-json-dir', type=str, default='tts_objects/tokens',
                       help='Directory for standalone TTS JSON files (temp)')
    
    args = parser.parse_args()
    
    tokens_dir = Path(args.tokens_dir)
    output_dir = Path(args.output_dir)
    tts_json_dir = Path(args.tts_json_dir)
    
    generator = TTSTokenGenerator()
    
    print(f"\nGenerating TTS tokens for: {args.team}")
    print("=" * 60)
    
    # Generate token bags
    try:
        metadata_path = Path(args.metadata.replace('{team}', args.team))
        
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
        
        # Generate tokens with mesh files copied to output
        tokens_data = generator.generate_individual_token_bags(
            team_name=args.team,
            metadata_file=metadata_path,
            token_images_dir=tokens_dir,
            output_dir=output_dir
        )
        
        # Get faction for output directory
        faction = generator.get_faction(args.team)
        output_token_dir = output_dir / faction / args.team / 'tts' / 'token'
        
        # Also save standalone JSON files for testing (temp location)
        team_json_dir = tts_json_dir / args.team
        team_json_dir.mkdir(exist_ok=True, parents=True)
        
        print(f"\nFaction: {faction}")
        print(f"Tokens generated:")
        
        # Save each token bag as standalone JSON
        for token_data in tokens_data:
            # Save to tts_objects for testing
            json_output_file = team_json_dir / token_data['filename']
            
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
                "ObjectStates": [token_data['bag']]
            }
            
            with open(json_output_file, 'w') as f:
                json.dump(tts_save, f, indent=2)
            
            print(f"  ✓ {token_data['token_name']} ({token_data['shape']})")
            print(f"    Image: {token_data['image_path'].relative_to(output_dir)}")
            print(f"    Mesh:  {token_data['mesh_path'].relative_to(output_dir)}")
            print(f"    JSON:  {json_output_file.name}")
        
        print(f"\n✓ Generated {len(tokens_data)} token bags")
        print(f"\nOutput locations:")
        print(f"  TTS assets: {output_token_dir.absolute()}")
        print(f"  JSON files: {team_json_dir.absolute()} (temp)")
        print(f"\nNote: Images converted to JPG and mesh files are in output_v2/*/tts/token/")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == '__main__':
    main()
