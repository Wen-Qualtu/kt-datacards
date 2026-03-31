"""Check LONG-SIGHT back card."""
import fitz
from pathlib import Path

# Find LONG-SIGHT cards
card_dir = Path("layers/warcom/extracted/farstalker-kinband/cards")

# Check landscape (front)
front = card_dir / "farstalker-kinband_page02_card3_landscape.pdf"
print(f"Front card: {front.name}")
doc = fitz.open(front)
text = doc[0].get_text()
print(text[:500])
print("\n" + "="*60 + "\n")
doc.close()

# Find corresponding portrait (back)
back_candidates = sorted(card_dir.glob("*portrait.pdf"))
print(f"Found {len(back_candidates)} portrait cards\n")

# Check page02_card4 (likely the back)
back = card_dir / "farstalker-kinband_page02_card4_landscape.pdf"
if back.exists():
    print(f"Checking: {back.name}")
    doc = fitz.open(back)
    text = doc[0].get_text()
    print(text)
    doc.close()
