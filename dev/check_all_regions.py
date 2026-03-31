"""Check all regions for unique actions."""
import fitz
from pathlib import Path

# Check the LONG-SIGHT back card
pdf_path = Path("layers/warcom/extracted/farstalker-kinband/cards/farstalker-kinband_page02_card4_landscape.pdf")

doc = fitz.open(pdf_path)
page = doc[0]
blocks = page.get_text('dict')['blocks']

print(f"Card: {pdf_path.name}")
print(f"Page height: {page.rect.height}")
print(f"35% threshold: {page.rect.height * 0.35}\n")

# Show ALL text blocks with their Y positions
for block in blocks:
    if block.get("type") == 0:
        bbox = block["bbox"]
        print(f"\nBlock at y={int(bbox[1])} (top) to y={int(bbox[3])} (bottom):")
        for line in block.get('lines', []):
            line_text = ""
            is_bold = False
            for span in line.get('spans', []):
                text = span.get('text', '')
                font = span.get('font', '')
                if 'Bold' in font:
                    is_bold = True
                line_text += text
            
            line_text = line_text.strip()
            if line_text:
                marker = "[BOLD]" if is_bold else "[    ]"
                print(f"  {marker} {line_text[:80]}")

doc.close()
