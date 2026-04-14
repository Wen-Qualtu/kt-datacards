# kt-datacards — Project Knowledge

## Overview
Kill Team datacards pipeline for Tabletop Simulator (TTS). Extracts operative data from PDF datacards, generates card images, tokens, and TTS mod objects for all 46+ Kill Team teams.

## Project Structure

### Two Pipelines
- **kt-app pipeline** (`script/`): Primary pipeline. CLI via `script/run_pipeline.py`. Orchestrated by `script/src/pipeline.py`.
- **warcom pipeline** (`pipelines/warcom/steps/`): Legacy pipeline with numbered steps (1–9). Kept for reference and some standalone tools (ROSZ generation, web scraping).

### Key Directories
| Directory | Purpose |
|-----------|---------|
| `input/` | Raw PDF sources (datacards) |
| `processed/` | Organized PDFs by team (`{team}/{team}-datacards.pdf`) |
| `output_v2/` | Final extracted images & metadata, organized by faction (`imperium/`, `chaos/`, `xenos/`) |
| `metadata/{team}/` | Per-team extracted metadata (`card_index.json`, `extraction_metadata.json`, `token_index.json`) |
| `tts_objects/{team}/` | Generated TTS save JSON files (card boxes, token bags) |
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

### Metadata JSON
- `extraction_metadata.json` per team — some teams have malformed JSON (battleclade, deathwatch, exaction-squad), always wrap in try/except
- `card_index.json` — maps card numbers to operative names
- `token_index.json` — token inventory

## Dependencies
- Python 3.9+
- Core: pymupdf, pillow, pypdf2, pytesseract, pyyaml, pandas, requests, beautifulsoup4, opencv-python
