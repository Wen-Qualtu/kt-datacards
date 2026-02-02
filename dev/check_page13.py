#!/usr/bin/env python3
import fitz
from pathlib import Path

cards = sorted(Path('layers/warcom/extracted/inquisitorial-agents/cards').glob('page13*.pdf'))

for c in cards:
    doc = fitz.open(c)
    blocks = sorted(doc[0].get_text("blocks"), key=lambda b: (b[1], b[0]))
    lines = []
    for b in blocks:
        lines.extend([l.strip() for l in b[4].split('\n') if l.strip()])
    
    print(f"\n{c.name}")
    print("=" * 50)
    for i, line in enumerate(lines[:5]):
        print(f"  Line {i}: {line}")
    doc.close()
