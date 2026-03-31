import fitz

# Check card2 (RATLING BOMBER front)
doc2 = fitz.open('layers/warcom/extracted/ratlings/cards/ratlings_page02_card2_landscape.pdf')
page2 = doc2[0]
text2 = page2.get_text().lower()
has_continue2 = 'continue' in text2 and 'other side' in text2

print("RATLING BOMBER (card2):")
print(f"  Has 'continues on other side': {has_continue2}")
if 'continue' in text2:
    for line in page2.get_text().split('\n'):
        if 'continue' in line.lower():
            print(f"  Found: {line}")

doc2.close()

# Check card3 (next card)
doc3 = fitz.open('layers/warcom/extracted/ratlings/cards/ratlings_page02_card3_landscape.pdf')
page3 = doc3[0]
blocks3 = page3.get_text('dict')['blocks']

# Find name block (top-left)
name3 = None
for block in blocks3:
    if block.get('type') == 0 and block['bbox'][0] < 100 and block['bbox'][1] < 30:
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                text = span.get('text', '').strip()
                if text and len(text) > 5:
                    name3 = text
                    break
            if name3:
                break
        if name3:
            break

doc3.close()

print(f"\nNext card (card3):")
print(f"  Operative name: {name3}")
