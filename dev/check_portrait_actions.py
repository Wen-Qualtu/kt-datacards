"""Check portrait cards for unique actions."""
import fitz
from pathlib import Path
import sys

# Test farstalker-kinband portrait cards
card_dir = Path("layers/warcom/extracted/farstalker-kinband/cards")
card_files = sorted(card_dir.glob("*_portrait.pdf"))

for pdf_path in card_files[:5]:
    doc = fitz.open(pdf_path)
    page = doc[0]
    
    # Get all text
    text = page.get_text()
    
    print(f"\n{'='*60}")
    print(f"Card: {pdf_path.name}")
    print(f"{'='*60}")
    print(text[:800])  # First 800 chars
    
    doc.close()
