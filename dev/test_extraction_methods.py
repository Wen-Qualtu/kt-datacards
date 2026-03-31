"""
Test different text extraction methods on datacards to find the best approach.
"""

import fitz
from pathlib import Path
import json

def test_extraction_methods(pdf_path: Path):
    """Compare different PyMuPDF extraction methods."""
    
    doc = fitz.open(pdf_path)
    page = doc[0]
    
    print(f"\n{'='*70}")
    print(f"Testing: {pdf_path.name}")
    print(f"{'='*70}\n")
    
    # Method 1: Simple text
    print("METHOD 1: get_text('text')")
    print("-" * 70)
    text = page.get_text("text")
    print(text[:500])
    print("\n")
    
    # Method 2: Blocks (what we're using)
    print("METHOD 2: get_text('blocks') - with coordinates")
    print("-" * 70)
    blocks = page.get_text("blocks")
    for i, block in enumerate(blocks[:10]):
        x0, y0, x1, y1, text, block_no, block_type = block
        print(f"Block {i} [{int(x0)},{int(y0)}-{int(x1)},{int(y1)}] type={block_type}: {text[:80]}")
    print(f"... ({len(blocks)} total blocks)\n")
    
    # Method 3: Words
    print("METHOD 3: get_text('words') - word-level")
    print("-" * 70)
    words = page.get_text("words")
    # Group words by y-coordinate (same line)
    lines = {}
    for word in words:
        x0, y0, x1, y1, text, block_no, line_no, word_no = word
        y = int(y0)
        if y not in lines:
            lines[y] = []
        lines[y].append(text)
    
    for y in sorted(lines.keys())[:15]:
        print(f"Line y={y}: {' '.join(lines[y])}")
    print("\n")
    
    # Method 4: Dict (detailed structure)
    print("METHOD 4: get_text('dict') - structured with fonts")
    print("-" * 70)
    text_dict = page.get_text("dict")
    for block_idx, block in enumerate(text_dict["blocks"][:5]):
        if block["type"] == 0:  # Text block
            print(f"\nBlock {block_idx}:")
            print(f"  bbox: {block['bbox']}")
            for line_idx, line in enumerate(block.get("lines", [])[:3]):
                print(f"  Line {line_idx}:")
                for span in line.get("spans", []):
                    print(f"    Font: {span.get('font', 'N/A')}, Size: {span.get('size', 'N/A')}")
                    print(f"    Text: {span['text'][:60]}")
        elif block["type"] == 1:  # Image block
            print(f"\nBlock {block_idx}: IMAGE at {block['bbox']}")
    print("\n")
    
    # Method 5: HTML
    print("METHOD 5: get_text('html') - HTML structure")
    print("-" * 70)
    html = page.get_text("html")
    print(html[:800])
    print("\n")
    
    doc.close()


def compare_weapon_table_extraction(pdf_path: Path):
    """Specifically test weapon table extraction methods."""
    
    doc = fitz.open(pdf_path)
    page = doc[0]
    
    print(f"\n{'='*70}")
    print(f"WEAPON TABLE EXTRACTION: {pdf_path.name}")
    print(f"{'='*70}\n")
    
    # Define weapon table region (approximate y=34-70 for most cards)
    weapon_region = fitz.Rect(0, 34, 342, 70)
    
    print("METHOD A: Blocks in weapon region")
    print("-" * 70)
    blocks = page.get_text("blocks")
    weapon_blocks = [b for b in blocks if 34 <= b[1] <= 70]
    for block in weapon_blocks:
        x0, y0, x1, y1, text, block_no, block_type = block
        print(f"Block [{int(x0)},{int(y0)}]: {text}")
    print("\n")
    
    print("METHOD B: Words in weapon region")
    print("-" * 70)
    words = page.get_text("words")
    weapon_words = [w for w in words if 34 <= w[1] <= 70]
    
    # Group by line
    lines = {}
    for word in weapon_words:
        x0, y0, x1, y1, text, block_no, line_no, word_no = word
        y = int(y0)
        if y not in lines:
            lines[y] = []
        lines[y].append((int(x0), text))
    
    for y in sorted(lines.keys()):
        words_on_line = sorted(lines[y], key=lambda x: x[0])
        line_text = ' '.join([w[1] for w in words_on_line])
        print(f"y={y}: {line_text}")
    print("\n")
    
    print("METHOD C: Dict structure in weapon region")
    print("-" * 70)
    text_dict = page.get_text("dict")
    for block in text_dict["blocks"]:
        if block["type"] == 0:  # Text
            bbox = block["bbox"]
            if bbox[1] <= 70 and bbox[3] >= 34:  # Overlaps weapon region
                print(f"Block bbox={[int(x) for x in bbox]}:")
                for line in block.get("lines", []):
                    line_text = ''.join([span['text'] for span in line.get('spans', [])])
                    print(f"  {line_text}")
        elif block["type"] == 1:  # Image
            bbox = block["bbox"]
            if bbox[1] <= 70 and bbox[3] >= 34:
                print(f"IMAGE block at {[int(x) for x in bbox]}")
    
    doc.close()


def main():
    # Test on problematic cards
    test_files = [
        Path("layers/warcom/extracted/ratlings/cards/ratlings_page01_card1_landscape.pdf"),  # RATLING BOMBER (front)
        Path("layers/warcom/extracted/ratlings/cards/ratlings_page01_card2_landscape.pdf"),  # RATLING BATTLEMUTT (back)
        Path("layers/warcom/extracted/kommandos/cards/kommandos_page01_card1_landscape.pdf"),  # Should work
    ]
    
    for pdf_path in test_files:
        if pdf_path.exists():
            test_extraction_methods(pdf_path)
            compare_weapon_table_extraction(pdf_path)
        else:
            print(f"File not found: {pdf_path}")


if __name__ == '__main__':
    main()
