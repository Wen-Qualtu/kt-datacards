#!/usr/bin/env python3
"""Debug script to check what backsides are missing"""
import sys
from pathlib import Path

script_dir = Path(__file__).parent.parent / 'script'
sys.path.insert(0, str(script_dir))

from src.processors.backside_processor import BacksideProcessor
from src.models.team import Team
from src.models.card_type import CardType
from src.models.datacard import Datacard

def check_backsides():
    """Check which faction rules need backsides"""
    output_dir = Path('output')
    backside_processor = BacksideProcessor(Path('config/card-backside'))
    
    # Scan faction-rules folders
    datacards_needing_backs = []
    
    for team_dir in output_dir.iterdir():
        if not team_dir.is_dir():
            continue
        
        faction_rules_dir = team_dir / 'faction-rules'
        if not faction_rules_dir.exists():
            continue
        
        print(f"\nChecking {team_dir.name}/faction-rules:")
        print("-" * 60)
        
        # Find all front images without backs
        for front_img in faction_rules_dir.glob('*_front.jpg'):
            card_name = front_img.stem.replace('_front', '')
            back_img = faction_rules_dir / f"{card_name}_back.jpg"
            
            if not back_img.exists():
                print(f"  ❌ Missing back: {card_name}")
                
                # Create datacard object
                team = Team(name=team_dir.name)
                datacard = Datacard(
                    source_pdf=None,
                    team=team,
                    card_type=CardType.FACTION_RULES,
                    card_name=card_name
                )
                datacard.front_image = front_img
                datacards_needing_backs.append(datacard)
            else:
                print(f"  ✓ Has back: {card_name}")
    
    print(f"\n{'='*60}")
    print(f"Total cards needing backsides: {len(datacards_needing_backs)}")
    
    if datacards_needing_backs:
        print("\nAdding backsides...")
        added = backside_processor.add_backsides(datacards_needing_backs)
        print(f"✅ Added {added} backsides")

if __name__ == '__main__':
    check_backsides()
