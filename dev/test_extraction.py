#!/usr/bin/env python3
"""Test the card name extraction with the fixed code"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'script'))

from src.processors.image_extractor import ImageExtractor
from src.models.team import Team
from src.models.card_type import CardType
import fitz

# Create a test team
team = Team(name="wolf-scouts")

# Test equipment PDF
pdf_path = "processed/wolf-scouts/wolf-scouts-equipment.pdf"
pdf = fitz.open(pdf_path)

extractor = ImageExtractor()

print("Testing equipment card name extraction:")
for page_num in range(len(pdf)):
    page = pdf[page_num]
    card_name = extractor._extract_card_name(page, CardType.EQUIPMENT, team)
    print(f"  Page {page_num}: {card_name}")

print("\nTesting firefight-ploys card name extraction:")
pdf_path = "processed/wolf-scouts/wolf-scouts-firefight-ploys.pdf"
pdf = fitz.open(pdf_path)
for page_num in range(len(pdf)):
    page = pdf[page_num]
    card_name = extractor._extract_card_name(page, CardType.FIREFIGHT_PLOYS, team)
    print(f"  Page {page_num}: {card_name}")

print("\nTesting strategy-ploys card name extraction:")
pdf_path = "processed/wolf-scouts/wolf-scouts-strategy-ploys.pdf"
pdf = fitz.open(pdf_path)
for page_num in range(len(pdf)):
    page = pdf[page_num]
    card_name = extractor._extract_card_name(page, CardType.STRATEGY_PLOYS, team)
    print(f"  Page {page_num}: {card_name}")
