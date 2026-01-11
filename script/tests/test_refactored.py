#!/usr/bin/env python3
"""
Test script to validate the refactored code
"""
import sys
from pathlib import Path

# Change to project root and add script to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'script'))

import os
os.chdir(project_root)

from src.models.team import Team
from src.models.card_type import CardType
from src.models.datacard import Datacard
from src.processors.team_identifier import TeamIdentifier
from src.processors.pdf_processor import PDFProcessor
from src.utils.logger import setup_logger


def test_models():
    """Test model classes"""
    print("\n=== Testing Models ===")
    
    # Test Team
    team = Team(name="kasrkin", aliases=["kasrkins", "astra militarum kasrkin"])
    print(f"Team: {team.name}")
    print(f"  Aliases: {team.aliases}")
    print(f"  Matches 'kasrkins': {team.matches('kasrkins')}")
    print(f"  Processed path: {team.get_processed_path()}")
    print(f"  Output path: {team.get_output_path()}")
    
    # Test CardType
    print(f"\nCardType:")
    for card_type in CardType:
        print(f"  {card_type.value}")
    print(f"  from_string('datacards'): {CardType.from_string('datacards')}")
    print(f"  from_string('strategy ploy'): {CardType.from_string('strategy ploy')}")
    
    # Test Datacard
    datacard = Datacard(
        source_pdf=Path("input/processed/kasrkin/kasrkin-datacards.pdf"),
        team=team,
        card_type=CardType.DATACARDS,
        card_name="kasrkin-trooper"
    )
    print(f"\nDatacard: {datacard.card_name}")
    print(f"  Team: {datacard.team.name}")
    print(f"  Type: {datacard.card_type.value}")
    print(f"  Output folder: {datacard.get_output_folder()}")
    print(f"  Front filename: {datacard.get_expected_front_filename()}")
    print(f"  Back filename: {datacard.get_expected_back_filename()}")


def test_team_identifier():
    """Test TeamIdentifier"""
    print("\n=== Testing TeamIdentifier ===")
    
    config_path = Path("config/team-config.yaml")
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        return
    
    identifier = TeamIdentifier(config_path)
    
    print(f"Loaded {len(identifier.get_all_teams())} mapped teams")
    
    # Test identification (with get_or_create_team which creates on-the-fly)
    test_names = [
        "Kasrkin",
        "blooded",
        "Hearthkyn Salvager",
        "ASTRA MILITARUM KASRKIN"
    ]
    
    for name in test_names:
        team = identifier.get_or_create_team(name)
        if team:
            print(f"  '{name}' → {team.name}")
        else:
            print(f"  '{name}' → NOT FOUND")


def test_pdf_processor():
    """Test PDFProcessor"""
    print("\n=== Testing PDFProcessor ===")
    
    config_path = Path("config/team-config.yaml")
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        return
    
    identifier = TeamIdentifier(config_path)
    processor = PDFProcessor(identifier)
    
    # Test with a sample PDF if available
    processed_dir = Path("processed")
    if not processed_dir.exists():
        print(f"Processed directory not found: {processed_dir}")
        return
    
    # Find first PDF
    pdf_files = list(processed_dir.glob("*/*.pdf"))
    if not pdf_files:
        print("No PDF files found")
        return
    
    test_pdf = pdf_files[0]
    print(f"Testing with: {test_pdf}")
    
    try:
        team, card_type = processor.identify_pdf(test_pdf)
        print(f"  Team: {team.name if team else 'UNKNOWN'}")
        print(f"  Type: {card_type.value if card_type else 'UNKNOWN'}")
    except Exception as e:
        print(f"  Error: {e}")


def main():
    """Run tests"""
    setup_logger(name='test', level='INFO')
    
    print("=" * 60)
    print("Refactored Code Validation Tests")
    print("=" * 60)
    
    test_models()
    test_team_identifier()
    test_pdf_processor()
    
    print("\n" + "=" * 60)
    print("Tests Complete")
    print("=" * 60)


if __name__ == '__main__':
    main()
