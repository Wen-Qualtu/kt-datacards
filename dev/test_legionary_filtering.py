import fitz

doc = fitz.open('processed/legionaries/legionaries-equipment.pdf')
team_name = "legionaries"

for page_num in range(4):
    page = doc[page_num]
    text_dict = page.get_text("dict")
    
    print(f"\n=== Page {page_num} ===")
    
    # Get all text items size 12.0
    for block in text_dict["blocks"]:
        if block["type"] == 0:
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    size = span["size"]
                    y_pos = span["bbox"][1]
                    
                    if size == 12.0 and len(text) > 3:
                        text_lower = text.lower()
                        text_normalized = text_lower.replace(' ', '').replace('-', '')
                        team_normalized = team_name.lower().replace(' ', '').replace('-', '')
                        
                        # Check all conditions
                        exact = text_normalized == team_normalized
                        plus_s = text_normalized + 's' == team_normalized
                        minus_s = text_normalized == team_normalized.rstrip('s')
                        y_to_ies = text_normalized.endswith('y') and team_normalized == text_normalized[:-1] + 'ies'
                        
                        print(f"  Y={y_pos:.1f}, '{text}' -> normalized='{text_normalized}'")
                        print(f"    exact={exact}, +s={plus_s}, -s={minus_s}, y→ies={y_to_ies}")
                        if any([exact, plus_s, minus_s, y_to_ies]):
                            print(f"    ✓ SHOULD BE FILTERED")
                        else:
                            print(f"    ✗ NOT FILTERED - will be extracted as card name!")

doc.close()
