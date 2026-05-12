"""Analyze Spectre Squad PDF and extraction issues"""
import json
import fitz
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

def analyze_pdf():
    """Analyze the source PDF"""
    pdf_path = PROJECT_ROOT / "processed" / "spectre-squad" / "spectre-squad-datacards.pdf"
    
    print("=" * 60)
    print("SPECTRE SQUAD PDF ANALYSIS")
    print("=" * 60)
    
    doc = fitz.open(pdf_path)
    print(f"\nTotal pages: {len(doc)}")
    
    # Check first 3 pages
    for i in range(min(3, len(doc))):
        page = doc[i]
        text = page.get_text()
        
        print(f"\n--- Page {i} ---")
        print(f"Text length: {len(text)} chars")
        
        # Look for card type indicators
        if "NAME" in text and "HIT" in text and "WR" in text:
            print("✓ Looks like a DATACARD (has NAME/HIT/WR header)")
        
        # Show first 300 chars
        print(f"\nFirst 300 chars:")
        print(text[:300])
        print("...")
    
    doc.close()


def analyze_classification():
    """Analyze the classification results"""
    structure_file = PROJECT_ROOT / "layers" / "kt-app" / "classified" / "spectre-squad" / "structure.json"
    
    print("\n" + "=" * 60)
    print("CLASSIFICATION RESULTS")
    print("=" * 60)
    
    with open(structure_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Count each card type
    for card_type, cards in data.items():
        if isinstance(cards, list) and cards:
            print(f"\n{card_type}: {len(cards)} cards")
            for card in cards[:5]:  # Show first 5
                print(f"  - {card.get('name', 'N/A')}")
            if len(cards) > 5:
                print(f"  ... and {len(cards) - 5} more")


def analyze_extraction():
    """Analyze the team data extraction"""
    data_file = PROJECT_ROOT / "output_v3" / "spectre-squad" / "data" / "spectre-squad-team-data.json"
    
    print("\n" + "=" * 60)
    print("TEAM DATA EXTRACTION")
    print("=" * 60)
    
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\nTotal datacards extracted: {len(data.get('datacards', []))}")
    
    for operative in data.get('datacards', []):
        name = operative.get('name', 'N/A')
        apl = operative.get('apl', 'N/A')
        movement = operative.get('movement', 'N/A')
        weapons = len(operative.get('weapons', []))
        
        print(f"\n  {name}:")
        print(f"    APL: {apl}, Movement: {movement}, Weapons: {weapons}")


if __name__ == '__main__':
    analyze_pdf()
    analyze_classification()
    analyze_extraction()
