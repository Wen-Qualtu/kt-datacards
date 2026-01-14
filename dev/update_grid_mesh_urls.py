"""
Update mesh URLs in the TTS grid file to use team-specific URLs
This version uses simple text replacement to preserve the exact file structure and encoding
"""
import json
import re
from pathlib import Path

def main():
    workspace_dir = Path(__file__).parent.parent
    grid_file = workspace_dir / 'tts_objects' / 'display-table' / 'kt_all_teams_grid.json'
    urls_file = workspace_dir / 'output_v2' / 'datacards-urls.json'
    
    # Load URLs database
    print(f"Loading URLs from {urls_file}...")
    with open(urls_file, encoding='utf-8') as f:
        url_entries = json.load(f)
    
    # Build a mapping of team -> mesh URL
    mesh_urls = {}
    for entry in url_entries:
        if entry['type'] == 'tts' and entry['name'].endswith('.obj'):
            team = entry['team']
            mesh_urls[team] = entry['url']
    
    print(f"Found {len(mesh_urls)} team mesh URLs")
    
    # Read grid file as raw bytes to preserve exact encoding
    print(f"\nLoading grid file from {grid_file}...")
    with open(grid_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # For each team, find and replace the old MeshURL pattern with new URL
    updated_count = 0
    
    # Find all old-style GitHub URLs in MeshURLs
    # Pattern: "MeshURL": "https://github.com/USER/REPO/blob/BRANCH/path/TEAMNAME-card-box.obj"
    # Replace with: "MeshURL": "https://raw.githubusercontent.com/USER/REPO/BRANCH/path/TEAMNAME-card-box.obj"
    
    for team_slug, new_url in mesh_urls.items():
        # The filename should be: {team_slug}-card-box.obj
        obj_filename = f"{team_slug}-card-box.obj"
        
        # Pattern to match any GitHub URL (blob or raw) that ends with this team's obj file
        # This will match the MeshURL value specifically
        pattern = rf'"MeshURL":\s*"https://[^"]*/{re.escape(obj_filename)}"'
        
        def replace_func(match):
            nonlocal updated_count
            old_line = match.group(0)
            new_line = f'"MeshURL": "{new_url}"'
            
            if old_line != new_line:
                updated_count += 1
                # Convert team slug to display name
                team_name = team_slug.replace('-', ' ').title()
                print(f"  ✓ Updated {team_name}: {new_url}")
            
            return new_line
        
        content = re.sub(pattern, replace_func, content)
    
    # Save updated grid file with exact encoding
    print(f"\nSaving updated grid file...")
    with open(grid_file, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    
    print(f"\n✓ Updated {updated_count} team mesh URLs in grid file")
    print(f"✓ Grid file saved to: {grid_file}")

if __name__ == '__main__':
    main()
