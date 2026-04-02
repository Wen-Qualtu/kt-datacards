"""Debug script to see the raw text from lite rules PDF."""
import fitz
from pathlib import Path

pdf_path = Path("layers/warcom/staging/eng_jul25_kt_lite_rules-jmjv4hdamy-qlsqxdf83p.pdf")
doc = fitz.open(pdf_path)

# Get last page
page = doc[len(doc) - 1]

print("=" * 60)
print(f"PAGE {len(doc)} - RAW TEXT")
print("=" * 60)
print(page.get_text())

print("\n" + "=" * 60)
print(f"PAGE {len(doc)} - DICT FORMAT")
print("=" * 60)

blocks = page.get_text("dict")["blocks"]
for i, block in enumerate(blocks[:10]):  # First 10 blocks
    if block.get("type") != 0:
        continue
    
    print(f"\nBlock {i}:")
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text = span.get("text", "")
            font = span.get("font", "")
            bold = "Bold" in font
            print(f"  [{'B' if bold else ' '}] {font:30} | {text}")

doc.close()
