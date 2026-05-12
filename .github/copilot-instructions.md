# kt-datacards — Project Knowledge

## Overview
Kill Team datacards pipeline for Tabletop Simulator (TTS). Extracts operative data from PDF datacards, generates card images, tokens, and TTS mod objects for all 46+ Kill Team teams.

## Project Structure

### Three Pipelines
- **kt-app pipeline** (`script/`): Production pipeline. CLI via `script/run_pipeline.py`. Orchestrated by `script/src/pipeline.py`. Outputs to `output_v2/` and `tts_objects/`.
- **kt-app refactor** (`pipelines/kt-app/steps/`): New modular pipeline architecture (refactor branch). 8 numbered steps (1–8). Outputs to `output_v3/` with cleaner structure. Uses `layers/kt-app/` for intermediate data.
- **warcom pipeline** (`pipelines/warcom/steps/`): Legacy pipeline with numbered steps (1–9). Kept for reference and some standalone tools (ROSZ generation, web scraping).

### Key Directories
| Directory | Purpose |
|-----------|---------|
| `input/` | Raw PDF sources (datacards) |
| `processed/` | Organized PDFs by team (`{team}/{team}-datacards.pdf`) |
| `output_v2/` | **Production**: Final extracted images & metadata, organized by faction (`imperium/`, `chaos/`, `xenos/`) |
| `output_v3/` | **Refactor**: Team-organized structure (`{team}/cards/`, `{team}/tokens/`, `{team}/data/`, `{team}/tts_object/`) |
| `metadata/{team}/` | Per-team extracted metadata (`card_index.json`, `extraction_metadata.json`, `token_index.json`) |
| `tts_objects/{team}/` | **Production**: Generated TTS save JSON files (card boxes, token bags) |
| `layers/kt-app/` | **Refactor**: Intermediate extraction data (processed PDFs, extracted pages, classified structure) |
| `config/` | Team configs, weapon rules, defaults |
| `layers/` | Image layers for card composition |
| `archive/` | Original processed PDFs |

### Config Structure
- `config/team-config.yaml` — Master team registry (canonical names, factions, aliases, token definitions)
- `config/team-guids.json` — TTS GUID mappings per team
- `config/weapon_rules.json` — Weapon rule definitions with descriptions
- `config/teams/{team}.yaml` — Individual team overrides
- `config/defaults/` — Default templates (box, card-backside, tts-image, tts-script, tts-token)

### Script Modules (`script/src/`)
- `pipeline.py` — Pipeline orchestrator with numbered steps
- `generators/` — Card/token image generation
- `managers/` — Management utilities
- `models/` — Data models/schemas
- `processors/` — Data processing
- `token_tools/` — Token-specific utilities
- `utils/` — Common utilities

## Pipeline Steps (kt-app)
1. Process raw PDFs
2. Extract images (parallel processing)
3. Add backsides
3.5. Process box textures
4. Generate V2 URLs JSON
5. Generate TTS objects
5.25. Embed ready team tokens (locked teams only)
5.4. Extract statlines from datacards PDFs
5.5. Embed datacard stats into TTS card boxes
6. Generate metadata
6.5. Generate TTS metadata with timestamps
7. Display table generation (deployment only)

## Data Flow
```
input/*.pdf
  → processed/{team}/{team}-datacards.pdf
    → extract_statlines.py → output/{team}/statlines/roster.json
    → extract images → output_v2/{faction}/{team}/cards/
      → embed_datacard_stats.py → tts_objects/{team}/*.json (patched with GMNotes + LuaScript)
```

## TTS Integration

### TTS Save JSON Structure
- Top-level `ObjectStates[]` array
- Card containers: `Bag` (CardBox) → `Deck` or `Card` objects
- Each card has `Nickname`, `GMNotes` (JSON stats), `LuaScript`
- Model state stored in `script_state` JSON: `state.stats`, `state.info` (weapons, abilities, actions, categories, rules), `state.wounds`

### Card Nickname Format
```
[FF5500]E[-] {8/8} Stalker Alpha
```
Order prefix (`[FF5500]E[-]`) + wounds (`{8/8}`) + operative name

### Lua Scripts
- `config/defaults/tts-script/datacard-load-stats.lua` — "Load stats to model" context menu
- Uses `diffAndApply()` for per-field comparison with change reporting
- `findModelOnCard()` uses `Physics.cast` to find models on card

## Key Conventions

### Team Identification
- Team slug: lowercase hyphenated (`angels-of-death`, `corsair-voidscarred`)
- Canonical names in `team-config.yaml` (e.g., "Angels of Death", "Corsair Voidscarred")
- Faction grouping: `imperium`, `chaos`, `xenos`

### Name Normalization
- `roster_slug()` strips non-ASCII characters for matching: `re.sub(r"[^\x00-\x7f]", "", s)`
- Handles Unicode chars in operative names: ô, â, ', ‑ (non-breaking hyphen)
- Card nickname matching strips order prefix and wounds from TTS nickname

### PDF Extraction
- Uses PyMuPDF (`fitz`) for text extraction
- Front page detection: looks for "NAME" + "HIT" + "WR" header keywords
- Two header formats: `NAME ATK HIT DMG WR` (full) and `NAME A HIT D WR` (abbreviated)
- Coordinate-based region extraction for statline values
- Back pages contain abilities, actions, weapon rules

### Multi-Card Faction Rules (Elite Fieldcraft Fix)
**Pattern**: Cards with "(CARD X/Y)" notation (e.g., "ELITE FIELDCRAFT (CARD 2/3)")

**Problem**: Cards were incorrectly paired as front/back when they should be separate cards.

**Solution** (applied to both pipelines):
1. Enhanced name extraction with regex: `r'FACTION\s+RULE\s+([A-Z\s]+?)\s*\(CARD\s+(\d+)/(\d+)\)'`
2. Append card number to name: "ELITE FIELDCRAFT (CARD 2/3)" → `elite-fieldcraft-card-2`
3. Prevent pairing when both pages have "(CARD X/Y)" pattern
4. Result: Card 1 (front+back), Card 2 (front+default back), Card 3 (front+default back)

**Implementation**:
- Main pipeline: `script/src/processors/image_extractor.py` lines 397-417, 172-203
- Refactor pipeline: `pipelines/kt-app/steps/2_classify_structure.py` in `extract_card_name()` and pairing logic

### Token Cleanup (Stray Pixel Fix)
**Problem**: Small pixel islands outside token boundaries (e.g., 2-5 pixels in bottom-right corner)

**Root Cause**: Conservative white detection threshold (245) allowed off-white pixels (235-244) to survive background removal.

**Solution** (refactor pipeline):
1. Lowered white detection: `v > 245` → `v > 235` (HSV value channel)
2. Increased saturation threshold: `s < 15` → `s < 25` (catches light-gray variations)
3. Added hard template boundary: Force pixels outside template to white/transparent

**Implementation**: `pipelines/kt-app/steps/5_extract_tokens.py`
- Lines ~128: `remove_background()` threshold adjustments
- Lines ~313: Hard template boundary cleanup in `process_token()`

### Metadata JSON
- `extraction_metadata.json` per team — some teams have malformed JSON (battleclade, deathwatch, exaction-squad), always wrap in try/except
- `card_index.json` — maps card numbers to operative names
- `token_index.json` — token inventory

## Dependencies
- Python 3.9+
- Core: pymupdf, pillow, pypdf2, pytesseract, pyyaml, pandas, requests, beautifulsoup4, opencv-python
