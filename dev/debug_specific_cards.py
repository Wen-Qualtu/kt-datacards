#!/usr/bin/env python3
"""
Debug script to check specific cards
"""
import fitz
from pathlib import Path

def check_card(card_path):
    """Check a specific card"""
    print(f"\n{card_path.name}")
    print("=" * 70)
    
    doc = fitz.open(card_path)
    page = doc[0]
    
    # Get text blocks sorted
    blocks = page.get_text("blocks")
    blocks_sorted = sorted(blocks, key=lambda b: (b[1], b[0]))
    
    lines = []
    for block in blocks_sorted:
        block_text = block[4].strip()
        if block_text:
            lines.extend([line.strip() for line in block_text.split('\n') if line.strip()])
    
    # Print all lines
    for i, line in enumerate(lines[:15]):
        print(f"Line {i:2d}: {line}")
    
    # Check full text
    full_text = page.get_text()
    print("\n--- Keywords ---")
    text_upper = full_text.upper()
    if 'TOKEN' in text_upper:
        print("✓ Contains 'TOKEN'")
    if 'MARKER' in text_upper:
        print("✓ Contains 'MARKER'")
    if 'INQUISITORIAL REQUISITION' in text_upper:
        print("✓ Contains 'INQUISITORIAL REQUISITION'")
    if 'FIREFIGHT PLOY' in text_upper:
        print("✓ Contains 'FIREFIGHT PLOY'")
    if 'FACTION RULE' in text_upper:
        print("✓ Contains 'FACTION RULE'")
    
    doc.close()

# Check the cards that went to faction-rules
cards_dir = Path('layers/warcom/extracted/inquisitorial-agents/cards')

# Find the problematic cards by scanning all portrait PDFs
portrait_cards = sorted(list(cards_dir.glob('*portrait.pdf')))

print(f"Found {len(portrait_cards)} portrait cards")

# Check all cards to find token guide
for i, card_path in enumerate(portrait_cards):
    if i < 5 or 'page13' in card_path.name or 'page14' in card_path.name:
        check_card(card_path)
