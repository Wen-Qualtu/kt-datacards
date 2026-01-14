import os
from PIL import Image
import pytesseract
from pathlib import Path
import re
import shutil

# Known team names to match against
TEAM_NAMES = [
    "angels of death",
    "battleclade",
    "blades of khaine",
    "blooded",
    "brood brothers",
    "canoptek circle",
    "chaos cult",
    "corsair voidscarred",
    "death korps",
    "deathwatch",
    "elucidian starstriders",
    "exaction squad",
    "farstalker kinband",
    "fellgor ravagers",
    "gellerpox infected",
    "goremongers",
    "hand of the archon",
    "hearthkyn salvagers",
    "hernkyn yaegirs",
    "hierotek circle",
    "hunter clade",
    "imperial navy breachers",
    "inquisitorial agents",
    "kasrkin",
    "kommandos",
    "legionaries",
    "mandrakes",
    "nemesis claw",
    "novitiates",
    "pathfinders",
    "phobos strike team",
    "plague marines",
    "ratlings",
    "raveners",
    "sanctifiers",
    "scout squad",
    "tempestus aquilons",
    "vespid stingwings",
    "void dancer troupe",
    "warpcoven",
    "wolf scouts",
    "wrecka krew",
    "wyrmblade",
    "xv26 stealth battlesuits",
]

# Add some common variations
TEAM_VARIATIONS = {
    "aeldari aspect warriors": "blades of khaine",
    "aspect warriors": "blades of khaine",
    "genestealer cults": "brood brothers",
    "space marines": "phobos strike team",
    "astra militarum": "kasrkin",
    "adeptus mechanicus": "hunter clade",
    "drukhari": "hand of the archon",
    "necrons": "hierotek circle",
    "orks": "kommandos",
    "chaos space marines": "legionaries",
    "death guard": "plague marines",
    "thousand sons": "warpcoven",
    "aeldari": "corsair voidscarred",
    "t'au": "pathfinders",
}

backside_dir = Path("downloaded_backsides")
renamed = []
failed = []
unidentifiable = []

for filename in sorted(os.listdir(backside_dir)):
    if not filename.endswith('.jpg'):
        continue
    
    # Skip files that already have team names (from the download)
    if not filename.startswith('-backside-'):
        continue
    
    filepath = backside_dir / filename
    print(f"\nProcessing: {filename}")
    
    try:
        # Open image and run OCR
        img = Image.open(filepath)
        text = pytesseract.image_to_string(img)
        text_lower = text.lower()
        
        print(f"  Extracted text: {text[:200]}...")  # First 200 chars
        
        # Try to find team names in the text
        found_team = None
        
        # Check direct team name matches
        for team_name in TEAM_NAMES:
            if team_name in text_lower:
                found_team = team_name
                break
        
        # Check variations
        if not found_team:
            for variation, team_name in TEAM_VARIATIONS.items():
                if variation in text_lower:
                    found_team = team_name
                    break
        
        if found_team:
            # Create new filename
            safe_team = found_team.replace(" ", "_").replace("/", "-")
            hash_part = filename.split('-backside-')[1]  # Keep the hash
            new_filename = f"{safe_team}-backside-{hash_part}"
            new_filepath = backside_dir / new_filename
            
            # Rename file
            shutil.move(str(filepath), str(new_filepath))
            renamed.append((filename, new_filename, found_team))
            print(f"  ✓ Identified as: {found_team}")
            print(f"  ✓ Renamed to: {new_filename}")
        else:
            unidentifiable.append(filename)
            print(f"  ✗ Could not identify team")
            
    except Exception as e:
        failed.append((filename, str(e)))
        print(f"  ✗ Error: {e}")

# Summary
print("\n" + "="*80)
print(f"✅ Successfully renamed {len(renamed)} files")
print(f"⚠️  Could not identify {len(unidentifiable)} files")
print(f"❌ Failed to process {len(failed)} files")

if renamed:
    print("\nRenamed files:")
    for old, new, team in renamed:
        print(f"  {old}")
        print(f"    → {new} ({team})")

if failed:
    print("\nFailed:")
    for filename, error in failed:
        print(f"  - {filename}: {error}")

print(f"\nUnidentifiable files remain in: {backside_dir}/")
