#!/usr/bin/env python3
"""Debug Angels of Death faction-rules page 4"""
import fitz

pdf_path = "processed/angels-of-death/angels-of-death-faction-rules.pdf"
pdf = fitz.open(pdf_path)

print(f"Total pages: {len(pdf)}")
print("\n=== Page 3 (0-indexed) ===")
page = pdf[3]

text_dict = page.get_text("dict")

# Collect text with sizes
text_candidates = []
for block in text_dict["blocks"]:
    if block["type"] == 0:  # Text block
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                size = span["size"]
                if len(text) > 3:
                    text_candidates.append((text, size))

# Sort by size
text_candidates.sort(key=lambda x: -x[1])

print("Largest text elements:")
for i, (text, size) in enumerate(text_candidates[:15]):
    print(f"  {i+1}. Size {size:.1f}: {text}")

print("\nFull page text (first 500 chars):")
print(page.get_text()[:500])
