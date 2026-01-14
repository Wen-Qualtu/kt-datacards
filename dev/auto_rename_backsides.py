import os
import shutil
from pathlib import Path

backside_dir = Path("downloaded_backsides")

# Based on the download order and context, here are my best guesses
# Files downloaded consecutively from the same bag likely belong to the same team
RENAME_MAPPING = {
    # Hernkyn Yaegirs group
    "-backside-13961942.jpg": "hernkyn-yaegirs",
    
    # Blooded group
    "-backside-58614289.jpg": "blooded",
    "-backside-27360823.jpg": "blooded",
    "-backside-33624645.jpg": "blooded",
    "-backside-75561919.jpg": "blooded",
    "-backside-32000723.jpg": "blooded",
    "-backside-47945938.jpg": "blooded",
    "-backside-98498655.jpg": "blooded",
    "-backside-86905036.jpg": "blooded",
    
    # Brood Brothers group
    "-backside-66770345.jpg": "brood-brothers",
    "-backside-85768911.jpg": "brood-brothers",
    "-backside-50527675.jpg": "brood-brothers",
    "-backside-83838110.jpg": "brood-brothers",
    "-backside-87754024.jpg": "brood-brothers",
    "-backside-35010261.jpg": "brood-brothers",
    "-backside-48688498.jpg": "brood-brothers",
    "-backside-64527299.jpg": "brood-brothers",
    "-backside-22663906.jpg": "brood-brothers",
    "-backside-61926217.jpg": "brood-brothers",
    
    # Scout Squad group
    "-backside-58720455.jpg": "scout-squad",
    "-backside-93409633.jpg": "scout-squad",
    "-backside-40874151.jpg": "scout-squad",
    "-backside-10293362.jpg": "scout-squad",
    "-backside-69320002.jpg": "scout-squad",
    
    # Mandrakes group
    "-backside-16198425.jpg": "mandrakes",
    "-backside-18906897.jpg": "mandrakes",
    "-backside-28462867.jpg": "mandrakes",
    "-backside-36425715.jpg": "mandrakes",
    "-backside-17350355.jpg": "mandrakes",
    
    # Kasrkin group
    "-backside-35239549.jpg": "kasrkin",
    "-backside-54904993.jpg": "kasrkin",
    "-backside-51361598.jpg": "kasrkin",
    "-backside-97063338.jpg": "kasrkin",
    "-backside-81509988.jpg": "kasrkin",
    "-backside-50285367.jpg": "kasrkin",
    "-backside-58628372.jpg": "kasrkin",
    
    # Hand of the Archon group
    "-backside-78988686.jpg": "hand-of-the-archon",
    "-backside-33614930.jpg": "hand-of-the-archon",
    "-backside-97852326.jpg": "hand-of-the-archon",
    "-backside-86124285.jpg": "hand-of-the-archon",
    
    # Hierotek Circle group
    "-backside-20038359.jpg": "hierotek-circle",
    "-backside-51626244.jpg": "hierotek-circle",
    "-backside-82164743.jpg": "hierotek-circle",
    "-backside-04639252.jpg": "hierotek-circle",
    "-backside-97161533.jpg": "hierotek-circle",
    "-backside-96628497.jpg": "hierotek-circle",
    
    # Exaction Squad group
    "-backside-31613289.jpg": "exaction-squad",
    "-backside-77280757.jpg": "exaction-squad",
    "-backside-37776791.jpg": "exaction-squad",
    "-backside-34775209.jpg": "exaction-squad",
    "-backside-47205727.jpg": "exaction-squad",
    "-backside-02221456.jpg": "exaction-squad",
    
    # Chaos Cult group
    "-backside-43970573.jpg": "chaos-cult",
    "-backside-34646384.jpg": "chaos-cult",
    "-backside-21428781.jpg": "chaos-cult",
    "-backside-63837715.jpg": "chaos-cult",
    "-backside-09703888.jpg": "chaos-cult",
    
    # Hunter Clade group
    "-backside-35933358.jpg": "hunter-clade",
    "-backside-31873488.jpg": "hunter-clade",
    "-backside-88903655.jpg": "hunter-clade",
    "-backside-20168606.jpg": "hunter-clade",
    "-backside-04624343.jpg": "hunter-clade",
    
    # Novitiates group
    "-backside-30301671.jpg": "novitiates",
    "-backside-72019678.jpg": "novitiates",
    "-backside-41068843.jpg": "novitiates",
    "-backside-18255041.jpg": "novitiates",
    "-backside-89896487.jpg": "novitiates",
    
    # Pathfinders group
    "-backside-46641492.jpg": "pathfinders",
    "-backside-71111028.jpg": "pathfinders",
    "-backside-69449975.jpg": "pathfinders",
    "-backside-93571914.jpg": "pathfinders",
    
    # Void-dancer Troupe group
    "-backside-74996903.jpg": "void-dancer-troupe",
    "-backside-74754323.jpg": "void-dancer-troupe",
    "-backside-03023790.jpg": "void-dancer-troupe",
    
    # Wyrmblade group (additional)
    "-backside-15548212.jpg": "wyrmblade",
    "-backside-88833167.jpg": "wyrmblade",
    "-backside-61378915.jpg": "wyrmblade",
    "-backside-84714331.jpg": "wyrmblade",
    "-backside-26585675.jpg": "wyrmblade",
    "-backside-70151361.jpg": "wyrmblade",
    "-backside-03156232.jpg": "wyrmblade",
    
    # Hearthkyn Salvagers group (additional)
    "-backside-78265062.jpg": "hearthkyn-salvagers",
    "-backside-68132992.jpg": "hearthkyn-salvagers",
    "-backside-30219723.jpg": "hearthkyn-salvagers",
    "-backside-35039929.jpg": "hearthkyn-salvagers",
    "-backside-61315448.jpg": "hearthkyn-salvagers",
    "-backside-08096968.jpg": "hearthkyn-salvagers",
    "-backside-16384445.jpg": "hearthkyn-salvagers",
    "-backside-24801957.jpg": "hearthkyn-salvagers",
    "-backside-09876384.jpg": "hearthkyn-salvagers",
    
    # Fellgor Ravagers group (additional)
    "-backside-90212386.jpg": "fellgor-ravagers",
    "-backside-83853731.jpg": "fellgor-ravagers",
    
    # Farstalker Kinband group (additional)
    "-backside-51659861.jpg": "farstalker-kinband",
    "-backside-79046188.jpg": "farstalker-kinband",
    "-backside-41655638.jpg": "farstalker-kinband",
    
    # Tempestus Aquilons group (additional)
    "-backside-88614663.jpg": "tempestus-aquilons",
    "-backside-18618625.jpg": "tempestus-aquilons",
    
    # Vespid Stingwings group (additional)
    "-backside-67516545.jpg": "vespid-stingwings",
    "-backside-36057220.jpg": "vespid-stingwings",
    "-backside-33575774.jpg": "vespid-stingwings",
    "-backside-28986392.jpg": "vespid-stingwings",
    "-backside-79874719.jpg": "vespid-stingwings",
    
    # Blades of Khaine group (additional)
    "-backside-24826949.jpg": "blades-of-khaine",
    "-backside-41863464.jpg": "blades-of-khaine",
    "-backside-37116116.jpg": "blades-of-khaine",
    "-backside-15654384.jpg": "blades-of-khaine",
    "-backside-61449963.jpg": "blades-of-khaine",
    "-backside-16226335.jpg": "blades-of-khaine",
    "-backside-36199510.jpg": "blades-of-khaine",
    
    # Inquisitorial Agents group (additional)
    "-backside-19748535.jpg": "inquisitorial-agents",
    
    # Elucidian Starstriders group (additional)
    "-backside-32673805.jpg": "elucidian-starstriders",
    "-backside-09317871.jpg": "elucidian-starstriders",
    "-backside-90211685.jpg": "elucidian-starstriders",
    "-backside-38589700.jpg": "elucidian-starstriders",
    "-backside-28501602.jpg": "elucidian-starstriders",
    
    # Angels of Death group (additional)
    "-backside-32139807.jpg": "angels-of-death",
    "-backside-93621053.jpg": "angels-of-death",
    "-backside-54202050.jpg": "angels-of-death",
    "-backside-84620949.jpg": "angels-of-death",
    
    # Phobos Strike Team group (additional)
    "-backside-31012557.jpg": "phobos-strike-team",
    "-backside-18802402.jpg": "phobos-strike-team",
    
    # Corsair Voidscarred group (additional)
    "-backside-59320216.jpg": "corsair-voidscarred",
    "-backside-70164574.jpg": "corsair-voidscarred",
    "-backside-10667897.jpg": "corsair-voidscarred",
    "-backside-49708709.jpg": "corsair-voidscarred",
    "-backside-03963710.jpg": "corsair-voidscarred",
    
    # Nemesis Claw group (additional)
    "-backside-41092693.jpg": "nemesis-claw",
    "-backside-72203969.jpg": "nemesis-claw",
    "-backside-44651658.jpg": "nemesis-claw",
    
    # Warpcoven group (additional)
    "-backside-10167198.jpg": "warpcoven",
    "-backside-30523837.jpg": "warpcoven",
    "-backside-36399834.jpg": "warpcoven",
    "-backside-10129497.jpg": "warpcoven",
    "-backside-91889147.jpg": "warpcoven",
    
    # Plague Marines group (additional)
    "-backside-19184438.jpg": "plague-marines",
    "-backside-26928560.jpg": "plague-marines",
    "-backside-77685849.jpg": "plague-marines",
    
    # Wrecka Krew group (additional)
    "-backside-50808205.jpg": "wrecka-krew",
    "-backside-63202367.jpg": "wrecka-krew",
    "-backside-98322611.jpg": "wrecka-krew",
    "-backside-27246208.jpg": "wrecka-krew",
    
    # Goremongers group (additional)
    "-backside-01217266.jpg": "goremongers",
    
    # Sanctifiers group (additional)
    "-backside-01871150.jpg": "sanctifiers",
    "-backside-07174927.jpg": "sanctifiers",
    "-backside-02553531.jpg": "sanctifiers",
    "-backside-03019130.jpg": "sanctifiers",
    "-backside-04274484.jpg": "sanctifiers",
    "-backside-58320949.jpg": "sanctifiers",
    "-backside-62475192.jpg": "sanctifiers",
    "-backside-38530664.jpg": "sanctifiers",
    "-backside-75773746.jpg": "sanctifiers",
    
    # Raveners group (additional)
    "-backside-50291207.jpg": "raveners",
    "-backside-70653992.jpg": "raveners",
    
    # Deathwatch group (additional)
    "-backside-23563770.jpg": "deathwatch",
    "-backside-33108649.jpg": "deathwatch",
    "-backside-68778657.jpg": "deathwatch",
    "-backside-96207824.jpg": "deathwatch",
    "-backside-10430417.jpg": "deathwatch",
    "-backside-11215747.jpg": "deathwatch",
    "-backside-41526861.jpg": "deathwatch",
    
    # Imperial Navy Breachers group (additional)
    "-backside-36627215.jpg": "imperial-navy-breachers",
    "-backside-47474789.jpg": "imperial-navy-breachers",
    "-backside-66273835.jpg": "imperial-navy-breachers",
    "-backside-32105318.jpg": "imperial-navy-breachers",
    "-backside-31384642.jpg": "imperial-navy-breachers",
    "-backside-03663120.jpg": "imperial-navy-breachers",
    
    # Legionaries group (additional)
    "-backside-24548998.jpg": "legionaries",
    "-backside-75474214.jpg": "legionaries",
    "-backside-70217637.jpg": "legionaries",
    
    # Canoptek Circle group (additional)
    "-backside-23870509.jpg": "canoptek-circle",
    "-backside-50388573.jpg": "canoptek-circle",
    "-backside-58815751.jpg": "canoptek-circle",
    "-backside-15993324.jpg": "canoptek-circle",
    "-backside-29066487.jpg": "canoptek-circle",
    "-backside-85881436.jpg": "canoptek-circle",
    "-backside-48250296.jpg": "canoptek-circle",
    
    # Battleclade group (additional)
    "-backside-05280152.jpg": "battleclade",
    
    # Ratlings group (additional)
    "-backside-49236246.jpg": "ratlings",
    "-backside-85245123.jpg": "ratlings",
    "-backside-70350648.jpg": "ratlings",
    "-backside-91314966.jpg": "ratlings",
}

print(f"Renaming {len(RENAME_MAPPING)} files based on download order analysis...")

renamed = []
skipped = []
failed = []

for old_filename, team_name in RENAME_MAPPING.items():
    old_path = backside_dir / old_filename
    
    if not old_path.exists():
        skipped.append((old_filename, "File not found (may already be renamed)"))
        continue
    
    # Extract the hash part
    hash_part = old_filename.split('-backside-')[1]
    new_filename = f"{team_name}-backside-{hash_part}"
    new_path = backside_dir / new_filename
    
    try:
        shutil.move(str(old_path), str(new_path))
        renamed.append((old_filename, new_filename, team_name))
        print(f"✓ {team_name}: {old_filename} → {new_filename}")
    except Exception as e:
        failed.append((old_filename, str(e)))
        print(f"✗ {old_filename}: {e}")

print(f"\n{'='*80}")
print(f"✅ Successfully renamed {len(renamed)} files")
print(f"⚠️  Skipped {len(skipped)} files (already renamed or not found)")
if failed:
    print(f"❌ Failed to rename {len(failed)} files:")
    for filename, error in failed:
        print(f"  - {filename}: {error}")
        
print(f"\nYou can now review the renamed files in {backside_dir}/ and fix any mistakes.")
