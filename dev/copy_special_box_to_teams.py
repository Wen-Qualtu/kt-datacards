import shutil
from pathlib import Path

# Teams that use the special 4-texture box
SPECIAL_BOX_TEAMS = [
    "wolf-scouts",
    "xv26-stealth-battlesuits"
]

source_obj = Path("config/defaults/box/card-box-4texture.obj")
if not source_obj.exists():
    print(f"❌ Source file not found: {source_obj}")
    exit(1)

print(f"Copying special 4-texture box to {len(SPECIAL_BOX_TEAMS)} teams...")
print(f"Source: {source_obj}")
print()

for team_name in SPECIAL_BOX_TEAMS:
    dest_dir = Path(f"config/teams/{team_name}/box")
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    dest_file = dest_dir / "card-box.obj"
    
    try:
        shutil.copy2(source_obj, dest_file)
        print(f"✅ {team_name}: Copied to {dest_file}")
    except Exception as e:
        print(f"❌ {team_name}: Failed - {e}")

print()
print("Done! These teams will now use the 4-texture box model.")
