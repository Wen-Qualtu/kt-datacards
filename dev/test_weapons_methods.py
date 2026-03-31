"""
Compare extraction methods specifically for weapons table.
"""

import fitz
from pathlib import Path

def test_weapons_extraction(pdf_path: Path):
    """Test different methods for extracting weapon table."""
    print(f"\n{'='*80}")
    print(f"WEAPON EXTRACTION TEST: {pdf_path.name}")
    print(f"{'='*80}\n")
    
    doc = fitz.open(pdf_path)
    page = doc[0]
    rect = page.rect
    
    # Method 1: Current approach - Dict blocks
    print("METHOD 1: Dict Blocks (Current)")
    print("-" * 80)
    text_dict = page.get_text("dict")
    weapon_blocks = []
    for i, block in enumerate(text_dict["blocks"]):
        if block.get("type") == 0:
            bbox = block["bbox"]
            y = bbox[1]
            # Weapon region: y between 34-75
            if 34 <= y <= 75:
                lines = []
                for line in block.get("lines", []):
                    line_text = "".join([span["text"] for span in line["spans"]])
                    lines.append(line_text)
                text = "\n".join(lines)
                weapon_blocks.append((i, bbox, text))
                print(f"Block {i} [y={int(y)}]: {repr(text[:80])}")
    
    # Method 2: Blocks list (simpler)
    print("\nMETHOD 2: Blocks List")
    print("-" * 80)
    blocks = page.get_text("blocks")
    for i, block in enumerate(blocks):
        x0, y0, x1, y1, text, block_no, block_type = block
        if 34 <= y0 <= 75:
            print(f"Block {i} [y={int(y0)}]: {repr(text[:80])}")
    
    # Method 3: Clip region
    print("\nMETHOD 3: Clip Region")
    print("-" * 80)
    weapons_region = fitz.Rect(0, 34, rect.width, 75)
    weapons_text = page.get_text(clip=weapons_region)
    print(repr(weapons_text[:400]))
    
    # Method 4: Clip + Blocks
    print("\nMETHOD 4: Clip + Blocks")
    print("-" * 80)
    weapons_blocks_clipped = page.get_text("blocks", clip=weapons_region)
    for i, block in enumerate(weapons_blocks_clipped):
        x0, y0, x1, y1, text, block_no, block_type = block
        print(f"Block {i}: {repr(text[:80])}")
    
    doc.close()


def test_stats_extraction(pdf_path: Path):
    """Test different methods for extracting stats box."""
    print(f"\n{'='*80}")
    print(f"STATS EXTRACTION TEST: {pdf_path.name}")
    print(f"{'='*80}\n")
    
    doc = fitz.open(pdf_path)
    page = doc[0]
    rect = page.rect
    
    # Method 1: Current - look for blocks in top-right
    print("METHOD 1: Top-Right Blocks (Current)")
    print("-" * 80)
    blocks = page.get_text("blocks")
    for i, block in enumerate(blocks):
        x0, y0, x1,y1, text, block_no, block_type = block
        if x0 > rect.width * 0.6 and y0 < 35:
            print(f"Block {i} [x={int(x0)}, y={int(y0)}]: {repr(text)}")
    
    # Method 2: Clip region
    print("\nMETHOD 2: Clip Stats Region")
    print("-" * 80)
    stats_region = fitz.Rect(rect.width * 0.65, 0, rect.width, 35)
    stats_text = page.get_text(clip=stats_region)
    print(repr(stats_text))
    
    # Parse the stats
    lines = stats_text.strip().split('\n')
    print(f"\nStats lines:")
    for i, line in enumerate(lines):
        print(f"  {i}: {repr(line)}")
    
    doc.close()


if __name__ == "__main__":
    # Test cards
    test_cards = [
        "layers/warcom/extracted/ratlings/cards/ratlings_page01_card2_landscape.pdf",  # RATLING BOMBER (front)
        "layers/warcom/extracted/kommandos/cards/kommandos_page01_card1_landscape.pdf",  # KOMMANDO
    ]
    
    for card_path_str in test_cards:
        card_path = Path(card_path_str)
        if card_path.exists():
            test_weapons_extraction(card_path)
            test_stats_extraction(card_path)
        else:
            print(f"Not found: {card_path}")
