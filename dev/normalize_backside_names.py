import os
import shutil
from pathlib import Path

backside_dir = Path("downloaded_backsides")

# Normalize naming and handle special cases
RENAME_MAPPING = {
    # Normalize underscores to hyphens and fix casing
    "Angels_of_Death-backside-20587948.jpg": "angels-of-death-backside-20587948.jpg",
    "Farstalker_Kinband-backside-95440762.jpg": "farstalker-kinband-backside-95440762.jpg",
    "Gellerpox_Infected-backside-16693971.jpg": "gellerpox-infected-backside-16693971.jpg",
    "Hearthkyn_Salvager-backside-94004344.jpg": "hearthkyn-salvagers-backside-94004344.jpg",
    "Hernkyn_Yaegirs-backside-55264880.jpg": "hernkyn-yaegirs-backside-55264880.jpg",
    "Hierotek_Circle-backside-41774843.jpg": "hierotek-circle-backside-41774843.jpg",
    "Phobos_Strike_Team-backside-45247986.jpg": "phobos-strike-team-backside-45247986.jpg",
    "Tempestus_Aquilons-backside-32605976.jpg": "tempestus-aquilons-backside-32605976.jpg",
    "Vespids_Stingwing-backside-17093841.jpg": "vespid-stingwings-backside-17093841.jpg",
    "Wrecka_Krew-backside-01699793.jpg": "wrecka-krew-backside-01699793.jpg",
    
    # Special cases - generic backsides
    "Equipment-backside-55944968.jpg": "generic-equipment-backside-55944968.jpg",
    "Firefight_Ploys-backside-77647029.jpg": "generic-firefight-ploys-backside-77647029.jpg",
}

print(f"Normalizing {len(RENAME_MAPPING)} filenames...")

renamed = []
skipped = []

for old_filename, new_filename in RENAME_MAPPING.items():
    old_path = backside_dir / old_filename
    new_path = backside_dir / new_filename
    
    if not old_path.exists():
        skipped.append((old_filename, "File not found"))
        continue
    
    if new_path.exists():
        skipped.append((old_filename, f"Target already exists: {new_filename}"))
        continue
    
    try:
        shutil.move(str(old_path), str(new_path))
        renamed.append((old_filename, new_filename))
        print(f"✓ {old_filename} → {new_filename}")
    except Exception as e:
        print(f"✗ {old_filename}: {e}")

print(f"\n{'='*80}")
print(f"✅ Successfully renamed {len(renamed)} files")
if skipped:
    print(f"⚠️  Skipped {len(skipped)} files")

# Show summary
print(f"\nAll backside files are now consistently named!")
all_files = sorted([f.name for f in backside_dir.glob("*-backside-*.jpg")])
print(f"Total backside files: {len(all_files)}")
