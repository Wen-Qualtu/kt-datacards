#!/usr/bin/env python3
"""Debug the card name extraction step by step"""
import fitz

pdf_path = "processed/wolf-scouts/wolf-scouts-equipment.pdf"
pdf = fitz.open(pdf_path)
page = pdf[0]  # First page

text_dict = page.get_text("dict")

# Collect text with sizes and positions
text_candidates = []
for block in text_dict["blocks"]:
    if block["type"] == 0:  # Text block
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                size = span["size"]
                y_pos = span["bbox"][1]  # Top position
                
                if len(text) > 3:
                    text_candidates.append((text, size, y_pos))

# Sort by size (largest first), then by position (top to bottom)
text_candidates.sort(key=lambda x: (-x[1], x[2]))

print("Sorted candidates (top 20):")
for i, (text, size, y_pos) in enumerate(text_candidates[:20]):
    print(f"{i+1}. Size {size:.1f}, Y {y_pos:.1f}: '{text}'")

# Now simulate the extraction logic
skip_terms = [
    'rules continue', 'wounds', 'save', 'move', 'apl',
    'strategy ploy', 'strategic ploy', 'tactical ploy',
    'firefight ploy', 'firefight',
    'faction equipment', 'equipment',
    'datacard', 'datacards',
    'hit', 'dmg', 'name', 'atk',
    'faction rules'
]

team_name = "wolf-scouts"
size_threshold = 7  # For equipment

print("\nProcessing candidates:")
for i, (text, size, y_pos) in enumerate(text_candidates[:20], 1):
    text_lower = text.lower()
    
    # Length check
    if len(text) < 5 or len(text) > 50:
        print(f"{i}. SKIP (length): {text}")
        continue
    
    # Team name filtering
    text_normalized = text_lower.replace(' ', '').replace('-', '')
    team_normalized = team_name.lower().replace(' ', '').replace('-', '')
    if text_normalized == team_normalized:
        print(f"{i}. SKIP (exact team match): {text}")
        continue
    
    # Skip generic terms
    matches = [skip for skip in skip_terms if skip in text_lower]
    if matches:
        print(f"{i}. SKIP (skip_terms {matches}): {text}")
        continue
    
    # Size threshold
    if size < size_threshold:
        print(f"{i}. SKIP (size {size:.1f} < {size_threshold}): {text}")
        continue
    
    # Skip rule text indicators
    if ':' in text or '(' in text or ')' in text:
        print(f"{i}. SKIP (punctuation): {text}")
        continue
    
    # This would be returned!
    print(f"{i}. ✓ MATCH: {text} (size {size:.1f})")
    break
