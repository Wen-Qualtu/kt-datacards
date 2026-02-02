#!/usr/bin/env python3
"""
Debug script to extract text from specific cards
"""
import fitz
from pathlib import Path

# Check the token guide and inquisitorial requisition cards
cards_dir = Path('layers/warcom/extracted/inquisitorial-agents/cards')

# Find portrait cards (likely token guide and faction rules)
portrait_cards = sorted([f for f in cards_dir.glob('*portrait.pdf')])

print("=" * 70)
print("PORTRAIT CARDS TEXT EXTRACTION")
print("=" * 70)

for card_path in portrait_cards[:10]:  # Check first 10 portrait cards
    print(f"\n📄 {card_path.name}")
    print("-" * 70)
    
    try:
        doc = fitz.open(card_path)
        page = doc[0]
        text = page.get_text()
        
        # Extract lines
        blocks = page.get_text("blocks")
        blocks_sorted = sorted(blocks, key=lambda b: (b[1], b[0]))  # Sort by y, then x
        
        lines = []
        for block in blocks_sorted:
            block_text = block[4].strip()
            if block_text:
                lines.extend([line.strip() for line in block_text.split('\n') if line.strip()])
        
        # Print first 10 lines
        for i, line in enumerate(lines[:10]):
            print(f"  Line {i}: {line}")
        
        # Check for special keywords
        text_upper = text.upper()
        if 'TOKEN' in text_upper or 'MARKER' in text_upper:
            print("  ⚠️  Contains TOKEN or MARKER keyword")
        if 'INQUISITORIAL REQUISITION' in text_upper:
            print("  ⚠️  Contains INQUISITORIAL REQUISITION")
        
        doc.close()
        
    except Exception as e:
        print(f"  ERROR: {e}")

print("\n" + "=" * 70)
