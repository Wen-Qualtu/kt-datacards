from PIL import Image
import pytesseract
import re
from pathlib import Path

# Go up one level from script/ to root
base_path = Path(__file__).parent.parent
img_path = base_path / 'output' / 'battleclade' / 'operatives' / 'operatives_front.jpg'

img = Image.open(img_path)
text = pytesseract.image_to_string(img)

print('=== RAW TEXT ===')
print(repr(text))

print('\n=== LINES ===')
for i, line in enumerate(text.split('\n')):
    print(f'{i}: {repr(line)}')

print('\n=== REGEX TESTS ===')
for i, line in enumerate(text.split('\n')):
    line = line.strip()
    if not line:
        continue
    
    match = re.match(r'^[NU]\s*[.:]?\s*(\d+)\s+(.+?)\s+operatives?(?:\s+with|$)', line, re.IGNORECASE)
    if match:
        print(f'Line {i} MATCHED: count={match.group(1)}, name={match.group(2)}')
        print(f'  Full line: {repr(line)}')
