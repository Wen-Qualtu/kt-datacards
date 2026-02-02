#!/usr/bin/env python3
import sys
import fitz
from pathlib import Path

# Add the steps directory to path
sys.path.insert(0, str(Path('pipelines/warcom/steps')))

# Import the classifier
from importlib import import_module
step3 = import_module('3_card_classification')

# Create classifier
classifier = step3.CardClassifier(Path('config'))

# Test the token guide card
token_guide_card = Path('layers/warcom/extracted/inquisitorial-agents/cards/page10_card2_portrait.pdf')

# Extract text blocks
doc = fitz.open(token_guide_card)
blocks = sorted(doc[0].get_text("blocks"), key=lambda b: (b[1], b[0]))
lines = []
for b in blocks:
    lines.extend([l.strip() for l in b[4].split('\n') if l.strip()])

print("Token Guide Card Analysis")
print("=" * 50)
print("\nFirst 5 lines:")
for i, line in enumerate(lines[:5]):
    print(f"  Line {i}: {line}")

print("\nCalling _extract_card_type_from_header:")
card_type = classifier._extract_card_type_from_header(lines)
print(f"  Result: {card_type}")

print("\nCalling _extract_name_from_card:")
card_name = classifier._extract_name_from_card(lines, is_landscape=False)
print(f"  Result: {card_name}")

print("\nFull classify_card result:")
result = classifier.classify_card(token_guide_card, None)
print(f"  Type: {result[0]}")
print(f"  Name: {result[1]}")
print(f"  Orientation: {result[2]}")

doc.close()
