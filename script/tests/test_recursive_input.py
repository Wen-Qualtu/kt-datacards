#!/usr/bin/env python3
"""Test recursive input directory scanning"""
from pathlib import Path

# Simulate the PDF discovery logic
input_dir = Path('input')

if not input_dir.exists():
    print(f"ERROR: {input_dir} does not exist")
    exit(1)

print(f"\nSearching for PDFs in: {input_dir.absolute()}")
print("-" * 60)

# Get all PDF files recursively (simple, no exclusions needed)
pdf_files = list(input_dir.rglob('*.pdf'))

for pdf_path in pdf_files:
    print(f"[FOUND] {pdf_path.relative_to(input_dir)}")

print("-" * 60)
print(f"\nTotal PDFs found: {len(pdf_files)}")
print(f"  - In root: {len([p for p in pdf_files if p.parent == input_dir])}")
print(f"  - In subdirs: {len([p for p in pdf_files if p.parent != input_dir])}")

# Show directory breakdown
from collections import defaultdict
by_dir = defaultdict(int)
for pdf in pdf_files:
    rel_dir = pdf.parent.relative_to(input_dir) if pdf.parent != input_dir else Path('.')
    by_dir[str(rel_dir)] += 1

print("\nBreakdown by directory:")
for dir_name, count in sorted(by_dir.items()):
    print(f"  {dir_name}: {count} PDF(s)")
