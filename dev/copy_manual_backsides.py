from pathlib import Path
from PIL import Image
import shutil

backside_dir = Path("downloaded_backsides")
config_teams_dir = Path("config/teams")

# Manual mappings for mismatched names
MANUAL_MAPPINGS = {
    "battle-suits-ploys": "xv26-stealth-battlesuits",
    "gallerpox-infected": "gellerpox-infected",
    "gormongers": "goremongers",
    "ravaners": "raveners",
    "vespid-stingwings": "vespids-stingwing",
}

copied_count = 0

for original_name, correct_folder in MANUAL_MAPPINGS.items():
    # Find files for this team
    pattern = f"{original_name}-backside-*.jpg"
    files = list(backside_dir.glob(pattern))
    
    if not files:
        print(f"⚠️  No files found for '{original_name}'")
        continue
    
    # Create destination directory
    dest_dir = config_teams_dir / correct_folder / "card-backside"
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Process each file
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
                    orientation = "landscape" if width > height else "portrait"
            
            # Generate destination filename
            dest_filename = f"card-backside-{orientation}.jpg"
            dest_path = dest_dir / dest_filename
            
            # Copy file
            shutil.copy2(file, dest_path)
            print(f"✅ {correct_folder:30s} {orientation:9s} ({width}x{height}, ratio: {aspect_ratio:.2f}) <- {file.name}")
            copied_count += 1
            
        except Exception as e:
            print(f"❌ Failed to process {file.name}: {e}")

print(f"\n{'='*80}")
print(f"✅ Copied {copied_count} manually mapped backside images")
