from PyPDF2 import PdfReader
import os

files = ['equipment', 'firefight-ploys', 'strategy-ploys']
for f in files:
    path = os.path.join("processed", "wolf-scouts", f"wolf-scouts-{f}.pdf")
    if os.path.exists(path):
        pages = len(PdfReader(path).pages)
        print(f'{f}: {pages} pages')
    else:
        print(f'{f}: FILE NOT FOUND at {path}')
