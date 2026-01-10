from PIL import Image
import pytesseract
import re
from pathlib import Path

# Go up one level from script/ to root
base_path = Path(__file__).parent.parent
img_path = base_path / 'output' / 'battleclade' / 'operatives' / 'operatives_front.jpg'

img = Image.open(img_path)
text = pytesseract.image_to_string(img)

total_slots = 0
options = []

lines = text.split('\n')
i = 0

print("=== PARSING SIMULATION ===\n")

while i < len(lines):
    line = lines[i].strip()
    
    # Skip empty lines and header
    if not line or 'OPERATIVES' in line.upper() or 'KILL TEAM' in line.upper() or 'ARCHETYPES' in line.upper():
        print(f"[{i}] SKIP: {repr(line)}")
        i += 1
        continue
    
    # Check for operative count lines
    match = re.match(r'^[NU]\s*[.:]?\s*(\d+)\s+(.+)', line, re.IGNORECASE)
    if match:
        count = int(match.group(1))
        name = match.group(2).strip()
        
        print(f"[{i}] MATCH: count={count}, name={repr(name)}")
        
        # Check next line
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ''
        print(f"[{i+1}] NEXT: {repr(next_line)}")
        
        # Case 1: Just "operative"
        if next_line.lower() == 'operative':
            print(f"  -> MANDATORY operative: {name}")
            total_slots += count
            clean_name = re.sub(r'[®©]', '', name).strip()
            options.append({
                'name': clean_name,
                'max': count,
                'mandatory': True
            })
            i += 2
            continue
        
        # Case 2: Selection pool
        combined = line + ' ' + next_line
        print(f"  -> COMBINED: {repr(combined)}")
        
        if 'operatives selected from' in combined.lower() or 'following list' in next_line.lower():
            print(f"  -> SELECTION POOL (count={count})")
            total_slots += count
            
            # Skip to option lines
            i += 2
            print(f"  -> Skipping to line {i} to find options...")
            
            # Parse options
            while i < len(lines):
                option_line = lines[i].strip()
                print(f"[{i}] OPTION CHECK: {repr(option_line)}")
                
                if option_line.startswith(('e ', '© ', '° ')):
                    option_text = option_line[2:].strip()
                    operative_match = re.match(r'^([A-Z][A-Z\s&-]+?)(?:\s+with|$)', option_text)
                    if operative_match:
                        operative_name = operative_match.group(1).strip()
                        print(f"  -> FOUND OPTION: {operative_name}")
                        
                        if not any(opt['name'] == operative_name for opt in options):
                            options.append({
                                'name': operative_name,
                                'max': count
                            })
                    
                    i += 1
                elif option_line.startswith(('N', 'U')) and any(c.isdigit() for c in option_line):
                    print(f"  -> HIT ANOTHER N/U LINE, breaking")
                    break
                elif not option_line or option_line.startswith(('©', 'o')):
                    print(f"  -> SUB-OPTION OR EMPTY, skip")
                    i += 1
                else:
                    print(f"  -> UNKNOWN, skip")
                    i += 1
            
            continue
    
    print(f"[{i}] NO MATCH: {repr(line)}")
    i += 1

print("\n=== RESULTS ===")
print(f"Total slots: {total_slots}")
print(f"Options ({len(options)}):")
for opt in options:
    print(f"  - {opt}")
