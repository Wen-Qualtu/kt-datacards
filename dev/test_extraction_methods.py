"""
Test different text extraction methods on datacards to find the most reliable approach.
"""

import fitz
from pathlib import Path
import json

def test_all_methods(pdf_path: Path):
    """Test all available PyMuPDF text extraction methods."""
    doc = fitz.open(pdf_path)
    page = doc[0]
    
    print(f"\n{'='*80}")
    print(f"Testing: {pdf_path.name}")
    print(f"{'='*80}\n")
    
    # Method 1: Plain text
    print("=" * 80)
    print("METHOD 1: get_text() - Plain Text")
    print("=" * 80)
    text = page.get_text()
    print(text)
    print(f"\nLength: {len(text)} chars")
    
    # Method 2: Dict format (what we currently use)
    print("\n" + "=" * 80)
    print("METHOD 2: get_text('dict') - Structured Blocks")
    print("=" * 80)
    text_dict = page.get_text("dict")
    for i, block in enumerate(text_dict["blocks"]):
        if block.get("type") == 0:  # Text block
            bbox = block["bbox"]
            lines = []
            for line in block.get("lines", []):
                line_text = "".join([span["text"] for span in line["spans"]])
                lines.append(line_text)
            text = "\n".join(lines)
            print(f"\nBlock {i} [{int(bbox[0])},{int(bbox[1])}]: {repr(text[:100])}")
    
    # Method 3: Blocks (simpler than dict)
    print("\n" + "=" * 80)
    print("METHOD 3: get_text('blocks') - Block List")
    print("=" * 80)
    blocks = page.get_text("blocks")
    for i, block in enumerate(blocks):
        x0, y0, x1, y1, text, block_no, block_type = block
        print(f"\nBlock {i} [{int(x0)},{int(y0)}-{int(x1)},{int(y1)}]: {repr(text[:100])}")
    
    # Method 4: Words (most granular)
    print("\n" + "=" * 80)
    print("METHOD 4: get_text('words') - Individual Words")
    print("=" * 80)
    words = page.get_text("words")
    print(f"Total words: {len(words)}")
    for i, word in enumerate(words[:30]):  # First 30 words
        x0, y0, x1, y1, text, block_no, line_no, word_no = word
        print(f"Word {i} [{int(x0)},{int(y0)}]: {repr(text)}")
    
    # Method 5: HTML (preserves structure)
    print("\n" + "=" * 80)
    print("METHOD 5: get_text('html') - HTML Format")
    print("=" * 80)
    html = page.get_text("html")
    print(html[:2000])  # First 2000 chars
    
    # Method 6: Extract specific regions
    print("\n" + "=" * 80)
    print("METHOD 6: Clip Regions - Extract Specific Areas")
    print("=" * 80)
    
    # Page dimensions
    rect = page.rect
    print(f"Page size: {rect.width} x {rect.height}")
    
    # Define regions based on typical layout
    name_region = fitz.Rect(0, 0, rect.width * 0.65, 35)
    stats_region = fitz.Rect(rect.width * 0.65, 0, rect.width, 35)
    weapons_region = fitz.Rect(0, 35, rect.width, 75)
    abilities_region = fitz.Rect(0, 75, rect.width, rect.height)
    
    print("\nName Region (top-left):")
    print(page.get_text(clip=name_region))
    
    print("\nStats Region (top-right):")
    print(page.get_text(clip=stats_region))
    
    print("\nWeapons Region (middle):")
    print(page.get_text(clip=weapons_region))
    
    print("\nAbilities Region (bottom):")
    abilities_text = page.get_text(clip=abilities_region)
    print(abilities_text[:500])  # First 500 chars
    
    doc.close()


def compare_methods_for_stats(pdf_path: Path):
    """Focus on extracting stats box using different methods."""
    doc = fitz.open(pdf_path)
    page = doc[0]
    rect = page.rect
    
    print(f"\n{'='*80}")
    print(f"STATS BOX EXTRACTION COMPARISON: {pdf_path.name}")
    print(f"{'='*80}\n")
    
    stats_region = fitz.Rect(rect.width * 0.65, 0, rect.width, 35)
    
    # Method A: Clip region plain text
    print("Method A: Clip + Plain Text")
    print("-" * 40)
    stats_text = page.get_text(clip=stats_region)
    print(repr(stats_text))
    
    # Method B: Clip region + dict
    print("\nMethod B: Clip + Dict Blocks")
    print("-" * 40)
    stats_dict = page.get_text("dict", clip=stats_region)
    for block in stats_dict["blocks"]:
        if block.get("type") == 0:
            for line in block.get("lines", []):
                line_text = "".join([span["text"] for span in line["spans"]])
                print(f"  Line: {repr(line_text)}")
    
    # Method C: Words in region
    print("\nMethod C: Words in Stats Region")
    print("-" * 40)
    all_words = page.get_text("words")
    stats_words = [w for w in all_words if w[0] >= stats_region.x0 and w[1] >= stats_region.y0 
                   and w[2] <= stats_region.x1 and w[3] <= stats_region.y1]
    for word in stats_words:
        print(f"  [{int(word[0])},{int(word[1])}]: {repr(word[4])}")
    
    doc.close()


def compare_methods_for_weapons(pdf_path: Path):
    """Focus on extracting weapon table using different methods."""
    doc = fitz.open(pdf_path)
    page = doc[0]
    rect = page.rect
    
    print(f"\n{'='*80}")
    print(f"WEAPON TABLE EXTRACTION COMPARISON: {pdf_path.name}")
    print(f"{'='*80}\n")
    
    weapons_region = fitz.Rect(0, 35, rect.width, 75)
    
    # Method A: Clip region plain text
    print("Method A: Clip + Plain Text")
    print("-" * 40)
    weapons_text = page.get_text(clip=weapons_region)
    print(repr(weapons_text))
    
    # Method B: Clip region + blocks
    print("\nMethod B: Clip + Blocks")
    print("-" * 40)
    weapons_blocks = page.get_text("blocks", clip=weapons_region)
    for i, block in enumerate(weapons_blocks):
        print(f"Block {i} [{int(block[0])},{int(block[1])}]: {repr(block[4])}")
    
    # Method C: Dict with lines and spans
    print("\nMethod C: Clip + Dict (Lines/Spans)")
    print("-" * 40)
    weapons_dict = page.get_text("dict", clip=weapons_region)
    for block in weapons_dict["blocks"]:
        if block.get("type") == 0:
            print(f"Block bbox: {block['bbox']}")
            for line in block.get("lines", []):
                line_text = "".join([span["text"] for span in line["spans"]])
                print(f"  Line: {repr(line_text)}")
    
    doc.close()


if __name__ == "__main__":
    # Test on problematic cards
    test_cards = [
        Path("layers/warcom/extracted/ratlings/cards/ratlings_page01_card2_landscape.pdf"),  # RATLING BOMBER
        Path("layers/warcom/extracted/kommandos/cards/kommandos_page01_card1_landscape.pdf"),  # KOMMANDO BOSS NOB
        Path("layers/warcom/extracted/sanctifiers/cards/sanctifiers_page01_card1_landscape.pdf"),  # Sanctifier (if exists)
    ]
    
    for card_path in test_cards:
        if card_path.exists():
            print("\n\n")
            print("#" * 80)
            print(f"# TESTING: {card_path}")
            print("#" * 80)
            
            # Full comparison
            test_all_methods(card_path)
            
            # Focused comparisons
            compare_methods_for_stats(card_path)
            compare_methods_for_weapons(card_path)
        else:
            print(f"\nSkipping {card_path} (not found)")
