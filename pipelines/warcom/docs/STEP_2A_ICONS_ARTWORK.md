# Step 2a: Icon and Artwork Extraction

## Purpose

Extract team icons and artwork images from warcom PDFs. Icons are used for card backsides, and artwork images are used for promotional materials and box textures.

---

## Script

`pipelines/warcom/steps/2a_extract_icons_and_artwork.py`

---

## Input

- **Source**: `layers/warcom/staging/*.pdf` (downloaded from Step 1)
- **Generic Backgrounds**: `layers/warcom/extracted/_generic/` (optional, for filtering)

---

## Output

### Icons
- **Directory**: `layers/warcom/extracted/{team}/icons/`
- **Files**:
  - `{team}-icon-portrait.jpg` - Portrait icon for portrait card backsides
  - `{team}-icon-landscape.jpg` - Landscape icon for landscape card backsides
  - `{team}-icon-token.jpg` - Token bag icon from operatives page

### Artwork
- **Directory**: `layers/warcom/extracted/{team}/artwork/`
- **Files**:
  - `{team}-artwork-01.{ext}` - Sequential artwork images
  - `{team}-artwork-02.{ext}`
  - `{team}-artwork-metadata.json` - Metadata with image hashes

---

## Features

### Icon Extraction
- **Portrait Icon**: Extracted from page 1 at fixed coordinates (top-left corner)
- **Landscape Icon**: Extracted from page 1 at fixed coordinates (top-left corner, below portrait)
- **Token Bag Icon**: Extracted from "KILL TEAM" operatives page

All icons rendered at 5x DPI (360 DPI) for high quality.

### Artwork Extraction
- **Size Filtering**: Only extracts images >= 500px on at least one dimension
- **Aspect Ratio**: Skips images with aspect ratio > 3.0 (too narrow/wide)
- **Minimum Area**: Requires at least 250,000 pixels total
- **Deduplication**: 
  - Exact hash (SHA256) for byte-identical images
  - Perceptual hash (pHash) for visually similar images
- **Generic Background Filtering**: Automatically skips backgrounds already in `_generic/` folder
- **Sequential Numbering**: Images numbered 01, 02, 03... for consistency

### Perceptual Hash Similarity
Uses DCT-based perceptual hashing to detect visually similar images even with different compression:
- Computes 8x8 DCT of grayscale image
- Creates binary hash from low-frequency components
- Hamming distance threshold: 15/64 bits
- Filters out generic backgrounds that appear across multiple teams

---

## Generic Backgrounds System

### Purpose
Many Kill Team PDFs reuse the same background images (dark textures, abstract patterns). The generic backgrounds system prevents these from being extracted as team-specific artwork.

### Setup (One-Time)
```bash
# 1. Extract all artwork from all teams (no filtering)
cd tools
poetry run python extract_all_to_generic.py

# 2. Manually review layers/warcom/extracted/_generic/
#    Delete any team-specific artwork (character portraits, etc.)
#    Keep only generic backgrounds

# 3. Regenerate metadata with hashes
poetry run python regenerate_generic_metadata.py
```

### How It Works
1. Step 2a loads generic background hashes from `_generic/generic-artwork-metadata.json`
2. For each image extracted from a team PDF:
   - Compute exact hash (SHA256) and perceptual hash (pHash)
   - Check if exact match to any generic background
   - Check if visually similar (Hamming distance ≤ 15) to any generic background
   - Skip if match found
3. Only team-specific artwork is saved

### Current Status
- 107 generic backgrounds curated (manually selected from 344 extracted images)
- Covers common dark textures, abstract patterns, decorative elements

---

## Configuration

### Icon Coordinates
Defined in script as percentages of page dimensions:
```python
# Portrait icon (page 1)
PORTRAIT_ICON_X1 = 0.0243  # 2.43% from left
PORTRAIT_ICON_Y1 = 0.0006  # 0.06% from top
PORTRAIT_ICON_X2 = 0.1620  # 16.20% from left
PORTRAIT_ICON_Y2 = 0.1324  # 13.24% from top

# Landscape icon (page 1)
LANDSCAPE_ICON_X1 = 0.0008
LANDSCAPE_ICON_Y1 = 0.0232
LANDSCAPE_ICON_X2 = 0.1839
LANDSCAPE_ICON_Y2 = 0.1027

# Token bag icon (operatives page)
TOKEN_ICON_X1 = 0.1288
TOKEN_ICON_Y1 = 0.1625
TOKEN_ICON_X2 = 0.2724
TOKEN_ICON_Y2 = 0.2613
```

### Artwork Filters
```python
min_dimension = 500        # Minimum width or height in pixels
max_aspect_ratio = 3.0     # Maximum aspect ratio (width/height or height/width)
min_area = 250000          # Minimum total pixels
perceptual_threshold = 15  # Hamming distance threshold (0-64)
```

---

## Usage

### Extract for All Teams
```bash
poetry run python pipelines/warcom/steps/2a_extract_icons_and_artwork.py
```

### Adjust Workers
```bash
# Use 8 concurrent workers (default: 4)
poetry run python pipelines/warcom/steps/2a_extract_icons_and_artwork.py --workers 8
```

### Custom Paths
```bash
poetry run python pipelines/warcom/steps/2a_extract_icons_and_artwork.py \
  --input-dir layers/warcom/staging \
  --output-dir layers/warcom/extracted
```

---

## Metadata Format

### Artwork Metadata JSON
`{team}-artwork-metadata.json`:
```json
{
  "team": "battleclade",
  "pdf": "kt_battleclade_team_rules.pdf",
  "total_images": 12,
  "images": [
    {
      "filename": "battleclade-artwork-01.jpeg",
      "page_number": 11,
      "width": 1654,
      "height": 2339,
      "aspect_ratio": 0.71,
      "file_size_kb": 1024,
      "orientation": "portrait",
      "xref": 145,
      "image_hash": "a3b2c1d4...",
      "perceptual_hash": "1a2b3c4d..."
    }
  ]
}
```

---

## Error Handling

### Missing Generic Metadata
If `_generic/generic-artwork-metadata.json` doesn't exist, step proceeds without generic filtering (all artwork extracted).

### No Operatives Page
If "KILL TEAM" operatives page not found, token bag icon skipped (portrait and landscape icons still extracted).

### PDF Access Errors
Logged as warnings, team skipped but other teams continue processing.

---

## Performance

- **Concurrent Processing**: Uses ThreadPoolExecutor with configurable workers (default: 4)
- **Typical Runtime**: ~2-3 seconds per team (icons + artwork)
- **Memory Usage**: Moderate (processes one team at a time per worker)

---

## Troubleshooting

### No Artwork Extracted
All images were either too small or matched generic backgrounds. This is normal for teams with minimal unique artwork.

### Icons Missing
Check PDF structure - coordinates may differ for special editions. Verify page 1 has team icons.

### Wrong Token Icon
Operatives page detection failed. Manually verify which page has "KILL TEAM" in large text.

---

## See Also

- [Step 2b: Card Extraction](STEP_2B_CARD_EXTRACTION.md) - Card and token extraction
- [Generic Backgrounds](../PIPELINE-REORGANIZATION.md#generic-backgrounds) - Setup details
