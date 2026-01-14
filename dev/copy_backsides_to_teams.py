from pathlib import Path
from PIL import Image
import shutil
import os

backside_dir = Path("downloaded_backsides")
config_teams_dir = Path("config/teams")

# Get all team folders
team_folders = [f.name for f in config_teams_dir.iterdir() if f.is_dir()]
print(f"Found {len(team_folders)} team folders in config/teams")

# Get all backside images
backside_files = list(backside_dir.glob("*-backside-*.jpg"))
print(f"Found {len(backside_files)} backside images\n")

# Group by team name (extract team from filename)
backsides_by_team = {}
for file in backside_files:
    # Extract team name from filename (everything before "-backside-")
    team_part = file.stem.rsplit("-backside-", 1)[0]
    if team_part not in backsides_by_team:
        backsides_by_team[team_part] = []
    backsides_by_team[team_part].append(file)

print(f"Found backsides for {len(backsides_by_team)} teams\n")

# Match team names and copy files
copied_count = 0
skipped_count = 0
errors = []

for team_name, files in sorted(backsides_by_team.items()):
    # Try to find matching team folder
    matched_folder = None
    
    # Direct match
    if team_name in team_folders:
        matched_folder = team_name
    else:
        # Try fuzzy matching (handle typos, plurals, etc.)
        normalized_team = team_name.lower().replace("-", "").replace("_", "")
        for folder in team_folders:
            normalized_folder = folder.lower().replace("-", "").replace("_", "")
            if normalized_team == normalized_folder:
                matched_folder = folder
                break
        
        # Try partial matches
        if not matched_folder:
            for folder in team_folders:
                if team_name in folder or folder in team_name:
                    matched_folder = folder
                    break
    
    if not matched_folder:
        print(f"⚠️  No match for '{team_name}' - skipping {len(files)} files")
        skipped_count += len(files)
        continue
    
    # Create card-backside directory
    dest_dir = config_teams_dir / matched_folder / "card-backside"
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Process each file and determine orientation
    for file in files:
        try:
            # Get image dimensions
            with Image.open(file) as img:
                width, height = img.size
                aspect_ratio = width / height
                
                # Determine orientation
                if aspect_ratio > 1.2:
                    orientation = "landscape"
                elif aspect_ratio < 0.8:
                    orientation = "portrait"
                else:
                    # Close to square, check which dimension is larger
                    orientation = "landscape" if width > height else "portrait"
            
            # Generate destination filename
            dest_filename = f"card-backside-{orientation}.jpg"
            dest_path = dest_dir / dest_filename
            
            # Copy file
            shutil.copy2(file, dest_path)
            print(f"✅ {matched_folder:30s} {orientation:9s} ({width}x{height}, ratio: {aspect_ratio:.2f}) <- {file.name}")
            copied_count += 1
            
        except Exception as e:
            error_msg = f"Failed to process {file.name}: {e}"
            errors.append(error_msg)
            print(f"❌ {error_msg}")

print(f"\n{'='*80}")
print(f"✅ Copied {copied_count} backside images")
print(f"⚠️  Skipped {skipped_count} files (no team match)")
if errors:
    print(f"❌ {len(errors)} errors occurred")
    for error in errors:
        print(f"   - {error}")
