"""
Compare roster.json files between output/ and output_v2/ to verify identical extraction.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
OUTPUT_V2_DIR = ROOT / "output_v2"
TEAM_CONFIG_PATH = ROOT / "config" / "team-config.yaml"

import yaml


def get_team_faction(team: str) -> str:
    """Get faction for a team from team-config.yaml"""
    with open(TEAM_CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    teams = config.get("teams", {})
    if team in teams:
        return teams[team].get("faction")
    return None


def compare_operative(op1: dict, op2: dict, team: str, path: str) -> list[str]:
    """Compare two operative dictionaries. Returns list of differences."""
    diffs = []
    
    # Compare basic fields
    for field in ["name", "apl", "movement", "save", "wounds"]:
        if op1.get(field) != op2.get(field):
            diffs.append(f"  {op1.get('name')}: {field} differs - output: {op1.get(field)} vs output_v2: {op2.get(field)}")
    
    # Compare weapons
    weapons1 = op1.get("weapons", [])
    weapons2 = op2.get("weapons", [])
    
    if len(weapons1) != len(weapons2):
        diffs.append(f"  {op1.get('name')}: weapon count differs - output: {len(weapons1)} vs output_v2: {len(weapons2)}")
    else:
        for i, (w1, w2) in enumerate(zip(weapons1, weapons2)):
            for field in ["name", "attacks", "hit", "damage"]:
                if w1.get(field) != w2.get(field):
                    diffs.append(f"  {op1.get('name')} weapon {i}: {field} differs - output: {w1.get(field)} vs output_v2: {w2.get(field)}")
            
            # Special case for special_rules (can be None or missing)
            sr1 = w1.get("special_rules")
            sr2 = w2.get("special_rules")
            if sr1 != sr2:
                diffs.append(f"  {op1.get('name')} weapon {i} ({w1.get('name')}): special_rules differs - output: '{sr1}' vs output_v2: '{sr2}'")
    
    return diffs


def compare_team(team: str) -> tuple[bool, list[str]]:
    """Compare roster.json for a team. Returns (is_identical, differences)."""
    # Get paths
    old_path = OUTPUT_DIR / team / "statlines" / "roster.json"
    
    faction = get_team_faction(team)
    if not faction:
        return False, [f"Team {team} not found in team-config.yaml"]
    
    new_path = OUTPUT_V2_DIR / faction / team / "statlines" / "roster.json"
    
    if not old_path.exists():
        return False, [f"Missing: {old_path}"]
    if not new_path.exists():
        return False, [f"Missing: {new_path}"]
    
    # Load both rosters
    with open(old_path, encoding="utf-8") as f:
        old_roster = json.load(f)
    with open(new_path, encoding="utf-8") as f:
        new_roster = json.load(f)
    
    diffs = []
    
    # Compare operative count
    old_ops = old_roster.get("operatives", [])
    new_ops = new_roster.get("operatives", [])
    
    if len(old_ops) != len(new_ops):
        diffs.append(f"Operative count differs: output: {len(old_ops)} vs output_v2: {len(new_ops)}")
        return False, diffs
    
    # Compare each operative
    for op1, op2 in zip(old_ops, new_ops):
        op_diffs = compare_operative(op1, op2, team, str(old_path))
        diffs.extend(op_diffs)
    
    return len(diffs) == 0, diffs


def main():
    """Compare all teams."""
    print("Comparing roster.json files between output/ and output_v2/\n")
    
    identical_teams = []
    different_teams = []
    
    # Get all teams from output/
    teams = sorted([d.name for d in OUTPUT_DIR.iterdir() if d.is_dir() and (d / "statlines" / "roster.json").exists()])
    
    for team in teams:
        is_identical, diffs = compare_team(team)
        
        if is_identical:
            identical_teams.append(team)
            print(f"OK {team:30s} IDENTICAL")
        else:
            different_teams.append((team, diffs))
            print(f"!! {team:30s} DIFFERENCES FOUND")
            for diff in diffs[:5]:  # Show first 5 differences
                print(f"    {diff}")
            if len(diffs) > 5:
                print(f"    ... and {len(diffs) - 5} more differences")
    
    print(f"\n{'='*80}")
    print(f"Summary: {len(identical_teams)} identical, {len(different_teams)} different")
    
    if different_teams:
        print(f"\nTeams with differences:")
        for team, diffs in different_teams:
            print(f"  - {team} ({len(diffs)} differences)")


if __name__ == "__main__":
    main()
