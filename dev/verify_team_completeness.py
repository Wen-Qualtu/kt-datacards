#!/usr/bin/env python3
"""
Verify that all teams in output folder have complete card sets
"""
from pathlib import Path
from collections import defaultdict

def count_cards_in_folder(folder: Path) -> int:
    """Count unique cards (not counting front/back separately)"""
    if not folder.exists():
        return 0
    
    # Get all image files
    images = list(folder.glob("*.jpg")) + list(folder.glob("*.png"))
    
    # Count unique card names (strip _front/_back)
    card_names = set()
    for img in images:
        name = img.stem
        # Remove _front or _back suffix
        if name.endswith('_front') or name.endswith('_back'):
            name = name.rsplit('_', 1)[0]
        card_names.add(name)
    
    return len(card_names)

def verify_teams(output_dir: Path):
    """Verify all teams have expected card counts"""
    
    expected = {
        'equipment': 4,
        'strategy-ploys': 4,
        'firefight-ploys': 4,
        'operatives': 1,
        'faction-rules': (1, None),  # At least 1, no max
        'datacards': (2, None),  # At least 2, no max
    }
    
    print("="*80)
    print("TEAM COMPLETENESS VERIFICATION")
    print("="*80)
    print()
    
    # Get all team directories
    team_dirs = [d for d in output_dir.iterdir() if d.is_dir()]
    team_dirs.sort()
    
    all_complete = True
    
    for team_dir in team_dirs:
        team_name = team_dir.name
        print(f"📁 {team_name.upper()}")
        print("-" * 60)
        
        team_issues = []
        card_counts = {}
        
        for card_type in ['datacards', 'equipment', 'faction-rules', 
                         'firefight-ploys', 'operatives', 'strategy-ploys']:
            folder = team_dir / card_type
            count = count_cards_in_folder(folder)
            card_counts[card_type] = count
            
            # Check against expected counts
            if card_type in expected:
                exp = expected[card_type]
                
                if isinstance(exp, tuple):
                    # Range check (min, max)
                    min_val, max_val = exp
                    if count < min_val:
                        team_issues.append(f"❌ {card_type}: {count} (expected at least {min_val})")
                    else:
                        print(f"  ✅ {card_type}: {count}")
                else:
                    # Exact count check
                    if count != exp:
                        team_issues.append(f"❌ {card_type}: {count} (expected {exp})")
                    else:
                        print(f"  ✅ {card_type}: {count}")
            else:
                print(f"  ℹ️  {card_type}: {count}")
        
        # Check for marker token guide specifically
        all_files = list(team_dir.rglob("*marker*"))
        marker_files = [f for f in all_files if f.suffix in ['.jpg', '.png']]
        has_marker = len(marker_files) > 0
        
        if has_marker:
            print(f"  ✅ marker-token-guide: found")
        else:
            team_issues.append(f"❌ marker-token-guide: NOT FOUND")
        
        if team_issues:
            print()
            print("  ISSUES:")
            for issue in team_issues:
                print(f"    {issue}")
            all_complete = False
        
        print()
    
    print("="*80)
    if all_complete:
        print("✅ ALL TEAMS COMPLETE!")
    else:
        print("⚠️  SOME TEAMS HAVE MISSING CARDS")
    print("="*80)

if __name__ == "__main__":
    output_dir = Path("output")
    verify_teams(output_dir)
