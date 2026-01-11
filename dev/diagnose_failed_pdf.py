#!/usr/bin/env python3
"""
Diagnostic script to analyze a failed PDF and show what text extraction finds
"""
import fitz  # PyMuPDF
import sys
from pathlib import Path

def analyze_pdf(pdf_path: Path):
    """Analyze PDF and show all extracted text with positions"""
    print(f"\n{'='*80}")
    print(f"Analyzing: {pdf_path.name}")
    print(f"{'='*80}\n")
    
    try:
        pdf = fitz.open(pdf_path)
        page = pdf[0]  # First page
        
        # Get all text
        print("=== RAW TEXT (get_text()) ===")
        raw_text = page.get_text()
        print(raw_text)
        print("\n")
        
        # Get text with structure
        print("=== STRUCTURED TEXT (by position, top to bottom) ===")
        blocks = page.get_text('dict')['blocks']
        text_items = []
        
        for block in blocks:
            if 'lines' in block:
                for line in block['lines']:
                    line_text = ' '.join(span['text'] for span in line['spans']).strip()
                    if line_text:
                        y_pos = line['spans'][0]['bbox'][1]
                        x_pos = line['spans'][0]['bbox'][0]
                        size = line['spans'][0]['size']
                        text_items.append((y_pos, x_pos, size, line_text))
        
        # Sort by Y position (top to bottom), then X position
        text_items.sort(key=lambda x: (x[0], x[1]))
        
        print(f"{'Y-Pos':<8} {'X-Pos':<8} {'Size':<6} {'Text'}")
        print(f"{'-'*80}")
        for y, x, size, text in text_items:
            print(f"{y:<8.1f} {x:<8.1f} {size:<6.1f} {text}")
        
        # Show bottom portion (last 20 lines)
        print(f"\n\n=== BOTTOM 20 LINES (where team tag expected) ===")
        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        for i, line in enumerate(lines[-20:], start=len(lines)-20):
            print(f"[{i:2d}] {line}")
        
        # Show lines by size (largest first)
        print(f"\n\n=== TEXT BY SIZE (largest first, top 30) ===")
        text_by_size = []
        for block in blocks:
            if 'lines' in block:
                for line in block['lines']:
                    for span in line['spans']:
                        text = span['text'].strip()
                        size = span['size']
                        if text and len(text) > 3:
                            text_by_size.append((size, text))
        
        text_by_size.sort(reverse=True, key=lambda x: x[0])
        
        print(f"{'Size':<8} {'Text'}")
        print(f"{'-'*80}")
        for size, text in text_by_size[:30]:
            print(f"{size:<8.1f} {text}")
        
        # Check for faction keywords
        print(f"\n\n=== FACTION KEYWORD DETECTION ===")
        faction_keywords = [
            'IMPERIUM', 'CHAOS', 'AELDARI', 'TYRANIDS', 'ORKS',
            'TAU', 'NECRONS', 'LEAGUES OF VOTANN', 'GENESTEALER'
        ]
        
        found_factions = []
        for line in lines:
            line_upper = line.upper()
            for faction in faction_keywords:
                if faction in line_upper:
                    found_factions.append((line, faction))
        
        if found_factions:
            print("Found faction keywords:")
            for line, faction in found_factions:
                print(f"  - {faction} in: {line}")
        else:
            print("NO FACTION KEYWORDS FOUND!")
        
        # Check for uppercase lines in bottom section
        print(f"\n\n=== UPPERCASE LINES IN BOTTOM 20 ===")
        for i, line in enumerate(lines[-20:], start=len(lines)-20):
            if line.isupper() and len(line) > 2:
                print(f"[{i:2d}] {line}")
        
        pdf.close()
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Default to the failed file
    failed_pdf = Path("input/failed/89436875-f17c-4eef-8fe4-03cbc7e80f05.pdf")
    
    if len(sys.argv) > 1:
        failed_pdf = Path(sys.argv[1])
    
    if not failed_pdf.exists():
        print(f"ERROR: File not found: {failed_pdf}")
        sys.exit(1)
    
    analyze_pdf(failed_pdf)
