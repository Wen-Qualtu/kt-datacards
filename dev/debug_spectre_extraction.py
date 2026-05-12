"""Debug Spectre Squad extraction"""
import json
import fitz
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def _extract_name_from_blocks(blocks, page_width, page_height):
    """Extract operative name from blocks"""
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block["bbox"]
        if bbox[0] < page_width * 0.6 and bbox[1] < 15:
            text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")
            text = text.strip()
            if ',' in text or text.upper() in ['NAME', 'ATK', 'HIT', 'DMG', 'WR', 'NOTES:', 'NOTES']:
                continue
            if 'ACTIONS' in text.upper():
                continue
            if text.isupper() and 3 <= len(text) <= 50:
                # Clean up OCR artifacts
                name = re.sub(r'\d+["\']?\d+\+?$', '', text).strip()
                name = re.sub(r'\d{2,}["\']?\d+[+\-]?$', '', name).strip()
                name = name.rstrip('0123456789+"\'-').strip()
                if len(name) >= 3:
                    return name
    return None


def _extract_stats_from_blocks(blocks, page_width, page_height):
    """Extract stats from blocks"""
    stats = {"apl": None, "movement": None, "save": None, "wounds": None}
    
    # Try to find APL in top-left
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block["bbox"]
        if bbox[0] < page_width * 0.6 and bbox[1] < 15:
            text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")
            text = text.strip()
            if text and text[-1].isdigit():
                stats["apl"] = int(text[-1])
                break
    
    # Alternative APL location
    if stats["apl"] is None:
        for block in blocks:
            if block.get("type") != 0:
                continue
            bbox = block["bbox"]
            if bbox[0] > page_width * 0.65 and bbox[1] < page_height * 0.25:
                text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text += span.get("text", "")
                text = text.strip()
                if text.isdigit() and len(text) == 1:
                    stats["apl"] = int(text)
                    break
    
    # Extract stats from right side
    stats_text = ""
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block["bbox"]
        if bbox[0] > page_width * 0.65 and bbox[3] < page_height * 0.25:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    stats_text += span.get("text", "") + "|"
    
    move_match = re.search(r'(\d+)[″"\']', stats_text)
    if move_match:
        stats["movement"] = move_match.group(1) + "″"
    
    save_match = re.search(r'(\d+)\|?\+', stats_text)
    if save_match:
        stats["save"] = save_match.group(1) + "+"
    
    # Find wounds
    all_numbers = re.findall(r'\d+', stats_text)
    for num_str in all_numbers:
        num = int(num_str)
        if 7 <= num <= 30:  # Typical wounds range
            if stats["wounds"] is None:
                stats["wounds"] = num
    
    return stats

def debug_extraction():
    """Debug extraction for each operative"""
    # Load structure
    structure_file = PROJECT_ROOT / "layers" / "kt-app" / "classified" / "spectre-squad" / "structure.json"
    
    with open(structure_file, 'r', encoding='utf-8') as f:
        structure = json.load(f)
    
    print("=" * 60)
    print("DEBUGGING SPECTRE SQUAD EXTRACTION")
    print("=" * 60)
    
    datacards = structure.get("datacards", [])
    print(f"\nTotal datacards in structure: {len(datacards)}")
    
    for i, entity in enumerate(datacards):
        name = entity.get("name", "UNKNOWN")
        cards = entity.get("cards", [])
        
        print(f"\n--- {i+1}. {name} ---")
        
        if not cards:
            print("  [X] No cards found")
            continue
        
        # Find front page
        front_card = None
        for card in cards:
            if "front" in card:
                front_card = card
                break
        
        if not front_card:
            print("  [X] No front page found")
            continue
        
        front_path = PROJECT_ROOT / front_card["front"]
        if not front_path.exists():
            print(f"  [X] Front page missing: {front_path}")
            continue
        
        print(f"  [+] Front page: {front_card['front']}")
        
        # Open PDF and extract
        try:
            doc = fitz.open(front_path)
            page = doc[0]
            pw = page.rect.width
            ph = page.rect.height
            blocks = page.get_text("dict").get("blocks", [])
            
            # Try extraction
            extracted_name = _extract_name_from_blocks(blocks, pw, ph)
            stats = _extract_stats_from_blocks(blocks, pw, ph)
            
            print(f"  Extracted name: {extracted_name}")
            print(f"  APL: {stats.get('apl')}")
            print(f"  Movement: {stats.get('movement')}")
            print(f"  Save: {stats.get('save')}")
            print(f"  Wounds: {stats.get('wounds')}")
            
            if not extracted_name:
                print("  [!] Name extraction failed")
            
            if stats.get("wounds") is None:
                print("  [!] Wounds extraction failed - operative will be skipped!")
                
                # Show some text blocks for debugging
                print("\n  Text blocks (first 5):")
                for j, block in enumerate(blocks[:5]):
                    if block.get("type") == 0:
                        text = ""
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                text += span.get("text", "")
                        bbox = block["bbox"]
                        print(f"    Block {j}: '{text[:50]}...' at ({bbox[0]:.1f}, {bbox[1]:.1f})")
            
            doc.close()
            
        except Exception as e:
            print(f"  [X] Extraction error: {e}")

if __name__ == '__main__':
    debug_extraction()
