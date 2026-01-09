import fitz

# Check battleclade datacards page 1
pdf = fitz.open("input/battleclade/battleclade-datacards.pdf")
page = pdf[0]

print("BATTLECLADE DATACARDS - PAGE 1")
print("="*60)

# Get text with detailed formatting info
text_dict = page.get_text("dict")

print("\nText blocks with sizes (sorted by size):")
text_list = []
for block in text_dict["blocks"]:
    if block["type"] == 0:  # Text block
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                size = span["size"]
                if text and len(text) > 3:
                    text_list.append((size, text))

text_list.sort(reverse=True)
for size, text in text_list[:20]:
    print(f"  Size {size:.1f}: '{text}'")

pdf.close()
