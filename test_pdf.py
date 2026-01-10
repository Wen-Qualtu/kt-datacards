from pathlib import Path
import fitz

pdf = fitz.open('input/failed/a3f3f97f-7ad2-4a53-b6d8-90c9b8d2db6b.pdf')
text = pdf[0].get_text()
lines = [l.strip() for l in text.split('\n') if l.strip()]

faction_keywords = ['IMPERIUM', 'CHAOS', 'AELDARI', 'TYRANIDS', 'ORKS', "T'AU", 'TAU', 'NECRONS', 'LEAGUES OF VOTANN', 'GENESTEALER']

print("Last 15 lines analysis:")
for i, line in enumerate(lines[-15:]):
    line_norm = line.replace(''', "'").replace(''', "'")
    has_faction = any(k in line_norm for k in faction_keywords)
    print(f"{i}: {repr(line[:70])}")
    print(f"   upper={line.isupper()}, commas={line.count(',')}, faction={has_faction}")
    if has_faction:
        print(f"   MATCHED!")
