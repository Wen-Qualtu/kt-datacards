import os
import shutil
from pathlib import Path

backside_dir = Path("downloaded_backsides")

# Add your mappings here: filename → team-name
# Example: "-backside-12345678.jpg": "blades-of-khaine"
RENAME_MAPPING = {
    # Add entries like:
    # "-backside-93571914.jpg": "pathfinders",
    # "-backside-12345678.jpg": "blooded",
}

print(f"Renaming {len(RENAME_MAPPING)} files...")

renamed = []
failed = []

for old_filename, team_name in RENAME_MAPPING.items():
    old_path = backside_dir / old_filename
    
    if not old_path.exists():
        failed.append((old_filename, "File not found"))
        continue
    
    # Extract the hash part
    hash_part = old_filename.split('-backside-')[1]
    new_filename = f"{team_name}-backside-{hash_part}"
    new_path = backside_dir / new_filename
    
    try:
        shutil.move(str(old_path), str(new_path))
        renamed.append((old_filename, new_filename))
        print(f"✓ {old_filename} → {new_filename}")
    except Exception as e:
        failed.append((old_filename, str(e)))
        print(f"✗ {old_filename}: {e}")

print(f"\n{'='*80}")
print(f"✅ Successfully renamed {len(renamed)} files")
if failed:
    print(f"❌ Failed to rename {len(failed)} files:")
    for filename, error in failed:
        print(f"  - {filename}: {error}")
