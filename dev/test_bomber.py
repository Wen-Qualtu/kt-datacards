import fitz

# Check RATLING BOMBER layout
doc = fitz.open('layers/warcom/extracted/ratlings/cards/ratlings_page02_card2_landscape.pdf')
page = doc[0]
blocks = page.get_text('dict')['blocks']

print("=== RATLING BOMBER TEXT BLOCKS ===")
for i, block in enumerate(blocks[:20]):
    if 'lines' not in block:
        continue
    for line in block['lines']:
        for span in line['spans']:
            text = span['text'].strip()
            if text:
                bbox = block['bbox']
                print(f"Block {i}: [{bbox[0]:.0f}, {bbox[1]:.0f}] = '{text}'")
