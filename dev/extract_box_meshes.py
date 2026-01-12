#!/usr/bin/env python3
"""
Extract box mesh URLs from example TTS files and download them to the appropriate team folders.
"""

import json
import subprocess
from pathlib import Path

def extract_bag_mesh(json_file):
    """Extract the CustomMesh URLs from a Custom_Model_Bag in a TTS JSON file."""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Look through ObjectStates for Custom_Model_Bag with CustomMesh
    for obj in data.get('ObjectStates', []):
        if obj.get('Name') == 'Custom_Model_Bag' and 'CustomMesh' in obj:
            mesh = obj['CustomMesh']
            team_name = obj.get('Nickname', '').strip()
            return {
                'team': team_name,
                'mesh_url': mesh.get('MeshURL', ''),
                'texture_url': mesh.get('DiffuseURL', '')
            }
    
    return None

def download_file(url, output_path):
    """Download a file from a URL to the specified path using PowerShell."""
    print(f"  Downloading {url}")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Use PowerShell Invoke-WebRequest
    cmd = f'Invoke-WebRequest -Uri "{url}" -OutFile "{output_path}"'
    subprocess.run(['powershell', '-Command', cmd], check=True, capture_output=True)
    
    print(f"  ✓ Saved to {output_path}")

def main():
    # Get the example directory
    example_dir = Path(__file__).parent.parent / "tts_objects" / "example"
    config_dir = Path(__file__).parent.parent / "config" / "box" / "team"
    
    if not example_dir.exists():
        print(f"Error: {example_dir} not found!")
        return
    
    print("Scanning example files for box meshes...\n")
    
    # Process each JSON file in the example directory
    for json_file in example_dir.glob("*.json"):
        # Skip the "Cards.json" files (those are our generated ones)
        if "Cards.json" in json_file.name:
            continue
        
        print(f"Processing {json_file.name}...")
        
        try:
            mesh_info = extract_bag_mesh(json_file)
            
            if not mesh_info:
                print(f"  ⚠ No Custom_Model_Bag found\n")
                continue
            
            if not mesh_info['mesh_url'] or not mesh_info['texture_url']:
                print(f"  ⚠ Missing mesh or texture URL\n")
                continue
            
            team_name = mesh_info['team']
            if not team_name:
                print(f"  ⚠ No team name found\n")
                continue
            
            # Convert team name to folder name (lowercase with hyphens)
            team_folder = team_name.lower().replace(' ', '-')
            team_dir = config_dir / team_folder
            
            print(f"  Team: {team_name} → {team_folder}")
            
            # Download mesh
            mesh_path = team_dir / "card-box.obj"
            if not mesh_path.exists():
                download_file(mesh_info['mesh_url'], mesh_path)
            else:
                print(f"  ✓ Mesh already exists: {mesh_path}")
            
            # Download texture
            texture_path = team_dir / "card-box-texture.jpg"
            if not texture_path.exists():
                download_file(mesh_info['texture_url'], texture_path)
            else:
                print(f"  ✓ Texture already exists: {texture_path}")
            
            print()
            
        except Exception as e:
            print(f"  ✗ Error: {e}\n")
    
    print("\n✓ Done!")

if __name__ == "__main__":
    main()
