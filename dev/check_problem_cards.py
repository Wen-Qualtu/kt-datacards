#!/usr/bin/env python3
import fitz
from pathlib import Path

cards_dir = Path('layers/warcom/extracted/inquisitorial-agents/cards')

# Find token guide card (page10_card2)
token_cards = [c for c in cards_dir.glob('*portrait.pdf') if 'page10_card2' in c.name]
if token_cards:
    print('=== TOKEN GUIDE CARD (page10_card2_portrait.pdf) ===')
    doc = fitz.open(token_cards[0])
    blocks = sorted(doc[0].get_text('blocks'), key=lambda b: (b[1], b[0]))
    lines = [l.strip() for b in blocks for l in b[4].split('\n') if l.strip()]
    for i, line in enumerate(lines[:10]):
        print(f'Line {i}: {line}')
    doc.close()

print()

# Find denounce card (page10_card3)
denounce_cards = [c for c in cards_dir.glob('*portrait.pdf') if 'page10_card3' in c.name]
if denounce_cards:
    print('=== DENOUNCE CARD (page10_card3_portrait.pdf) ===')
    doc = fitz.open(denounce_cards[0])
    blocks = sorted(doc[0].get_text('blocks'), key=lambda b: (b[1], b[0]))
    lines = [l.strip() for b in blocks for l in b[4].split('\n') if l.strip()]
    for i, line in enumerate(lines[:10]):
        print(f'Line {i}: {line}')
    doc.close()

print()

# Now let's test classification on both
import sys
sys.path.insert(0, 'pipelines/warcom/steps')
from importlib import import_module
step3 = import_module('3_card_classification')

classifier = step3.CardClassifier(Path('config'))

if token_cards:
    print('=== TOKEN GUIDE CLASSIFICATION TEST ===')
    result = classifier.classify_card(token_cards[0], None)
    print(f'Type: {result[0]}')
    print(f'Name: {result[1]}')
    print(f'Orientation: {result[2]}')

print()

if denounce_cards:
    print('=== DENOUNCE CLASSIFICATION TEST ===')
    result = classifier.classify_card(denounce_cards[0], None)
    print(f'Type: {result[0]}')
    print(f'Name: {result[1]}')
    print(f'Orientation: {result[2]}')
