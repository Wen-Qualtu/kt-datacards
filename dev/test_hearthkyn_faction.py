#!/usr/bin/env python3
"""Test specific team faction rule extraction"""
import sys
from pathlib import Path

script_dir = Path(__file__).parent.parent / 'script'
sys.path.insert(0, str(script_dir))

from src.processors.team_identifier import TeamIdentifier
from src.processors.image_extractor import ImageExtractor
from src.models.card_type import CardType

# Initialize
team_identifier = TeamIdentifier(Path('config/team-name-mapping.yaml'))
extractor = ImageExtractor(dpi=300)

# Test hearthkyn-salvager
pdf_path = Path('processed/hearthkyn-salvager/hearthkyn-salvager-faction-rules.pdf')
team = team_identifier.get_or_create_team('hearthkyn-salvager')

print(f"Testing: {pdf_path.name}")
print(f"Team: {team.name}")
print("="*80)

datacards = extractor.extract_from_pdf(pdf_path, team, CardType.FACTION_RULES)

print(f"\nExtracted {len(datacards)} cards:")
for card in datacards:
    print(f"  - {card.card_name}")
    print(f"    Front: {card.front_image.name if card.front_image else 'None'}")
    print(f"    Back:  {card.back_image.name if card.back_image else 'None'}")
