#!/usr/bin/env python3
"""
Test Battleclade faction rules extraction (has a continuation page)
"""
import sys
import shutil
from pathlib import Path

# Add script directory to path
script_dir = Path(__file__).parent.parent / 'script'
sys.path.insert(0, str(script_dir))

from src.processors.team_identifier import TeamIdentifier
from src.processors.image_extractor import ImageExtractor
from src.models.card_type import CardType

def main():
    project_root = Path(__file__).parent.parent
    test_output = project_root / 'dev' / 'test_output' / 'battleclade'
    
    # Clean test output
    if test_output.exists():
        shutil.rmtree(test_output)
    test_output.mkdir(parents=True)
    
    # Initialize
    team_identifier = TeamIdentifier(Path('config/team-name-mapping.yaml'))
    extractor = ImageExtractor(dpi=150)
    
    # Test Battleclade
    pdf_path = project_root / 'processed' / 'battleclade' / 'battleclade-faction-rules.pdf'
    
    print(f"\n{'='*80}")
    print(f"Testing: {pdf_path.name}")
    print(f"{'='*80}\n")
    
    team = team_identifier.get_or_create_team('battleclade')
    cards = extractor.extract_from_pdf(pdf_path, team, CardType.FACTION_RULES)
    
    print(f"Extracted {len(cards)} cards:")
    print("-" * 80)
    
    for i, card in enumerate(cards, 1):
        print(f"\n{i}. {card.card_name}")
        print(f"   Front: {card.front_image.name if card.front_image else 'None'}")
        print(f"   Back:  {card.back_image.name if card.back_image else 'None'}")
    
    print(f"\n{'='*80}")
    print("Expected: 1 faction rule with back side + 1 marker guide = 2 cards")
    print(f"Got: {len(cards)} cards")
    
    # Check if first card has back
    if len(cards) > 0:
        first_card = cards[0]
        if first_card.card_name == 'noospheric-network' and first_card.back_image:
            print("✅ SUCCESS: Noospheric Network has back side (continuation page)")
        elif first_card.card_name == 'noospheric-network':
            print("⚠️  WARNING: Noospheric Network missing back side")
        else:
            print(f"⚠️  WARNING: First card is '{first_card.card_name}', expected 'noospheric-network'")

if __name__ == '__main__':
    main()
