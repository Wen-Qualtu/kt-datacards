#!/usr/bin/env python3
import fitz
from pathlib import Path

# Check the inquisitorial-requisition card
card = Path('layers/warcom/extracted/inquisitorial-agents/cards/page07_card3_portrait.pdf')

doc = fitz.open(card)
text = doc[0].get_text()

print("Card:", card.name)
print("\nChecking special case logic:")
print(f"  Team: 'inquisitorial-agents'")
print(f"  'INQUISITORIAL REQUISITION' in text: {'INQUISITORIAL REQUISITION' in text.upper()}")
print(f"\nResult: {('inquisitorial-agents' == 'inquisitorial-agents') and ('INQUISITORIAL REQUISITION' in text.upper())}")

print("\nFirst 500 chars of text:")
print(text[:500])

doc.close()
