"""
Compare output from new pipeline (output/) vs old pipeline (output_v2/)
to verify all cards are present in both.
"""

from pathlib import Path
from collections import defaultdict

def get_card_files(base_dir: Path, team: str) -> set:
    """Get set of card filenames for a team (without -front/-back suffix)."""
    # Try flat structure first (new output: output/{team}/cards/)
    cards_dir = base_dir / team / 'cards'
    if not cards_dir.exists():
        # Try nested structure (old output: output_v2/{faction}/{team}/)
        for faction in ['chaos', 'imperium', 'xenos']:
            cards_dir = base_dir / faction / team
            if cards_dir.exists():
                break
        else:
            return set()
    
    cards = set()
    # Look for both PNG and JPG files
    for pattern in ['*.png', '*.jpg']:
        for file in cards_dir.rglob(pattern):
            # Skip if inside tts folders
            if 'tts' in file.parts:
                continue
            # Remove -front/-back, _front/_back and extension to get base card name
            name = file.stem
            if name.endswith('-front') or name.endswith('-back'):
                name = name.rsplit('-', 1)[0]
            elif name.endswith('_front') or name.endswith('_back'):
                name = name.rsplit('_', 1)[0]
            cards.add(name)
    
    return cards

def main():
    output_new = Path('output')
    output_old = Path('output_v2')
    
    # Get all teams from new output (flat structure)
    teams_new = {d.name for d in output_new.iterdir() if d.is_dir()}
    
    # Get all teams from old output (nested under factions)
    teams_old = set()
    for faction_dir in output_old.iterdir():
        if faction_dir.is_dir() and faction_dir.name in ['chaos', 'imperium', 'xenos']:
            for team_dir in faction_dir.iterdir():
                if team_dir.is_dir():
                    teams_old.add(team_dir.name)
    
    print("=" * 80)
    print("OUTPUT COMPARISON: output/ vs output_v2/")
    print("=" * 80)
    print()
    
    # Teams only in one output
    only_new = teams_new - teams_old
    only_old = teams_old - teams_new
    common_teams = teams_new & teams_old
    
    if only_new:
        print(f"Teams ONLY in new output ({len(only_new)}):")
        for team in sorted(only_new):
            print(f"  + {team}")
        print()
    
    if only_old:
        print(f"Teams ONLY in old output ({len(only_old)}):")
        for team in sorted(only_old):
            print(f"  - {team}")
        print()
    
    print(f"Common teams: {len(common_teams)}")
    print()
    
    # Compare cards for common teams
    issues = []
    perfect_matches = []
    
    for team in sorted(common_teams):
        cards_new = get_card_files(output_new, team)
        cards_old = get_card_files(output_old, team)
        
        only_in_new = cards_new - cards_old
        only_in_old = cards_old - cards_new
        
        if only_in_new or only_in_old:
            issues.append({
                'team': team,
                'only_new': only_in_new,
                'only_old': only_in_old,
                'count_new': len(cards_new),
                'count_old': len(cards_old)
            })
        else:
            perfect_matches.append(team)
    
    # Show summary
    print("=" * 80)
    print(f"Perfect matches: {len(perfect_matches)} teams")
    if issues:
        print(f"Differences found: {len(issues)} teams")
    print("=" * 80)
    print()
    
    # Show detailed differences
    if issues:
        print("DETAILED DIFFERENCES:")
        print("=" * 80)
        for issue in issues:
            print()
            print(f"Team: {issue['team']}")
            print(f"  New: {issue['count_new']} cards | Old: {issue['count_old']} cards")
            
            if issue['only_new']:
                print(f"  >> ONLY in NEW output ({len(issue['only_new'])}):")
                for card in sorted(issue['only_new']):
                    print(f"     + {card}")
            
            if issue['only_old']:
                print(f"  >> ONLY in OLD output ({len(issue['only_old'])}):")
                for card in sorted(issue['only_old']):
                    print(f"     - {card}")
        print()
        print("=" * 80)
        print()
        
        # Summary of difference patterns
        print("SUMMARY OF CHANGES:")
        print("=" * 80)
        total_only_new = sum(len(issue['only_new']) for issue in issues)
        total_only_old = sum(len(issue['only_old']) for issue in issues)
        print(f"Total cards ONLY in new: {total_only_new}")
        print(f"Total cards ONLY in old: {total_only_old}")
        print()
    
    # Final summary
    print()
    print("SUMMARY:")
    print(f"  Teams in new: {len(teams_new)}")
    print(f"  Teams in old: {len(teams_old)}")
    print(f"  Perfect matches: {len(perfect_matches)}")
    print(f"  Teams with differences: {len(issues)}")
    
    if not only_new and not only_old and not issues:
        print()
        print("ALL TEAMS AND CARDS MATCH PERFECTLY!")
    else:
        print()
        print("Differences detected - review above")

if __name__ == '__main__':
    main()
