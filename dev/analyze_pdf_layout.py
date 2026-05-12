"""Analyze PDF layout to understand extraction differences"""
import fitz
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

def analyze_pdf(pdf_path, name):
    """Analyze text block positions in a PDF"""
    print(f"\n{'='*60}")
    print(f"ANALYZING: {name}")
    print(f"{'='*60}")
    
    doc = fitz.open(pdf_path)
    page = doc[0]
    pw = page.rect.width
    ph = page.rect.height
    
    print(f"Page size: {pw:.1f} x {ph:.1f}")
    print(f"\nText blocks:")
    
    blocks = page.get_text("dict").get("blocks", [])
    
    for i, block in enumerate(blocks):
        if block.get("type") != 0:  # Skip non-text blocks
            continue
        
        bbox = block["bbox"]
        x0, y0, x1, y1 = bbox
        
        # Extract text
        text = ""
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text += span.get("text", "")
        
        text = text.strip()
        if not text:
            continue
        
        # Calculate relative position
        rel_x = x0 / pw
        rel_y = y0 / ph
        
        # Show block info
        print(f"\n  Block {i}:")
        print(f"    Position: ({x0:.1f}, {y0:.1f}) - ({x1:.1f}, {y1:.1f})")
        print(f"    Relative: ({rel_x:.2f}, {rel_y:.2f})")
        print(f"    Text: '{text[:80]}'")
        
        # Categorize by position
        if rel_x < 0.6 and rel_y < 0.05:
            print(f"    => TOP-LEFT (name/APL area)")
        elif rel_x > 0.65 and rel_y < 0.25:
            print(f"    => TOP-RIGHT (stats area)")
        elif 'NAME' in text or 'HIT' in text or 'DMG' in text:
            print(f"    => HEADER")
    
    doc.close()

# Analyze working vs failing operatives
working = PROJECT_ROOT / "layers/kt-app/extracted/spectre-squad/cards/datacards/spectre-squad-datacards-page_5.pdf"
failing = PROJECT_ROOT / "layers/kt-app/extracted/spectre-squad/cards/datacards/spectre-squad-datacards-page_0.pdf"

if working.exists():
    analyze_pdf(working, "SPECTRE GUIDE (WORKING)")
else:
    print(f"Working PDF not found: {working}")

if failing.exists():
    analyze_pdf(failing, "SPECTRE VETERAN SERGEANT (FAILING)")
else:
    print(f"Failing PDF not found: {failing}")
