# KT Datacards Extractor

This project extracts individual pages from PDF files and saves them as JPG images for use in game applications.

## Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Place your PDF files in the `input/<team-name>` folder (e.g., `input/salvagers`)
2. Run the extraction script:
```bash
python extract_pages.py
```
3. The extracted JPG images will be saved in `output/<team-name>` folder

## Output Format

Each page is saved with the naming convention:
`<pdf-filename>_page_<page-number>.jpg`

For example:
- `salvagers-datacards_page_001.jpg`
- `salvagers-datacards_page_002.jpg`
- `salvagers-equipment_page_001.jpg`

## Configuration

You can adjust the DPI (resolution) in the script by modifying the `dpi` parameter in the `extract_pdf_pages_to_jpg()` function. Default is 300 DPI.
