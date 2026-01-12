#!/usr/bin/env python3
"""Debug script to check what's in the Wolf Scouts PDFs"""
import fitz  # PyMuPDF

files = ['equipment', 'firefight-ploys', 'strategy-ploys']
for file_type in files:
    pdf_path = f"processed/wolf-scouts/wolf-scouts-{file_type}.pdf"
    print(f"\n{'='*60}")
    print(f"Analyzing: {pdf_path}")
    print(f"{'='*60}")
    
    pdf = fitz.open(pdf_path)
    print(f"Total pages: {len(pdf)}")
    
    for page_num in range(len(pdf)):
        page = pdf[page_num]
        text_dict = page.get_text("dict")
        
        print(f"\n--- Page {page_num} ---")
        
        # Collect text with sizes
        text_candidates = []
        for block in text_dict["blocks"]:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        size = span["size"]
                        if len(text) > 3:
                            text_candidates.append((text, size))
        
        # Sort by size
        text_candidates.sort(key=lambda x: -x[1])
        
        # Print top 10 largest text elements
        print("Largest text elements:")
        for i, (text, size) in enumerate(text_candidates[:10]):
            print(f"  {i+1}. Size {size:.1f}: {text}")
