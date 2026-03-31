import fitz

doc = fitz.open('layers/warcom/extracted/ratlings/cards/ratlings_page02_card2_landscape.pdf')
page = doc[0]
blocks = page.get_text('dict')['blocks']

print(f"\n{'='*60}")
print("RATLING BOMBER - FRONT CARD")
print(f"{'='*60}\n")

for i, b in enumerate(blocks):
    if b.get('type') == 1:  # Image
        bbox = b['bbox']
        print(f"Block {i} IMAGE [{bbox[0]:.0f},{bbox[1]:.0f}-{bbox[3]:.0f}]")
    elif b.get('type') == 0 and b.get('lines'):  # Text
        bbox = b['bbox']
        text = ''
        for line in b['lines']:
            for span in line['spans']:
                text += span['text'] + ' '
        print(f"Block {i} TEXT [{bbox[0]:.0f},{bbox[1]:.0f}-{bbox[3]:.0f}]: {text[:80]}")

doc.close()
