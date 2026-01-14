"""
Download TTS token mesh files and prepare token object generation.

This script downloads the 3D mesh files used for Kill Team tokens
and prepares to generate token objects with custom textures.
"""

import argparse
import requests
from pathlib import Path
import json
from typing import Dict, List
from urllib.parse import urlparse


class TokenMeshManager:
    """Manage token mesh files for TTS objects."""
    
    # Known mesh URLs from existing TTS mods
    # These are the standard shapes used for Kill Team tokens
    KNOWN_MESHES = {
        'bag': 'https://steamusercontent-a.akamaihd.net/ugc/1666858152071990826/9AD455F2CBAEC01B2CBCDDB8B6DC4CE48D14B545/',
        # We'll need to find the actual token mesh URLs - they should be similar patterns
        # Typically round tokens and complex shaped tokens have different meshes
    }
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True, parents=True)
    
    def download_mesh(self, url: str, name: str) -> Path | None:
        """Download a mesh file from URL."""
        try:
            print(f"  Downloading {name}...")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Save with appropriate extension (usually .obj)
            output_path = self.output_dir / f"{name}.obj"
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            print(f"    ✓ Saved: {output_path}")
            return output_path
        except Exception as e:
            print(f"    ✗ Failed: {e}")
            return None
    
    def extract_mesh_urls_from_tts_json(self, json_path: Path) -> Dict[str, str]:
        """Extract mesh URLs from a TTS JSON file."""
        with open(json_path) as f:
            data = json.load(f)
        
        mesh_urls = {}
        
        def find_meshes(obj, path="root"):
            """Recursively find mesh URLs in TTS object."""
            if isinstance(obj, dict):
                # Check for CustomMesh
                if 'CustomMesh' in obj and 'MeshURL' in obj['CustomMesh']:
                    mesh_url = obj['CustomMesh']['MeshURL']
                    nickname = obj.get('Nickname', 'unknown')
                    mesh_urls[f"{nickname}_{path}"] = mesh_url
                
                # Check for Custom_Model
                if 'CustomModel' in obj and 'MeshURL' in obj['CustomModel']:
                    mesh_url = obj['CustomModel']['MeshURL']
                    nickname = obj.get('Nickname', 'unknown')
                    mesh_urls[f"{nickname}_{path}"] = mesh_url
                
                # Recurse into nested structures
                for key, value in obj.items():
                    if key in ['ObjectStates', 'ChildObjects', 'ContainedObjects']:
                        if isinstance(value, list):
                            for i, item in enumerate(value):
                                find_meshes(item, f"{path}.{key}[{i}]")
                    else:
                        find_meshes(value, f"{path}.{key}")
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    find_meshes(item, f"{path}[{i}]")
        
        find_meshes(data)
        return mesh_urls
    
    def generate_token_object(self, 
                             token_image_path: Path,
                             mesh_url: str,
                             token_name: str,
                             guid: str = None) -> Dict:
        """
        Generate a TTS token object definition.
        
        Args:
            token_image_path: Path to the token texture image
            mesh_url: URL to the 3D mesh for the token
            token_name: Name of the token
            guid: Optional GUID (will be generated if not provided)
        
        Returns:
            TTS object dict
        """
        if guid is None:
            # Generate a random GUID (6 hex characters)
            import random
            guid = ''.join(random.choices('0123456789abcdef', k=6))
        
        # For TTS, we'll need to upload the texture image somewhere
        # For now, we'll use a placeholder URL structure
        texture_url = f"https://raw.githubusercontent.com/YOUR_REPO/kt-datacards/main/output_v2/tokens/{token_image_path.name}"
        
        return {
            "GUID": guid,
            "Name": "Custom_Token",
            "Transform": {
                "posX": 0.0,
                "posY": 2.0,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 270.0,
                "rotZ": 0.0,
                "scaleX": 1.0,
                "scaleY": 1.0,
                "scaleZ": 1.0
            },
            "Nickname": token_name,
            "Description": "",
            "GMNotes": "",
            "ColorDiffuse": {
                "r": 1.0,
                "g": 1.0,
                "b": 1.0
            },
            "Tags": [],
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": true,
            "Grid": true,
            "Snap": true,
            "IgnoreFoW": false,
            "MeasureMovement": false,
            "DragSelectable": true,
            "Autoraise": true,
            "Sticky": true,
            "Tooltip": true,
            "GridProjection": false,
            "HideWhenFaceDown": false,
            "Hands": false,
            "CustomImage": {
                "ImageURL": texture_url,
                "ImageSecondaryURL": texture_url,
                "ImageScalar": 1.0,
                "WidthScale": 0.0,
                "CustomToken": {
                    "Thickness": 0.1,
                    "MergeDistancePixels": 15.0,
                    "StandUp": False,
                    "Stackable": False
                }
            },
            "CustomMesh": {
                "MeshURL": mesh_url,
                "DiffuseURL": texture_url,
                "NormalURL": "",
                "ColliderURL": "",
                "Convex": True,
                "MaterialIndex": 3,
                "TypeIndex": 0,
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


def main():
    parser = argparse.ArgumentParser(description='Manage token meshes and object generation')
    parser.add_argument('--extract-meshes', type=str, 
                       help='Extract mesh URLs from TTS JSON file')
    parser.add_argument('--download', action='store_true',
                       help='Download mesh files')
    parser.add_argument('--output-dir', type=str, default='dev/token-meshes',
                       help='Output directory for mesh files')
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    manager = TokenMeshManager(output_dir)
    
    if args.extract_meshes:
        json_path = Path(args.extract_meshes)
        print(f"\nExtracting mesh URLs from: {json_path}")
        print("=" * 60)
        
        mesh_urls = manager.extract_mesh_urls_from_tts_json(json_path)
        
        if mesh_urls:
            print(f"\nFound {len(mesh_urls)} mesh URLs:")
            for name, url in mesh_urls.items():
                print(f"  {name}:")
                print(f"    {url}")
            
            # Save to JSON
            output_json = output_dir / "extracted-mesh-urls.json"
            with open(output_json, 'w') as f:
                json.dump(mesh_urls, f, indent=2)
            print(f"\n✓ Saved to: {output_json}")
            
            if args.download:
                print(f"\nDownloading meshes...")
                for name, url in mesh_urls.items():
                    manager.download_mesh(url, name)
        else:
            print("  No mesh URLs found")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
