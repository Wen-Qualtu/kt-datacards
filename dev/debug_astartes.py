#!/usr/bin/env python3
"""Debug why ASTARTES is being filtered"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'script'))

from src.processors.image_extractor import ImageExtractor
from src.models.team import Team
from src.models.card_type import CardType
import fitz

team = Team(name="angels-of-death")
pdf = fitz.open("processed/angels-of-death/angels-of-death-faction-rules.pdf")
page = pdf[4]

extractor = ImageExtractor()
result = extractor._extract_card_name(page, CardType.FACTION_RULES, team)

print(f"Extracted card name: {result}")

# Now manually trace through the logic
text_dict = page.get_text("dict")
text_candidates = []
for block in text_dict["blocks"]:
    if block["type"] == 0:
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                size = span["size"]
                y_pos = span["bbox"][1]
                if len(text) > 3:
                    text_candidates.append((text, size, y_pos))

text_candidates.sort(key=lambda x: (-x[1], x[2]))

print("\nTop candidates:")
for i, (text, size, y_pos) in enumerate(text_candidates[:10]):
    print(f"  {i+1}. Size {size:.1f}: {text}")

# Check ASTARTES specifically
print("\nChecking ASTARTES:")
print(f"  Length: {len('ASTARTES')}")
print(f"  Size: 14.0")
print(f"  Has 'faction rule': {'faction rule' in 'ASTARTES'.lower()}")
print(f"  Team normalized: {'angelsofdeaTh'.lower()}")
print(f"  ASTARTES normalized: {'astartes'}")
print(f"  Match singular/plural: {False}")
