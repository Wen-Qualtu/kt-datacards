"""Debug script to trace blooded equipment PDF identification"""

import fitz
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'script'))

from src.processors.team_identifier import TeamIdentifier
from src.processors.pdf_processor import PDFProcessor

# Initialize
ti = TeamIdentifier(Path('config/team-config.yaml'))
pp = PDFProcessor(ti)

# Open PDF
pdf_path = Path('input/failed/74d8bf18-0a70-4ddd-93c6-1665c23b8c9e.pdf')
pdf = fitz.open(pdf_path)
page = pdf[0]

# Extract lines by position
blocks = page.get_text('dict')['blocks']
text_items = []
for block in blocks:
    if 'lines' in block:
        for line in block['lines']:
            line_text = ' '.join(span['text'] for span in line['spans']).strip()
            if line_text:
                y_pos = line['spans'][0]['bbox'][1]
                text_items.append((y_pos, line_text))

text_items.sort(key=lambda x: x[0])
lines_by_position = [text for _, text in text_items]

print("First 10 lines:")
for i, line in enumerate(lines_by_position[:10]):
    print(f"  {i}: {line}")

# Check for card type line
print("\nLooking for card type...")
card_type_line_idx = -1
for i in range(1, min(5, len(lines_by_position))):
    line_upper = lines_by_position[i].upper()
    print(f"  Line {i}: '{line_upper}'")
    if any(keyword in line_upper for keyword in [
        'FACTION EQUIPMENT', 'STRATEGY PLOY', 'FIREFIGHT PLOY',
        'FACTION RULE', 'OPERATIVES', 'ARCHETYPE'
    ]):
        print(f"    → Found card type at line {i}!")
        card_type_line_idx = i
        break

if card_type_line_idx == -1:
    print("  No card type found!")
else:
    print(f"\nExtracting team name from lines before {card_type_line_idx}...")
    team_name_lines = []
    for i in range(max(0, card_type_line_idx - 2), card_type_line_idx):
        line = lines_by_position[i].strip()
        print(f"  Checking line {i}: '{line}'")
        if line and len(line) > 3 and line.isupper():
            print(f"    → Adding to team name")
            team_name_lines.append(line)
        else:
            print(f"    → Skipping (len={len(line)}, isupper={line.isupper()})")
    
    print(f"\nTeam name lines: {team_name_lines}")
    
    if team_name_lines:
        team_name = ' '.join(team_name_lines)
        print(f"Combined team name: '{team_name}'")
        
        # Clean filename
        cleaned = pp._clean_filename(team_name)
        print(f"Cleaned team name: '{cleaned}'")

pdf.close()
