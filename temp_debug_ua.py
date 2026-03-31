import fitz

doc = fitz.open('layers/warcom/extracted/pathfinders/cards/pathfinders-shaseui-pathfinder_landscape.pdf')
page = doc[0]
blocks_dict = page.get_text('dict')
blocks = blocks_dict['blocks']

print("Page size:", page.rect.width, "x", page.rect.height)
print("\nAbility blocks (y > 50%):")
print("="*80)

ability_blocks = [b for b in blocks if b.get('type') == 0 and b['bbox'][1] > page.rect.height * 0.5]

for i, block in enumerate(ability_blocks[:10]):
    bbox = block['bbox']
    print(f"\nBlock {i} at [{bbox[0]:.0f}, {bbox[1]:.0f}]:")
    for line in block.get('lines', []):
        line_text = ""
        for span in line.get('spans', []):
            text = span.get('text', '')
            font = span.get('font', '')
            is_bold = 'Bold' in font
            line_text += f"[{'B' if is_bold else 'N'}:{text}]"
        print(f"  {line_text}")

doc.close()
