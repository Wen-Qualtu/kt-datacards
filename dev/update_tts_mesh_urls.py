"""
Update mesh URLs in existing TTS object files without regenerating them
"""
import json
from pathlib import Path

def main():
    workspace_dir = Path(__file__).parent.parent
    tts_objects_dir = workspace_dir / 'tts_objects'
    urls_file = workspace_dir / 'output_v2' / 'datacards-urls.json'
    
    # Load URLs database
    print(f"Loading URLs from {urls_file}...")
    with open(urls_file) as f:
        url_entries = json.load(f)
    
    # Build a mapping of team -> mesh URL
    mesh_urls = {}
    for entry in url_entries:
        if entry['type'] == 'tts' and entry['name'].endswith('.obj'):
            team = entry['team']
            mesh_urls[team] = entry['url']
    
    print(f"Found {len(mesh_urls)} team mesh URLs")
    
    # Update each TTS object file
    updated_count = 0
    for tts_file in tts_objects_dir.glob("* Cards.json"):
        # Extract team name from filename (e.g., "Wolf Scouts Cards.json" -> "wolf-scouts")
        team_display_name = tts_file.stem[:-6]  # Remove " Cards"
        team_slug = team_display_name.lower().replace(' ', '-')
        
        if team_slug not in mesh_urls:
            print(f"  ⚠ No mesh URL found for: {team_display_name}")
            continue
        
        # Load TTS object
        with open(tts_file, 'r', encoding='utf-8') as f:
            tts_data = json.load(f)
        
        # Update mesh URL in the bag object
        if 'ObjectStates' in tts_data and len(tts_data['ObjectStates']) > 0:
            bag = tts_data['ObjectStates'][0]
            if 'CustomMesh' in bag:
                old_url = bag['CustomMesh'].get('MeshURL', '')
                new_url = mesh_urls[team_slug]
                
                if old_url != new_url:
                    bag['CustomMesh']['MeshURL'] = new_url
                    
                    # Save updated file
                    with open(tts_file, 'w', encoding='utf-8') as f:
                        json.dump(tts_data, f, indent=2)
                    
                    updated_count += 1
                    print(f"  ✓ Updated {team_display_name}")
    
    print(f"\n✓ Updated {updated_count} TTS object files")

if __name__ == '__main__':
    main()
