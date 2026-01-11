#!/usr/bin/env python3
"""
Test extraction of faction rules to verify back side detection
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

def test_extraction(pdf_path: Path, test_output_dir: Path):
    """Test full extraction with back side detection"""
    print(f"\n{'='*80}")
    print(f"Testing extraction: {pdf_path.name}")
    print(f"{'='*80}\n")
    
    # Clean test output
    if test_output_dir.exists():
        shutil.rmtree(test_output_dir)
    test_output_dir.mkdir(parents=True)
    
    # Initialize
    team_identifier = TeamIdentifier(Path('config/team-name-mapping.yaml'))
    extractor = ImageExtractor(dpi=150)  # Lower DPI for faster testing
    
    # Extract team
    team_name = pdf_path.stem.replace('-faction-rules', '')
    team = team_identifier.get_or_create_team(team_name)
    
    # Extract datacards
    datacards = extractor.extract_from_pdf(pdf_path, team, CardType.FACTION_RULES)
    
    print(f"\nExtracted {len(datacards)} cards:")
    print("-" * 80)
    
    for i, card in enumerate(datacards, 1):
        print(f"\n{i}. Card: {card.card_name}")
        print(f"   Front: {card.front_image.name if card.front_image else 'None'}")
        print(f"   Back:  {card.back_image.name if card.back_image else 'None'}")
    
    return datacards

def main():
    project_root = Path(__file__).parent.parent
    test_output = project_root / 'dev' / 'test_output'
    
    # Test Deathwatch (should have 2 faction rules + 1 marker guide)
    deathwatch_pdf = project_root / 'processed' / 'deathwatch' / 'deathwatch-faction-rules.pdf'
    if deathwatch_pdf.exists():
        cards = test_extraction(deathwatch_pdf, test_output / 'deathwatch')
        
        print(f"\n{'='*80}")
        print("VALIDATION:")
        print("Expected: 2 faction rule cards + 1 marker guide = 3 cards total")
        print(f"Got: {len(cards)} cards")
        
        expected_names = ['veteran-astartes', 'special-issue-ammunition', 'markertoken-guide']
        actual_names = [c.card_name for c in cards]
        
        print(f"\nExpected names: {expected_names}")
        print(f"Actual names:   {actual_names}")
        
        if actual_names == expected_names:
            print("\n✅ SUCCESS: All faction rules extracted correctly!")
        else:
            print("\n❌ MISMATCH: Card names don't match expected")
    else:
        print(f"PDF not found: {deathwatch_pdf}")

if __name__ == '__main__':
    main()
