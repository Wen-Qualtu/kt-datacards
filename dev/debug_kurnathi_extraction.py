#!/usr/bin/env python3
"""Debug Kurnathi abilities extraction."""
import sys
sys.path.insert(0, 'pipelines/kt-app/steps')

import fitz
from pathlib import Path

# Open PDF
pdf_path = Path("processed/corsair-voidscarred/corsair-voidscarred-datacards.pdf")
doc = fitz.open(pdf_path)

print(f"Total pages: {len(doc)}\n")

# Find Kurnathi pages
for i in range(len(doc)):
    text = doc[i].get_text()
    if 'KURNATHI' in text.upper():
        print(f"=" * 60)
        print(f"Page {i}: Kurnathi card")
        print("=" * 60)
        print(text)
        print()
        
        # Check if this is front or back page
        if 'NAME' in text and 'HIT' in text and 'WR' in text:
            print("-> This is a FRONT page (has weapon stats)")
        else:
            print("-> This is a BACK page (abilities)")
        print()

doc.close()
