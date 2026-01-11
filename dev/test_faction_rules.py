#!/usr/bin/env python3
"""
Quick test to extract faction rule names from processed PDFs
"""
import sys
from pathlib import Path

# Add script directory to path
script_dir = Path(__file__).parent.parent / 'script'
sys.path.insert(0, str(script_dir))

from src.processors.team_identifier import TeamIdentifier
from src.processors.image_extractor import ImageExtractor
from src.models.card_type import CardType
import fitz

def test_faction_rules(pdf_path: Path):
    """Test faction rule extraction"""
    print(f"\nTesting: {pdf_path.name}")
    print("=" * 80)
    
    try:
        doc = fitz.open(pdf_path)
        print(f"Total pages: {len(doc)}")
        
        # Initialize extractor
        team_identifier = TeamIdentifier(Path('config/team-name-mapping.yaml'))
        extractor = ImageExtractor(dpi=300)
        
        # Extract team from filename
        team_name = pdf_path.stem.replace('-faction-rules', '')
        team = team_identifier.get_or_create_team(team_name)
        
        print(f"Team: {team.name}")
        print(f"\nExtracting card names from each page:")
        print("-" * 80)
        
        for i in range(len(doc)):
            page = doc[i]
            card_name = extractor._extract_card_name(page, CardType.FACTION_RULES, team)
            
            # Also show top text snippets
            text = page.get_text()
            lines = [l.strip() for l in text.split('\n') if l.strip()][:10]
            
            print(f"\nPage {i+1}:")
            print(f"  Extracted name: {card_name}")
            print(f"  Top text lines:")
            for line in lines[:5]:
                if len(line) > 60:
                    line = line[:60] + "..."
                print(f"    - {line}")
        
        doc.close()
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

def main():
    project_root = Path(__file__).parent.parent
    processed_dir = project_root / 'processed'
    
    # Find all faction rules PDFs
    faction_pdfs = list(processed_dir.rglob('*faction-rules.pdf'))
    
    if not faction_pdfs:
        print("No faction rules PDFs found!")
        return
    
    print(f"Found {len(faction_pdfs)} faction rules PDFs")
    
    for pdf in faction_pdfs:
        test_faction_rules(pdf)
        print("\n")

if __name__ == '__main__':
    main()
