# kt-datacards — Project Knowledge

## Overview
Kill Team datacards pipeline for Tabletop Simulator (TTS). Extracts operative data from PDF datacards, generates card images, tokens, and TTS mod objects for all 46+ Kill Team teams.

## Project Structure

### One Pipeline, Two Tracks
There is a single pipeline: the `pipeline/` Python package at the repo root. Run it from
the repo root with `PYTHONPATH` = repo root:

```
python -m pipeline.main --source kt-app|warcom [--step X | --from X --to Y] [--teams a,b] [--jobs N] [--force]
python -m pipeline.main --list
```

Two interchangeable extraction front-ends (**tracks**) converge on a shared,
source-agnostic integration layer, then share the rest of asset/TTS generation:
- `--source kt-app` — PDFs exported from the Kill Team mobile app (`input/`).
- `--source warcom` — official PDFs scraped from Warhammer Community.

Steps 1–4 are track-specific (need `--source`); steps 5–12 operate only on the shared
integration layer and are source-agnostic.

### Key Directories
| Directory | Purpose |
|-----------|---------|
| `pipeline/` | The pipeline code (Python package: `main.py`, `steps/`, `utils/`) |
| `config/` | Team configs (`team-config.yaml`, `defaults/`, `teams/`, `pipelines/warcom/card_templates.json`) |
| `input/` + `input_archive/` | Raw kt-app PDF sources (import / archive) |
| `layers/{track}/` | Per-track intermediate: `staging/`, `extracted/`, `structure/` (gitignored, reproducible) |
| `layers/integration/` | **Shared** classified single-card PDFs + `{team}/` manifests, content, artwork + per-team `{team}-pipeline-state.json` |
| `output/{team}/` | Final assets: `cards/`, `tokens/`, `dice/`, `cardbox/`, `data/`, `tts_objects/` |
| `output/_generic-tts-objects/` | Shared/generic TTS objects |

Output assets are referenced by TTS via `main`-branch raw URLs:
`https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/{team}/...`

### Config Structure
- `config/team-config.yaml` — Master team registry (canonical names, factions, aliases, token definitions)
- `config/team-guids.json` — TTS GUID mappings per team
- `config/weapon_rules.json` — Weapon rule definitions with descriptions
- `config/teams/{team}.yaml` — Individual team overrides
- `config/defaults/` — Default templates (box, card-backside, tts-image, tts-script, tts-token)
- `config/pipelines/warcom/card_templates.json` — Warcom card template definitions

### Pipeline Modules (`pipeline/`)
- `main.py` — Entry point + `STEP_ORDER` orchestrator
- `steps/` — One module per pipeline step
- `utils/` — Shared helpers (`paths.py` for all path resolution, `artwork.py` for pixel work, etc.)

## Pipeline Steps (`pipeline/main.py` → `STEP_ORDER`)
1. `front_end` — raw source → per-card split PDFs (`layers/{track}/extracted`)
2. `extract_artwork` — raw source → lore art + icons (`layers/integration/{team}/artwork`)
3. `build_structure` — split PDFs → `layers/{track}/structure/{team}-structure.json`
4. `integrate_classified` — extracted + structure → `layers/integration/{team}/*.pdf` + `manifest.json`
5. `content_analysis` — classified PDFs + manifest → content maps + `{team}-pipeline-state.json`
6. `extract_backsides` — artwork → `output/{team}/card-backside/*`
7. `extract_tokens` — content + artwork → `output/{team}/tokens/*.png`
8. `generate_dice` — artwork + config → `output/{team}/dice/*`
9. `generate_box_texture` — artwork + config → `output/{team}/cardbox/*`
10. `generate_card_images` — classified PDFs + backsides + content → `output/{team}/cards/*`
11. `extract_stats` — content → `output/{team}/data/{team}-team-data.json`
12. `generate_tts` — cards + stats + dice + cardbox → `output/{team}/tts_objects/*.json`

## Data Flow
```
input/*.pdf (kt-app)  OR  layers/warcom/staging/*.pdf (warcom)
  → front_end → layers/{track}/extracted/{team}/…
    → build_structure → layers/{track}/structure/{team}-structure.json
      → integrate_classified → layers/integration/{team}/*.pdf + manifest.json
        → content_analysis → layers/integration/{team}/content/*.json
          → generate_card_images → output/{team}/cards/…
          → extract_stats → output/{team}/data/{team}-team-data.json
            → generate_tts → output/{team}/tts_objects/*.json (GMNotes + LuaScript embedded)
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
- `config/defaults/tts-script/datacard-load-stats.lua` — card right-click menu, in order:
  **Load everything** (one button: stats → loadout → faction rules → movement),
  **Load stats** (loads stats + weapons; forces the loadout popup when present),
  **Add Move Action** / **Add sprint action** (keyword-gated), **Choose upgrades**,
  **Special: Rotate base 90**
- Uses `diffAndApply()` for per-field comparison with change reporting
- `findModelOnCard()` uses `Physics.cast` to find models on card
- `injectBlock()` installs/updates a tagged block on the model (`-- START/END KT_<NAME> --`,
  replace-in-place or append for old models); movement embeds via `MOVE_TOOL_CODE`/`SPRINT_TOOL_CODE`
- Movement tools: `move-tool.lua` (Move + Dash) and `sprint-movement-tool.lua`
  (Sprint/Turn/Leap, MOUNTED only) — both step the model per leg with a centred click-catcher
- **Base facing (`kt_front`)** — Sprint/Turn/Leap derive the start heading from the model's
  transform-forward + `sprint-movement-tool.lua`'s `KTUI_FACING_OFFSET` (now **0** = head-first
  by default) + a per-model `kt_front` offset (0/90/180/270) stored in the KTUI mini's
  `script_state`. **Special: Rotate base 90** bumps `kt_front` (and swaps the KTUI base `x/z`
  for the ring shape) so mirrored/proxy models are corrected in-game with a couple of clicks;
  KTUI has NO native facing field — this is our addition and it round-trips through KTUI's
  state. Rotating the model *transform* can't fix it (the heading turns with the mesh). (PR #72)

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

**Solution** (applied in the integrated pipeline):
1. Enhanced name extraction with regex: `r'FACTION\s+RULE\s+([A-Z\s]+?)\s*\(CARD\s+(\d+)/(\d+)\)'`
2. Append card number to name: "ELITE FIELDCRAFT (CARD 2/3)" → `elite-fieldcraft-card-2`
3. Prevent pairing when both pages have "(CARD X/Y)" pattern
4. Result: Card 1 (front+back), Card 2 (front+default back), Card 3 (front+default back)

**Implementation**: `pipeline/steps/` build_structure logic (card-name extraction + pairing), backed by helpers in `pipeline/utils/`.

### Token Cleanup (Stray Pixel Fix)
**Problem**: Small pixel islands outside token boundaries (e.g., 2-5 pixels in bottom-right corner)

**Root Cause**: Conservative white detection threshold (245) allowed off-white pixels (235-244) to survive background removal.

**Solution**:
1. Lowered white detection: `v > 245` → `v > 235` (HSV value channel)
2. Increased saturation threshold: `s < 15` → `s < 25` (catches light-gray variations)
3. Added hard template boundary: Force pixels outside template to white/transparent

**Implementation**: `pipeline/steps/` (extract_tokens) + `pipeline/utils/artwork.py`
- `remove_background()` threshold adjustments
- Hard template boundary cleanup during token processing

### Generated Counter Tokens (numbered per-value tokens)
**Feature**: A team's `team-config.yaml` `operative_counters` entry can carry a `generate`
block (min/max + a background image); the pipeline renders one numbered token per value.

**Key facts**:
- Code: `pipeline/utils/counter_tokens.py` (`generated_counter_states`, `generate_counter_tokens`,
  `counter_slug`), invoked by `pipeline/steps/extract_tokens.py` (`_generate_counter_tokens_for_team`).
- Background lives at `config/teams/{team}/custom-tokens/counters/{bg}.png` (derive it from a
  cut output token so it inherits the exact operative cutter alpha); output goes to
  `output/{team}/tokens/counters/{slug}-{value}.png`.
- The **dispenser scan is non-recursive** (`tokens_dir.glob('*.obj')`), so the `counters/`
  subfolder is auto-excluded — generated counters are art-only, no box token bags.
- TTS: `tts_impl._build_operative_counters_lua` positions the panels; Exodite MOUNTED riders
  get a Movement Remaining 0-12 counter (starts at 12) beside Speed + Remaining Actions. (PR #69)

### Metadata JSON
- `extraction_metadata.json` per team — some teams have malformed JSON (battleclade, deathwatch, exaction-squad), always wrap in try/except
- `card_index.json` — maps card numbers to operative names
- `token_index.json` — token inventory

## Dependencies
- Python 3.9+
- Core: pymupdf, pillow, pypdf2, pytesseract, pyyaml, pandas, requests, beautifulsoup4, opencv-python
