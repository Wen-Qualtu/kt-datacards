"""Update Kill Team Card Boxes bag with latest team JSONs from tts_objects/"""
import json
import os
from pathlib import Path

def main():
    # Paths
    workspace_root = Path(__file__).parent.parent
    bag_file = workspace_root / "dev" / "examples" / "Kill Team Card Boxes.json"
    tts_objects_dir = workspace_root / "tts_objects"
    
    print(f"Reading bag file: {bag_file}")
    with open(bag_file, 'r', encoding='utf-8') as f:
        bag_data = json.load(f)
    
    # Get all team boxes in the bag
    contained_objects = bag_data['ObjectStates'][0]['ContainedObjects']
    print(f"Found {len(contained_objects)} teams in bag")
    
    updated_count = 0
    not_found_count = 0
    error_count = 0
    
    # For each team box in the bag
    for i, team_box in enumerate(contained_objects):
        team_name = team_box.get('Nickname', '')
        gm_notes = team_box.get('GMNotes', '')
        
        if not team_name:
            print(f"  Skipping entry {i} (no nickname)")
            continue
        
        # Derive team slug from GMNotes (e.g., "_Angels Of Death" -> "angels-of-death")
        # or from nickname as fallback
        team_slug = gm_notes.strip('_').lower().replace(' ', '-') if gm_notes else team_name.lower().replace(' ', '-')
        
        # Find the corresponding JSON file
        team_dir = tts_objects_dir / team_slug
        team_json_file = team_dir / f"{team_name} Cards.json"
        
        if not team_json_file.exists():
            print(f"  ❌ {team_name}: JSON not found at {team_json_file}")
            not_found_count += 1
            continue
        
        try:
            # Load the latest team JSON
            with open(team_json_file, 'r', encoding='utf-8') as f:
                team_data = json.load(f)
            
            # Extract the first ObjectState (the team box itself)
            if 'ObjectStates' not in team_data or len(team_data['ObjectStates']) == 0:
                print(f"  ❌ {team_name}: Invalid JSON structure")
                error_count += 1
                continue
            
            latest_team_box = team_data['ObjectStates'][0]
            
            # Preserve Transform and GUID from the bag version
            latest_team_box['Transform'] = team_box['Transform']
            latest_team_box['GUID'] = team_box['GUID']
            
            # Replace the team box in the bag
            contained_objects[i] = latest_team_box
            
            print(f"  ✓ {team_name}: Updated")
            updated_count += 1
            
        except Exception as e:
            print(f"  ❌ {team_name}: Error - {e}")
            error_count += 1
    
    # Write the updated bag back
    print(f"\nWriting updated bag to: {bag_file}")
    with open(bag_file, 'w', encoding='utf-8') as f:
        json.dump(bag_data, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✓ Updated: {updated_count}")
    print(f"❌ Not found: {not_found_count}")
    print(f"❌ Errors: {error_count}")
    print(f"{'='*60}")
    
    if updated_count > 0:
        print(f"\n✓ Successfully updated {updated_count} teams in the bag!")
    else:
        print("\n⚠ No teams were updated. Check the paths and team names.")

if __name__ == "__main__":
    main()
