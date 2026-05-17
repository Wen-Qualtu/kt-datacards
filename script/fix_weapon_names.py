"""
One-time script to fix weapon names in output/{team}/statlines/roster.json files.
Removes control characters and extracts actual weapon names from special_rules.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"


def clean_weapon_name(weapon: dict) -> dict:
    """Clean control characters from weapon name and special_rules."""
    # Clean control characters from name
    clean_name = re.sub(r'[\x00-\x1f]+', '', weapon.get("name", "")).strip()
    sr = weapon.get("special_rules", "")
    
    # If cleaned name is empty or very short, extract from special_rules
    if not clean_name or len(clean_name) <= 1 or weapon.get("name") in ['—', '-']:
        if sr:
            # Clean control characters first
            sr = re.sub(r'[\x00-\x1f]+', '', sr).strip()
            
            # Extract weapon name from the text
            # Pattern: weapon name is before common special rule keywords
            # Keywords that indicate start of special rules: Range, Piercing, Saturate, etc.
            match = re.match(r'^(.+?)\s+(Range\s|Piercing\s|Saturate|Torrent|Ceaseless|Lethal|Balanced|Brutal|Rending|Hot|Massive|Stun|Indirect|Silent|MW\s|AP\s|Unwieldy|Heavy|Relentless)', sr)
            if match:
                # Found a keyword - text before it is the weapon name
                clean_name = match.group(1).strip()
                # Everything from the keyword onwards is special rules
                sr = sr[len(match.group(1)):].strip()
            else:
                # No keyword found - check if ends with " - " or just "-"
                if sr.endswith(' -') or sr == '-':
                    # The whole thing minus the dash is the name, no special rules
                    clean_name = sr.rstrip(' -').strip()
                    sr = ""
                else:
                    # Entire text is the weapon name, no special rules
                    clean_name = sr
                    sr = ""
    
    # Clean control characters from special_rules if still present
    if sr:
        sr = re.sub(r'[\x00-\x1f]+', '', sr).strip()
    
    # Update weapon dict
    weapon["name"] = clean_name if clean_name else weapon.get("name", "")
    if sr and sr not in ['-', '']:
        weapon["special_rules"] = sr
    elif "special_rules" in weapon and (not sr or sr == '-'):
        del weapon["special_rules"]
    
    return weapon


def fix_roster_file(roster_path: Path) -> int:
    """Fix weapon names in a single roster file. Returns number of weapons fixed."""
    with open(roster_path, 'r', encoding='utf-8') as f:
        roster = json.load(f)
    
    fixed_count = 0
    for operative in roster.get("operatives", []):
        for weapon in operative.get("weapons", []):
            old_name = weapon.get("name", "")
            weapon = clean_weapon_name(weapon)
            if weapon.get("name") != old_name:
                fixed_count += 1
    
    # Write back
    with open(roster_path, 'w', encoding='utf-8') as f:
        json.dump(roster, f, indent=2, ensure_ascii=False)
    
    return fixed_count


def main():
    """Fix all roster files in output/{team}/statlines/."""
    total_teams = 0
    total_fixed = 0
    
    for team_dir in sorted(OUTPUT_DIR.iterdir()):
        if not team_dir.is_dir():
            continue
        
        roster_path = team_dir / "statlines" / "roster.json"
        if not roster_path.exists():
            continue
        
        try:
            fixed = fix_roster_file(roster_path)
            if fixed > 0:
                print(f"  {team_dir.name:30s} {fixed:3d} weapons fixed")
                total_fixed += fixed
            total_teams += 1
        except Exception as e:
            print(f"ERROR {team_dir.name}: {e}")
    
    print(f"\nDone: {total_teams} teams, {total_fixed} weapons fixed")


if __name__ == "__main__":
    main()
