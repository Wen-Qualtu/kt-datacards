from pathlib import Path
import shutil

config_teams_dir = Path("config/teams")

# Get all team folders
team_folders = [f for f in config_teams_dir.iterdir() if f.is_dir()]
print(f"Found {len(team_folders)} team folders\n")

renamed_count = 0
errors = []

for team_folder in sorted(team_folders):
    team_name = team_folder.name
    backside_dir = team_folder / "card-backside"
    
    if not backside_dir.exists():
        continue
    
    # Rename each orientation
    for orientation in ['landscape', 'portrait']:
        old_name = f"card-backside-{orientation}.jpg"
        new_name = f"{team_name}-backside-{orientation}.jpg"
        
        old_path = backside_dir / old_name
        new_path = backside_dir / new_name
        
        if old_path.exists():
            try:
                shutil.move(str(old_path), str(new_path))
                print(f"✅ {team_name:30s} {orientation:9s}: {old_name} → {new_name}")
                renamed_count += 1
            except Exception as e:
                error_msg = f"{team_name} {orientation}: {e}"
                errors.append(error_msg)
                print(f"❌ {error_msg}")

print(f"\n{'='*80}")
print(f"✅ Renamed {renamed_count} backside files")
if errors:
    print(f"❌ {len(errors)} errors occurred")
    for error in errors:
        print(f"   - {error}")
