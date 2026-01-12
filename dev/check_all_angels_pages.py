#!/usr/bin/env python3
"""Check all pages of Angels faction-rules"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'script'))

from src.processors.image_extractor import ImageExtractor
from src.models.team import Team
from src.models.card_type import CardType
import fitz

team = Team(name="angels-of-death")
pdf = fitz.open("processed/angels-of-death/angels-of-death-faction-rules.pdf")

extractor = ImageExtractor()

print(f"Total pages: {len(pdf)}\n")

for page_num in range(len(pdf)):
    page = pdf[page_num]
    card_name = extractor._extract_card_name(page, CardType.FACTION_RULES, team)
    
    # Get largest text for context
    text_dict = page.get_text("dict")
    text_candidates = []
    for block in text_dict["blocks"]:
        if block["type"] == 0:
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    size = span["size"]
                    if len(text) > 3 and size > 10:
                        text_candidates.append((text, size))
    text_candidates.sort(key=lambda x: -x[1])
    
    print(f"Page {page_num}:")
    print(f"  Extracted: {card_name}")
    print(f"  Large text: {[t[0] for t in text_candidates[:3]]}")
    print()
