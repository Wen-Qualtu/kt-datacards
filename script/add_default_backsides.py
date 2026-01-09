import os
import shutil
from pathlib import Path

def add_default_backsides():
    """
    For all cards with only a _front image, copy the default backside image as _back.
    Checks for team-specific backside first, then falls back to common default.
    """
    output_dir = Path('output')
    default_backside = Path('input/default-backside.jpg')
    
    if not default_backside.exists():
        print(f"❌ Error: Default backside image not found at {default_backside}")
        print("Please save the default-backside.jpg image in the input folder.")
        return
    
    print(f"Using default backside: {default_backside}\n")
    
    added_count = 0
    
    # Walk through all team folders
    for team_dir in sorted(output_dir.iterdir()):
        if not team_dir.is_dir():
            continue
        
        team_name = team_dir.name
        
        # Check if team has its own default backside
        team_backside = Path(f'input/{team_name}/default-backside.jpg')
        backside_to_use = team_backside if team_backside.exists() else default_backside
        
        if team_backside.exists():
            print(f"Using team-specific backside for {team_name}\n")
        
        # Look for all card type folders
        for type_dir in team_dir.iterdir():
            if not type_dir.is_dir():
                continue
            
            print(f"Processing: {team_dir.name}/{type_dir.name}")
            
            # Get all _front images
            front_images = list(type_dir.glob('*_front.jpg'))
            
            for front_image in front_images:
                # Check if corresponding _back exists
                back_image = front_image.parent / front_image.name.replace('_front.jpg', '_back.jpg')
                
                if not back_image.exists():
                    # Copy appropriate backside (team-specific or default)
                    shutil.copy2(backside_to_use, back_image)
                    print(f"  ✓ Added: {back_image.name}")
                    added_count += 1
    
    print(f"\n{'='*60}")
    print(f"Added {added_count} default backside image(s)")
    print(f"{'='*60}")

if __name__ == '__main__':
    add_default_backsides()
