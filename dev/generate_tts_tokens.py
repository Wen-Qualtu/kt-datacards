"""
Generate TTS token objects from extracted token images.

Creates token infinite bags with the proper structure based on
the two token shape templates (round and complex).
"""

import argparse
from pathlib import Path
import json
import random
from typing import Dict, List


class TTSTokenGenerator:
    """Generate TTS token objects and infinite bags."""
    
    # Template meshes for the infinite bags containing the tokens
    MESH_TEMPLATES = {
        'complex': 'https://steamusercontent-a.akamaihd.net/ugc/1666858288775771801/9B3BE50061314478867674DFD2262D4CD3DC30A3/',
        'round': 'https://steamusercontent-a.akamaihd.net/ugc/1666858152071991282/5C391C2599AE5F6972D6EFA7BFC04B41D6E821E3/'
    }
    
    def __init__(self, github_repo_base: str = "https://raw.githubusercontent.com/YOUR_REPO/kt-datacards/main"):
        self.github_repo_base = github_repo_base
    
    def generate_guid(self) -> str:
        """Generate a random 6-character hexadecimal GUID."""
        return ''.join(random.choices('0123456789abcdef', k=6))
    
    def generate_token_object(self, 
                             token_name: str,
                             token_texture_url: str,
                             shape: str = 'complex',
                             scale: float = 0.24) -> Dict:
        """
        Generate a single token object.
        
        Args:
            token_name: Name/nickname for the token
            token_texture_url: URL to the token texture image
            shape: 'complex' or 'round' 
            scale: Scale factor (default 0.24 for complex, 0.228 for round)
        
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
                             team_name: str,
                             tokens: List[Dict],
                             mesh_url: str = None) -> Dict:
        """
        Generate an infinite bag containing tokens.
        
        Args:
            team_name: Name of the team
            tokens: List of token objects to include
            mesh_url: Custom mesh URL for the bag (uses complex shape by default)
        
        Returns:
            TTS infinite bag object
        """
        if mesh_url is None:
            mesh_url = self.MESH_TEMPLATES['complex']
        
        # Create a template token for the ChildObjects (defines what spawns)
        child_token_template = tokens[0].copy() if tokens else self.generate_token_object(
            f"{team_name}_token", "", 'complex'
        )
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
            "Nickname": f"{team_name} tokens",
            "Description": "",
            "GMNotes": f"_{team_name}_tokens_infi",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 0.0},
            "Tags": [f"_{team_name}_tokens"],
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
                "MeshURL": mesh_url,
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
            "ContainedObjects": tokens,
            "ChildObjects": [child_token_template]
        }
    
    def generate_tokens_from_analysis(self,
                                     team_name: str,
                                     analysis_file: Path,
                                     token_images_dir: Path) -> Dict:
        """
        Generate token objects from shape analysis file.
        
        Args:
            team_name: Team name
            analysis_file: Path to token-shape-analysis.json
            token_images_dir: Directory containing extracted token images
        
        Returns:
            Dict with 'round' and 'complex' infinite bags
        """
        # Load analysis
        with open(analysis_file) as f:
            analysis_data = json.load(f)
        
        # Find team data
        team_data = None
        for team in analysis_data:
            if team['team'] == team_name:
                team_data = team
                break
        
        if not team_data:
            raise ValueError(f"Team {team_name} not found in analysis file")
        
        results = {}
        
        # Generate tokens for each shape category
        for shape in ['round', 'complex']:
            tokens = []
            token_list = team_data['tokens'][shape]
            
            for token_info in token_list:
                filename = token_info['filename']
                token_path = token_images_dir / team_name / filename
                
                # Generate URL for uploaded token image
                # This will need to be updated with actual GitHub repo path
                texture_url = f"{self.github_repo_base}/output_v2/tokens/{team_name}/{filename}"
                
                # Create descriptive name from filename
                token_name = f"{team_name}_{filename.replace('token-', '').replace('.png', '')}"
                
                token_obj = self.generate_token_object(
                    token_name=token_name,
                    token_texture_url=texture_url,
                    shape=shape
                )
                tokens.append(token_obj)
            
            # Create infinite bag for this shape category
            if tokens:
                bag = self.generate_infinite_bag(
                    team_name=f"{team_name}_{shape}",
                    tokens=tokens,
                    mesh_url=self.MESH_TEMPLATES[shape]
                )
                results[shape] = bag
        
        return results


    def generate_individual_infinite_bags(self,
                                         team_name: str,
                                         metadata_file: Path,
                                         token_images_dir: Path) -> List[Dict]:
        """
        Generate individual infinite bags for each token (like the examples).
        Each token type gets its own infinite bag.
        
        Args:
            team_name: Team name
            metadata_file: Path to extraction-metadata.json
            token_images_dir: Directory containing extracted token images
        
        Returns:
            List of infinite bag dicts
        """
        # Load extraction metadata
        with open(metadata_file) as f:
            metadata = json.load(f)
        
        bags = []
        
        for token_data in metadata['tokens']:
            filename = token_data['filename']
            token_name = token_data['name']
            shape = token_data['shape']
            
            token_path = token_images_dir / team_name / filename
            
            # Generate URL for uploaded token image
            texture_url = f"{self.github_repo_base}/output_v2/tokens/{team_name}/{filename}"
            
            # Create token nickname
            if token_name != 'unknown':
                nickname = token_name
            else:
                # Use filename without extension
                nickname = filename.replace('.png', '').replace('-', ' ').title()
            
            # Create single token object
            token_obj = self.generate_token_object(
                token_name=nickname,
                token_texture_url=texture_url,
                shape=shape
            )
            
            # Create infinite bag for this single token type
            bag = self.generate_infinite_bag(
                team_name=nickname,
                tokens=[token_obj],
                mesh_url=self.MESH_TEMPLATES[shape]
            )
            
            bags.append({
                'bag': bag,
                'filename': f"{filename.replace('.png', '')}.json",
                'token_name': nickname,
                'shape': shape
            })
        
        return bags


def main():
    parser = argparse.ArgumentParser(description='Generate TTS token objects')
    parser.add_argument('--team', type=str, required=True,
                       help='Team name (e.g., farstalker-kinband)')
    parser.add_argument('--mode', choices=['grouped', 'individual'], default='individual',
                       help='grouped: one bag per shape, individual: one bag per token (default)')
    parser.add_argument('--analysis', type=str, default='dev/token-shape-analysis.json',
                       help='Path to token shape analysis file (for grouped mode)')
    parser.add_argument('--metadata', type=str, default='dev/extracted-tokens/{team}/extraction-metadata.json',
                       help='Path to extraction metadata file (for individual mode)')
    parser.add_argument('--tokens-dir', type=str, default='dev/extracted-tokens',
                       help='Directory with extracted token images')
    parser.add_argument('--output-dir', type=str, default='tts_objects/tokens',
                       help='Output directory for TTS JSON files')
    parser.add_argument('--github-repo', type=str,
                       default='https://raw.githubusercontent.com/YOUR_REPO/kt-datacards/main',
                       help='GitHub repository base URL for token images')
    
    args = parser.parse_args()
    
    tokens_dir = Path(args.tokens_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)
    
    generator = TTSTokenGenerator(github_repo_base=args.github_repo)
    
    print(f"\nGenerating TTS tokens for: {args.team} (mode: {args.mode})")
    print("=" * 60)
    
    # Generate token bags
    try:
        if args.mode == 'individual':
            # Individual bags - one per token type
            metadata_path = Path(args.metadata.replace('{team}', args.team))
            
            if not metadata_path.exists():
                raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
            
            bags_data = generator.generate_individual_infinite_bags(
                team_name=args.team,
                metadata_file=metadata_path,
                token_images_dir=tokens_dir
            )
            
            # Create team output directory
            team_output_dir = output_dir / args.team
            team_output_dir.mkdir(exist_ok=True, parents=True)
            
            # Save each bag
            for bag_data in bags_data:
                output_file = team_output_dir / bag_data['filename']
                
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
                
                with open(output_file, 'w') as f:
                    json.dump(tts_save, f, indent=2)
                
                print(f"  ✓ {bag_data['token_name']} ({bag_data['shape']}) -> {output_file.name}")
            
            print(f"\n✓ Generated {len(bags_data)} individual token bags")
            print(f"  Output directory: {team_output_dir.absolute()}")
        
        else:
            # Grouped bags - one per shape
            analysis_file = Path(args.analysis)
            
            bags = generator.generate_tokens_from_analysis(
                team_name=args.team,
                analysis_file=analysis_file,
                token_images_dir=tokens_dir
            )
            
            # Save each bag
            for shape, bag in bags.items():
                output_file = output_dir / f"{args.team}_{shape}_tokens.json"
                
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
                    "ObjectStates": [bag]
                }
                
                with open(output_file, 'w') as f:
                    json.dump(tts_save, f, indent=2)
                
                print(f"  ✓ Generated {shape} tokens bag: {output_file.name}")
                token_count = len(bag['ContainedObjects'])
                print(f"    Contains {token_count} tokens")
        
        print(f"\n⚠ Note: Update --github-repo parameter with your actual repository URL")
        print(f"   and upload token images to that location.")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == '__main__':
    main()
