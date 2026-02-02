# Warcom Pipeline Documentation

## Overview

The Warcom pipeline extracts Kill Team datacards from official PDF rules documents downloaded from Warhammer Community (warcom). It processes PDFs through a 3-step pipeline to produce individual card images organized by type.

## Pipeline Steps

### Step 1: PDF Download and Archiving
**Script:** `steps/1_pdf_downloader.py`

Downloads Kill Team rules PDFs from warcom URLs and archives them.

**Input:** `config/pipelines/warcom/sources.yaml` - Contains team names and PDF download URLs
**Output:** `layers/archive/{team}/warcom/*.pdf` - Archived PDF files

**Key Features:**
- Validates URLs before downloading
- Skips already downloaded files
- Archives PDFs by team name
- Supports concurrent downloads

### Step 2: Card Extraction
**Script:** `steps/2_card_extractor.py`

Extracts individual cards from the archived PDFs. Each card is saved as a separate PDF.

**Input:** `layers/archive/{team}/warcom/*.pdf`
**Output:** `layers/warcom/extracted/{team}/cards/*.pdf`

**Filename Format:** `page{XX}_card{Y}_{orientation}.pdf`
- `page{XX}` - Zero-padded page number
- `card{Y}` - Card number on the page (1-4)
- `{orientation}` - Either `landscape` or `portrait`

**Key Features:**
- Detects card orientation automatically
- Extracts 1-4 cards per page depending on layout
- Preserves card quality in separate PDF files

### Step 3: Card Classification and Organization
**Script:** `steps/3_card_classification.py`

Classifies cards by type and converts them to PNG images with rounded corners.

**Input:** `layers/warcom/extracted/{team}/cards/*.pdf`
**Output:** `output/{team}/cards/{type}/*.png`

**Card Types:**
- `datacards/` - Operative datacards (landscape orientation)
- `equipment/` - Equipment cards
- `faction-rules/` - Faction rule cards
- `token-guide/` - Token reference guide
- `ploys/firefight/` - Firefight ploy cards
- `ploys/strategy/` - Strategic ploy cards
- `operative-selection/` - Operative selection card

**Filename Format:** `{team}-{card-name}-{side}.png`
- `{team}` - Team slug (e.g., `kommandos`, `pathfinders`)
- `{card-name}` - Extracted card name (e.g., `kommando-boss-nob`)
- `{side}` - Either `front` or `back`

**Classification Logic:**

1. **LANDSCAPE cards** = Always `datacards` (unless NOTES)
   - Extracts operative name from top-left text
   - Detects "CONTINUES ON OTHER SIDE" to pair front/back

2. **PORTRAIT cards** = Classified by header structure
   - Line 0: Team name
   - Line 1: Card type (e.g., "EQUIPMENT", "STRATEGY PLOY")
   - Line 2: Card name

3. **Special Cases:**
   - **NOTES cards** - Skipped (contain no game data)
   - **Operative Selection** - Detected by "KILL TEAM" + "ARCHETYPES"
   - **Multi-option Faction Rules** - Cards like "ACCURSED GIFTS" with numbered options

**Backside Handling:**

For cards without explicit back sides, default backsides are created:

**Priority Order:**
1. Team-specific: `config/teams/{team}/card-backside/{team}-backside-{orientation}.jpg`
2. Default: `config/defaults/card-backside/default-backside-{orientation}.jpg`

**Image Processing:**
- Renders PDFs at 300 DPI for high quality
- Applies rounded corners using template masks
- Templates shrunk by 1% and centered to prevent white edges
- Templates: `config/pipelines/warcom/template-card-{orientation}-cutter.png`

## Running the Pipeline

### Full Pipeline
```powershell
poetry run python pipelines/warcom/pdf_process_pipeline.py --step 1 --step 2 --step 3
```

### Individual Steps
```powershell
# Step 1: Download PDFs
poetry run python pipelines/warcom/pdf_process_pipeline.py --step 1

# Step 2: Extract cards
poetry run python pipelines/warcom/pdf_process_pipeline.py --step 2

# Step 3: Classify cards
poetry run python pipelines/warcom/pdf_process_pipeline.py --step 3
```

### Specific Teams
```powershell
poetry run python pipelines/warcom/pdf_process_pipeline.py --step 3 --teams kommandos pathfinders
```

### Parallel Processing
```powershell
# Use 4 concurrent workers
poetry run python pipelines/warcom/pdf_process_pipeline.py --step 3 --workers 4
```

## Directory Structure

```
pipelines/warcom/
├── README.md                          # This file
├── pdf_process_pipeline.py            # Main pipeline orchestrator
├── steps/
│   ├── 1_pdf_downloader.py           # Step 1: Download
│   ├── 2_card_extractor.py           # Step 2: Extract
│   └── 3_card_classification.py      # Step 3: Classify
│
config/
├── pipelines/warcom/
│   ├── sources.yaml                   # Download URLs
│   ├── template-card-landscape-cutter.png
│   └── template-card-portrait-cutter.png
├── defaults/card-backside/            # Default card backs
│   ├── default-backside-landscape.jpg
│   └── default-backside-portrait.jpg
└── teams/{team}/card-backside/        # Team-specific backs
    ├── {team}-backside-landscape.jpg
    └── {team}-backside-portrait.jpg
│
layers/
├── archive/{team}/warcom/*.pdf        # Archived source PDFs
└── warcom/
    ├── extracted/{team}/cards/*.pdf   # Extracted card PDFs
    └── failed/{team}/*.pdf            # Cards with naming issues
│
output/{team}/cards/                   # Final output
├── datacards/*.png
├── equipment/*.png
├── faction-rules/*.png
├── operative-selection/*.png
├── ploys/
│   ├── firefight/*.png
│   └── strategy/*.png
└── token-guide/*.png
```

## Important Details for Future Sessions

### Text Extraction
- Uses PyMuPDF (fitz) to extract text directly from PDFs
- Text blocks are sorted by position (top-to-bottom, left-to-right)
- More reliable than OCR for these PDFs

### Known Special Cases

1. **Angels of Death Chapter Tactics**
   - Cards are in wrong order in PDF
   - Special handling to pair correct fronts/backs
   - Pattern: "CHAPTER TACTIC OPTIONS ARE PRESENTED ON THEIR OWN CARD"

2. **Duplicate Card Names**
   - First occurrence keeps original name
   - Subsequent cards get `-2`, `-3`, etc. suffix
   - Tracked per card type (same name OK in different types)

3. **Multi-option Faction Rules**
   - Cards like "ACCURSED GIFTS" or "SANGUAVITAE"
   - Main rule name at top, followed by numbered options
   - Creates separate cards: `{main-rule}-{option-name}`

4. **Front/Back Card Detection**
   - Looks for "CONTINUES ON OTHER SIDE" (or "CONTINUE ON THE OTHER SIDE")
   - Next sequential card becomes the back
   - Otherwise, default backside is used

### Failed Card Detection
- Cards with naming issues are copied to `layers/warcom/failed/{team}/`
- Check this directory if cards are missing or misnamed

### Dependencies
- `PyMuPDF` (fitz) - PDF manipulation
- `opencv-python` (cv2) - Image processing
- `numpy` - Array operations
- `pyyaml` - Config file parsing
- `requests` - HTTP downloads
- `pytesseract` - OCR (optional, not actively used)

### Configuration Files
- `config/team-config.yaml` - Team metadata (names, slugs)
- `config/pipelines/warcom/sources.yaml` - Download URLs per team

### Image Quality
- PDFs rendered at 300 DPI (high quality for printing)
- PNG format with transparency (rounded corners)
- Template masks ensure consistent card shape

### Performance
- Step 1: Network-bound (downloads)
- Step 2: CPU-bound (PDF rendering)
- Step 3: CPU-bound (PDF rendering + image processing)
- Use `--workers N` for parallel processing (default: 1)

### Troubleshooting

**Card classification errors:**
- Check PDF text extraction in `layers/archive/{team}/warcom/*.pdf`
- Verify text structure matches expected pattern (Line 0=Team, 1=Type, 2=Name)

**Missing backsides:**
- Ensure default backside exists: `config/defaults/card-backside/`
- Or create team-specific: `config/teams/{team}/card-backside/`

**White edges on cards:**
- Template masks are shrunk by 1% to prevent edge artifacts
- Adjust scale in `apply_rounded_corners()` if needed

**Import errors:**
- `shutil` is imported at module level (line 19)
- Never import it locally again (causes shadowing issues)

## Future Improvements

Potential enhancements:
- [ ] Add OCR fallback for poorly structured PDFs
- [ ] Validate all cards have matching front/back pairs
- [ ] Generate card manifest/index JSON
- [ ] Add card image validation (check for corruption)
- [ ] Support batch PDF processing from multiple sources
- [ ] Add card dimension validation
- [ ] Generate preview contact sheets

## Last Updated

February 2, 2026 - Initial documentation with fixes for:
- Fixed `_get_backside_image()` path resolution
- Removed shadowing `import shutil` in `classify_team_cards()`
- Verified all teams process successfully
