import os
import shutil
from pathlib import Path

def add_default_backsides():
    """
    For all cards with only a _front image, copy the default backside image as _back.
    Uses landscape orientation for datacards, portrait for others.
    Checks for team-specific backside first, then falls back to common default.
    
    Backside priority:
    1. Team-specific: script/config/card-backside/team/{team-name}/backside-{orientation}.jpg
    2. Default: script/config/card-backside/default/default-backside-{orientation}.jpg
    """
    output_dir = Path('output')
    default_backside_portrait = Path('script/config/card-backside/default/default-backside-portrait.jpg')
    default_backside_landscape = Path('script/config/card-backside/default/default-backside-landscape.jpg')
    
    if not default_backside_portrait.exists():
        print(f"[ERROR] Error: Default portrait backside image not found at {default_backside_portrait}")
        print("Please save the default-backside-portrait.jpg image in script/config/card-backside/default/")
        return
    
    if not default_backside_landscape.exists():
        print(f"[ERROR] Error: Default landscape backside image not found at {default_backside_landscape}")
        print("Please save the default-backside-landscape.jpg image in script/config/card-backside/default/")
        return
    
    print(f"Default backsides location: script/config/card-backside/default/\n")
    
    added_count = 0
    
    # Walk through all team folders
    for team_dir in sorted(output_dir.iterdir()):
        if not team_dir.is_dir():
            continue
        
        team_name = team_dir.name
        
        # Check if team has custom backsides in script/config/card-backside/team/{team}/
        team_backside_dir = Path(f'script/config/card-backside/team/{team_name}')
        team_backside_portrait = team_backside_dir / 'backside-portrait.jpg'
        team_backside_landscape = team_backside_dir / 'backside-landscape.jpg'
        
        if team_backside_portrait.exists() or team_backside_landscape.exists():
            print(f"[CUSTOM] Team '{team_name}' has custom backsides:")
            if team_backside_portrait.exists():
                print(f"  - Portrait: {team_backside_portrait}")
            if team_backside_landscape.exists():
                print(f"  - Landscape: {team_backside_landscape}")
            print()
        
        # Look for all card type folders
        for type_dir in team_dir.iterdir():
            if not type_dir.is_dir():
                continue
            
            print(f"Processing: {team_dir.name}/{type_dir.name}")
            
            # Determine if this is datacards (landscape) or other types (portrait)
            is_datacards = 'datacard' in type_dir.name.lower()
            
            # Select appropriate backside (team-specific if available, else default)
            if is_datacards:
                backside_to_use = team_backside_landscape if team_backside_landscape.exists() else default_backside_landscape
                orientation = "landscape"
            else:
                backside_to_use = team_backside_portrait if team_backside_portrait.exists() else default_backside_portrait
                orientation = "portrait"
            
            # Get all _front images
            front_images = list(type_dir.glob('*_front.jpg'))
            
            for front_image in front_images:
                # Check if corresponding _back exists
                back_image = front_image.parent / front_image.name.replace('_front.jpg', '_back.jpg')
                
                if not back_image.exists():
                    # Copy appropriate backside (team-specific or default)
                    shutil.copy2(backside_to_use, back_image)
                    print(f"  [OK] Added: {back_image.name}")
                    added_count += 1
    
    print(f"\n{'='*60}")
    print(f"Added {added_count} default backside image(s)")
    print(f"{'='*60}")

if __name__ == '__main__':
    add_default_backsides()
