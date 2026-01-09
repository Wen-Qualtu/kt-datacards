import fitz

# Check the firefight ploy that was misidentified
pdf = fitz.open("input/deathwatch-watch-sergeant/deathwatch-watch-sergeant-firefight-ploy.pdf")
page = pdf[0]

print("FIREFIGHT PLOY - PAGE 1")
print("="*60)

text_dict = page.get_text("dict")

print("\nText blocks with sizes (sorted by size):")
text_list = []
for block in text_dict["blocks"]:
    if block["type"] == 0:
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

print("\n")

# Check faction rules
pdf = fitz.open("input/veteran-astartes/veteran-astartes-faction-rules.pdf")
page = pdf[0]

print("FACTION RULES - PAGE 1")
print("="*60)

text_dict = page.get_text("dict")

print("\nText blocks with sizes (sorted by size):")
text_list = []
for block in text_dict["blocks"]:
    if block["type"] == 0:
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
