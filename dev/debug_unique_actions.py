"""Debug unique actions extraction."""
import fitz
from pathlib import Path

# Test farstalker-kinband cards (including portrait/back sides)
card_dir = Path("layers/warcom/extracted/farstalker-kinband/cards")
card_files = sorted(card_dir.glob("*.pdf"))

print(f"Testing {len(card_files)} farstalker-kinband cards (landscape + portrait)\n")

for pdf_path in card_files:
    doc = fitz.open(pdf_path)
    page = doc[0]
    blocks = page.get_text('dict')['blocks']
    
    # Find ability blocks (y > 100)
    ability_blocks = [b for b in blocks if b.get('type') == 0 and b['bbox'][1] > 100]
    
    print(f"\n{'='*60}")
    print(f"Card: {pdf_path.name}")
    print(f"{'='*60}")
    
    if not ability_blocks:
        print("  No ability blocks found")
        doc.close()
        continue
    
    # Extract text lines with bold formatting
    ability_lines = []
    for block in ability_blocks:
        for line in block.get('lines', []):
            line_text = ""
            is_bold = False
            for span in line.get('spans', []):
                text = span.get('text', '')
                font = span.get('font', '')
                if 'Bold' in font or span.get('flags', 0) & 16:
                    is_bold = True
                line_text += text
            
            line_text = line_text.strip()
            if line_text:
                ability_lines.append((line_text, is_bold))
    
    # Print first 10 lines
    for i, (text, is_bold) in enumerate(ability_lines[:10]):
        marker = "[BOLD]" if is_bold else "[    ]"
        print(f"  {marker} {text[:70]}")
    
    doc.close()

