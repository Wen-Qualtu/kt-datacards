import fitz
from pathlib import Path

# Recreate the extraction logic with debug output
pdf_path = Path('layers/warcom/extracted/ratlings/cards/ratlings_page02_card2_landscape.pdf')

doc = fitz.open(pdf_path)
page = doc[0]
page_rect = page.rect
page_width = page_rect.width
page_height = page_rect.height

print(f"Page dimensions: {page_width} x {page_height}")
print(f"Weapon region: y from {page_height * 0.15:.1f} to {page_height * 0.50:.1f}")
print()

blocks_dict = page.get_text("dict")
blocks = blocks_dict.get("blocks", [])

# Filter blocks in weapons region
region_y1 = page_height * 0.15
region_y2 = page_height * 0.50

weapon_blocks = []
for i, block in enumerate(blocks):
    if block.get("type") != 0:  # Skip non-text blocks
        continue
    
    bbox = block["bbox"]
    
    # Extract text
    block_text = ""
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            block_text += span.get("text", "")
        block_text += "\n"
    
    block_text = block_text.strip()
    
    # Check if in weapon region
    in_x_range = bbox[0] < page_width * 0.6
    in_y_range = bbox[1] >= region_y1 and bbox[3] <= region_y2
    
    print(f"Block {i}: y=[{bbox[1]:.1f}-{bbox[3]:.1f}]  x_ok={in_x_range}  y_ok={in_y_range}")
    print(f"  Text: {block_text[:80]}")
    
    if in_x_range and in_y_range:
        weapon_blocks.append(block_text)
        print(f"  ✓ IN WEAPON REGION")
    print()

print(f"\nTotal weapon blocks found: {len(weapon_blocks)}")

doc.close()
