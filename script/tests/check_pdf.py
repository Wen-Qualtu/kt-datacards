#!/usr/bin/env python3
"""Quick test to check PDF content"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'script'))
import os
os.chdir(project_root)

import fitz

pdf_path = Path("processed/angels-of-death/angels-of-death-datacards.pdf")

if pdf_path.exists():
    doc = fitz.open(pdf_path)
    print(f"Pages: {len(doc)}")
    print("\n=== First Page Text ===")
    if len(doc) > 0:
        text = doc[0].get_text()
        print(text[:1000])
    doc.close()
else:
    print(f"PDF not found: {pdf_path}")
