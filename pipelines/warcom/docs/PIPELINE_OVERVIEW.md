# Warcom Pipeline Overview

## Purpose

The warcom pipeline extracts Kill Team datacards and tokens from official PDF rules documents downloaded from Warhammer Community (warcom). It processes PDFs through a 5-step pipeline to produce individual card images, tokens, and TTS-compatible JSON objects.

---

## Pipeline Steps

| Step | Script | Input | Output | Purpose |
|------|--------|-------|--------|---------|
| **1** | `1_scrape_warcom_killteam_downloads.py` | Warcom website | `layers/warcom/staging/*.pdf` | Download PDFs from warcom downloads page |
| **2** | `2_card_extractor.py` | `layers/warcom/staging/*.pdf` | `layers/warcom/extracted/{team}/cards/*.pdf`<br>`layers/warcom/extracted/{team}/tokens/*.png` | Extract individual cards and tokens using template matching |
| **3** | `3_card_classification.py` | `layers/warcom/extracted/{team}/cards/*.pdf` | `output/{team}/cards/{type}/*.jpg` | Classify cards by type and convert to PNG with rounded corners |
| **4** | `4_token_extraction.py` | `layers/warcom/extracted/{team}/tokens/*.png`<br>`layers/warcom/extracted/{team}/tokens/token-names.json` | `output/{team}/tokens/*.png` | Match tokens to names, apply shape templates, make transparent |
| **5** | `5_generate_tts_objects.py` | `output/{team}/cards/**/*.jpg`<br>`output/{team}/tokens/*.png` | `output/{team}/tts/**/*.json`<br>`output/.tts-metadata.json` | Generate TTS JSON objects with change detection |

---

## Running the Pipeline

### Prerequisites
```bash
poetry install
```

### Run All Steps (1-3)
```bash
poetry run python pipelines/warcom/pdf_process_pipeline.py --all
```

### Run Individual Steps
```bash
# Step 1: Download PDFs
poetry run python pipelines/warcom/pdf_process_pipeline.py --step 1

# Step 2: Extract cards and tokens
poetry run python pipelines/warcom/pdf_process_pipeline.py --step 2

# Step 3: Classify cards
poetry run python pipelines/warcom/pdf_process_pipeline.py --step 3

# Step 4: Process tokens
poetry run python pipelines/warcom/steps/4_token_extraction.py

# Step 5: Generate TTS objects
poetry run python pipelines/warcom/steps/5_generate_tts_objects.py
```

### Process Specific Teams
```bash
# Steps 1-3
poetry run python pipelines/warcom/pdf_process_pipeline.py --step 3 --teams kommandos pathfinders

# Step 4
poetry run python pipelines/warcom/steps/4_token_extraction.py --teams kommandos

# Step 5
poetry run python pipelines/warcom/steps/5_generate_tts_objects.py --teams kommandos --force

# Step 5 with custom branch for GitHub URLs (for testing)
poetry run python pipelines/warcom/steps/5_generate_tts_objects.py --branch dev --force
```

### Parallel Processing
```bash
# Use 4 concurrent workers
poetry run python pipelines/warcom/pdf_process_pipeline.py --step 3 --workers 4
```

---

## Directory Structure

```
pipelines/warcom/
├── docs/
│   ├── PIPELINE_OVERVIEW.md          # This file
│   ├── STEP_1_SCRAPING.md             # Step 1 detailed logic
│   ├── STEP_2_EXTRACTION.md           # Step 2 detailed logic
│   ├── STEP_3_CLASSIFICATION.md       # Step 3 detailed logic
│   ├── STEP_4_TOKEN_PROCESSING.md     # Step 4 detailed logic
│   └── STEP_5_TTS_GENERATION.md       # Step 5 detailed logic
├── pdf_process_pipeline.py            # Main orchestrator (steps 1-3)
└── steps/
    ├── 1_scrape_warcom_killteam_downloads.py
    ├── 2_card_extractor.py
    ├── 3_card_classification.py
    ├── 4_token_extraction.py
    └── 5_generate_tts_objects.py

config/
├── team-config.yaml                   # Team metadata, token shapes
├── pipelines/warcom/
│   ├── extraction-templates.json      # Card extraction templates
│   ├── template-card-landscape-cutter.png
│   └── template-card-portrait-cutter.png
├── defaults/
│   ├── card-backside/                 # Default card backs
│   │   ├── default-backside-landscape.jpg
│   │   └── default-backside-portrait.jpg
│   ├── tts-script/                    # Lua scripts
│   │   ├── token-bag-script.lua
│   │   └── ...other scripts
│   ├── tts-spawner/                   # Team spawner assets
│   │   └── spawner-overview.png
│   └── tts-token/                     # Token meshes and templates
│       ├── square-bag-mesh.obj
│       ├── token-mesh.obj
│       └── input/
│           ├── template-round-cutter.png
│           ├── template-octagon-cutter.png
│           ├── template-diamond-cutter.png
│           ├── template-operative-cutter.png
│           └── token-bg-sample.png
└── teams/{team}/card-backside/        # Team-specific backs
    ├── {team}-backside-landscape.jpg
    └── {team}-backside-portrait.jpg

layers/
├── archive/{team}/warcom/*.pdf        # Archived source PDFs
└── warcom/
    ├── staging/*.pdf                  # Downloaded PDFs awaiting extraction
    └── extracted/{team}/
        ├── cards/*.pdf                # Extracted card PDFs
        └── tokens/
            ├── *.png                  # Rough-cropped tokens
            └── token-names.json       # Token name mapping

output/{team}/
├── cards/{cardtype}/*.jpg             # Final card images
├── tokens/*.png                       # Final token images
└── tts/                               # TTS objects
    ├── {team}-cardbox.json            # Main container
    └── cardbox/
        ├── {team}-lua-script.lua
        ├── single-cards/
        │   └── {team}-{type}.json     # Single cards
        ├── decks/
        │   ├── {team}-{type}.json     # Deck objects
        │   └── {type}/                # Individual card JSONs
        │       └── {team}-{card}.json
        └── token-bag/
            ├── token-bag.json
            └── {token}/
                ├── {team}-{token}.json         # Dispenser
                └── {team}-{token}-token.json   # Token

output/
└── .tts-metadata.json                 # Change detection metadata
```

---

## Key Concepts

### Card Types

| Type | Description | Orientation | Example |
|------|-------------|-------------|---------|
| `datacards` | Operative datacards with stats | Landscape | kommando-boy-front.jpg |
| `equipment` | Equipment cards | Portrait | kustom-shoota-front.jpg |
| `faction-rules` | Faction-specific rules | Portrait | da-kommanda-front.jpg |
| `operative-selection` | Operative selection reference | Portrait | operative-selection-front.jpg |
| `firefight-ploys` | Firefight tactical ploys | Portrait | get-stuck-in-front.jpg |
| `strategy-ploys` | Strategic ploys | Portrait | opportunist-front.jpg |
| `token-guide` | Token reference guide | Portrait | token-guide-front.jpg |

### Filename Conventions

**Cards:**
- Pattern: `{team}-{card-name}-{side}.jpg`
- Example: `kommandos-kommando-boy-front.jpg`
- Side: `front` or `back`

**Tokens:**
- Pattern: `{team}_{token-name}.png`
- Example: `kommandos_breach.png`
- Background: Transparent

**TTS Objects:**
- Pattern: `{team}-{object-name}.json`
- Example: `kommandos-datacards.json`

### Team Naming

All team names are normalized to **kebab-case**:
- `angels-of-death`
- `corsair-voidscarred`
- `kommandos`

Team names are matched using `config/team-config.yaml` which includes aliases for flexible matching.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `PyMuPDF` (fitz) | PDF manipulation and text extraction |
| `opencv-python` (cv2) | Image processing and template matching |
| `numpy` | Array operations |
| `pyyaml` | Configuration file parsing |
| `requests` | HTTP downloads |
| `playwright` | Browser automation for web scraping |

---

## Configuration Files

### `config/team-config.yaml`
Team metadata including:
- Canonical names
- Faction assignments (imperium, chaos, xenos)
- Army classifications
- Aliases for flexible name matching
- Token shapes per team

### `config/pipelines/warcom/extraction-templates.json`
Template matching grid definitions for card extraction at 300 DPI.

---

## Performance Characteristics

| Step | Workload Type | Bottleneck | Parallelization |
|------|--------------|------------|-----------------|
| 1 | Network-bound | Download speed | Yes (concurrent downloads) |
| 2 | CPU-bound | PDF rendering | Yes (`--workers N`) |
| 3 | CPU-bound | Image processing | Yes (`--workers N`) |
| 4 | CPU-bound | Image processing | No |
| 5 | I/O-bound | File operations | No |

**Typical Runtime:**
- Full pipeline (all 46 teams): 15-30 minutes (depending on parallelization)
- Single team: 1-2 minutes

---

## Troubleshooting

### Common Issues

**No PDFs downloaded:**
- Check `config/pipelines/warcom/sources.yaml` for valid URLs
- Verify network connectivity
- Check logs for HTTP errors

**Cards missing after extraction:**
- Check `layers/warcom/extracted/{team}/cards/` for PDFs
- Verify templates match PDF structure
- Review logs for extraction errors

**Card classification errors:**
- Check PDF text extraction quality
- Verify team name in `config/team-config.yaml`
- Review text structure on problematic cards

**Tokens not matching names:**
- Check `layers/warcom/extracted/{team}/tokens/token-names.json`
- Verify token shapes in `config/team-config.yaml`
- Check coordinate scale detection in logs

**TTS objects not updating:**
- Use `--force` flag to bypass change detection
- Check `.tts-metadata.json` for component hashes
- Verify card images exist in `output/{team}/cards/`

---

## Design Philosophy

### Quality Over Speed
- Accuracy is paramount (especially for stats and card names)
- Better to warn/error than produce wrong data
- Manual review is acceptable when uncertain
- Processing can take hours - that's fine

### Immutable Output
- The `output/` folder structure is **IMMUTABLE**
- TTS cards reference exact GitHub raw URLs
- Never rename folders, restructure paths, or move files in `output/`
- Only add new files or update existing images

### Logging Standard
- All scripts use Python's `logging` module exclusively
- No `print()` statements
- Use `--log-level DEBUG` for detailed diagnostics
- Format: `'%(levelname)s: %(message)s'`

---

## Next Steps

For detailed information on each step, see:
- [STEP_1_SCRAPING.md](STEP_1_SCRAPING.md) - PDF download logic
- [STEP_2_EXTRACTION.md](STEP_2_EXTRACTION.md) - Card and token extraction
- [STEP_3_CLASSIFICATION.md](STEP_3_CLASSIFICATION.md) - Card classification rules
- [STEP_4_TOKEN_PROCESSING.md](STEP_4_TOKEN_PROCESSING.md) - Token name matching and processing
- [STEP_5_TTS_GENERATION.md](STEP_5_TTS_GENERATION.md) - TTS object generation and change detection

---

**Last Updated**: February 16, 2026
