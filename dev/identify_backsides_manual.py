import os
from PIL import Image
from pathlib import Path
import shutil

# Known team names
TEAM_NAMES = [
    "angels-of-death",
    "battleclade", 
    "blades-of-khaine",
    "blooded",
    "brood-brothers",
    "canoptek-circle",
    "chaos-cult",
    "corsair-voidscarred",
    "death-korps",
    "deathwatch",
    "elucidian-starstriders",
    "exaction-squad",
    "farstalker-kinband",
    "fellgor-ravagers",
    "gellerpox-infected",
    "goremongers",
    "hand-of-the-archon",
    "hearthkyn-salvagers",
    "hernkyn-yaegirs",
    "hierotek-circle",
    "hunter-clade",
    "imperial-navy-breachers",
    "inquisitorial-agents",
    "kasrkin",
    "kommandos",
    "legionaries",
    "mandrakes",
    "nemesis-claw",
    "novitiates",
    "pathfinders",
    "phobos-strike-team",
    "plague-marines",
    "ratlings",
    "raveners",
    "sanctifiers",
    "scout-squad",
    "tempestus-aquilons",
    "vespid-stingwings",
    "void-dancer-troupe",
    "warpcoven",
    "wolf-scouts",
    "wrecka-krew",
    "wyrmblade",
    "xv26-stealth-battlesuits",
]

backside_dir = Path("downloaded_backsides")
unidentified_files = []

# Find all unidentified files
for filename in sorted(os.listdir(backside_dir)):
    if filename.startswith('-backside-') and filename.endswith('.jpg'):
        unidentified_files.append(filename)

print(f"Found {len(unidentified_files)} unidentified backside images")
print("\nOpening images for manual inspection...")
print("="*80)
print("\nInstructions:")
print("1. Look at each image that opens")
print("2. If you can see a team name, type the team slug (e.g., 'blades-of-khaine')")
print("3. Type 'skip' if you can't identify it")
print("4. Type 'quit' to stop")
print("\nAvailable team names:")
for i, team in enumerate(TEAM_NAMES, 1):
    print(f"  {i:2}. {team}")
print("="*80)

renamed_count = 0

for filename in unidentified_files:
    filepath = backside_dir / filename
    
    try:
        # Open image for user to view
        img = Image.open(filepath)
        img.show()
        
        # Ask user for identification
        print(f"\n\nShowing: {filename}")
        response = input("Team name (or 'skip'/'quit'): ").strip().lower()
        
        if response == 'quit':
            print("\nStopping...")
            break
        elif response == 'skip' or response == '':
            print("  Skipped")
            continue
        elif response in TEAM_NAMES:
            # Rename the file
            hash_part = filename.split('-backside-')[1]
            new_filename = f"{response}-backside-{hash_part}"
            new_filepath = backside_dir / new_filename
            
            shutil.move(str(filepath), str(new_filepath))
            renamed_count += 1
            print(f"  ✓ Renamed to: {new_filename}")
        else:
            print(f"  ✗ Unknown team name: {response}")
            print("  Use one of the team names from the list above")
            
    except Exception as e:
        print(f"  ✗ Error: {e}")

print(f"\n{'='*80}")
print(f"✅ Renamed {renamed_count} files")
print(f"Remaining unidentified: {len(unidentified_files) - renamed_count}")
