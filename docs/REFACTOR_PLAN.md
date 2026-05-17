# KT-App Pipeline Refactoring Plan

## Key Changes from Current Pipeline

### 1. **Intermediate Layer with Single-Page PDFs**
- **Current**: `processed/{team}/{team}-datacards.pdf` (multi-page) → directly to `output_v2/` images
- **New**: `processed/{team}/{team}-datacards.pdf` → `layers/kt-app/extracted/{team}/cards/{team}-datacards-page_0.pdf` → `output_v2/` images
- **Benefit**: Classification and statline extraction work on single-page PDFs (much simpler!)

### 2. **Reordered Steps (Logical Flow)**
- **Current**: Process → Extract Images → Backsides → Box Textures → URLs → TTS (no stats!) → Tokens → Extract Stats → Embed Stats
- **New**: Process+Split → Classify → **Extract Stats** → Extract Cards → Tokens → TTS (with stats embedded!)
- **Benefit**: Stats available before TTS generation, no need for separate embedding step

### 3. **Unified Metadata System**
- **Current**: Multiple metadata files (`metadata/{team}/*.json`, `output_v2/tts-metadata.json`, `output_v2/tts-card-boxes.json`)
- **New**: Single `layers/kt-app/metadata.json` with hashes, updated continuously by Steps 1-6
- **Benefit**: Hash-based change detection, skip unchanged files automatically

### 4. **Continuous Metadata Updates**
- **Current**: Metadata generated at end (Step 6.5)
- **New**: Each step (1-6) updates `layers/kt-app/metadata.json` with file hashes and timestamps
- **Benefit**: Step 7 just generates public deployment file, not tracking metadata

### 5. **Classification Before Extraction**
- **Current**: Extract images blindly from multi-page PDF
- **New**: Step 2 analyzes single-page PDFs, builds structure.json mapping pages to cards
- **Benefit**: Step 3 knows exactly which pages are fronts/backs/multi-card operatives

### 6. **File Naming Convention**
- **Current**: `page_0.pdf`, `page_1.pdf` (no context)
- **New**: `{team}-datacards-page_0.pdf`, `{team}-faction-rules-page_0.pdf` (clear source)
- **Benefit**: Easier debugging, clear which source PDF each page came from

### Visual Flow Comparison

**Current (Broken):**
```
input/*.pdf 
  → processed/{team}-datacards.pdf (multi-page)
    → output_v2/ cards (direct extraction)
      → tts_objects/ (NO STATS!)
        → extract_statlines.py
          → embed_datacard_stats.py (patch after generation)
```

**New (Logical):**
```
input/*.pdf
  → layers/kt-app/processed/{team}-datacards.pdf
    → layers/kt-app/extracted/{team}/cards/{team}-datacards-page_0.pdf (single pages)
      → layers/kt-app/classified/{team}/structure.json (analyze structure)
        → output_v2/{team}/statlines/roster.json (EXTRACT STATS EARLY)
          → output_v2/{team}/cards/*.jpg (extract cards)
            → tts_objects/{team}/*.json (WITH STATS EMBEDDED!)
```

---

## Current State Analysis

### Current Directory Structure
```
script/
├── run_pipeline.py                    # Main orchestrator
├── process_pdfs.py                    # Step 1: PDF identification
├── extract_statlines.py               # Step 5.4: Extract stats from PDFs
├── embed_datacard_stats.py            # Step 5.5: Embed stats into TTS cards
├── generate_team_tokens.py            # Token generation (manual)
├── generate_tts_metadata.py           # Metadata generation
├── generate_metadata.py               # Legacy metadata
├── generate_urls.py                   # URL generation
├── generate_tts_objects.py            # TTS object wrapper
├── generate_display_table.py          # Display table generation
├── update_bag_from_tts_objects.py     # Utility script
├── src/
│   ├── pipeline.py                    # DatacardPipeline class
│   ├── processors/                    # 10+ processor modules
│   ├── generators/                    # 3 generator modules
│   └── models/                        # Data models
└── tools/                             # Utility scripts

processed/                             # Intermediate artifacts
├── {team}/                           
│   ├── {team}-datacards.pdf          # Processed PDFs
│   └── {team}-faction-rules.pdf
└── extracted-tokens/{team}/*.png     # Token images

metadata/{team}/                       # Team-specific metadata
└── extraction_metadata.json          # Legacy extraction data

tts_objects/{team}/                    # TTS output
├── {Team Name} Cards.json
└── tokens/*.json

output_v2/{faction}/{team}/            # V2 output structure
├── cards/*.jpg
├── tokens/*.png
└── statlines/roster.json
```

### Current Pipeline Flow
1. **Process** (`process_pdfs.py`): Identify and organize raw PDFs into `processed/`
2. **Extract** (ImageExtractor): Extract cards from PDFs to `output_v2/{faction}/{team}/cards/`
3. **Backsides** (BacksideProcessor): Add default backsides
4. **Box Textures** (BoxTextureProcessor): Generate cardbox textures
5. **URLs** (URLGenerator): Generate V2 URLs JSON
6. **TTS Objects** (TTSGenerator): Generate TTS JSON objects
7. **Embed Tokens** (TokenIntegrator): Package and embed ready tokens
8. **Extract Statlines** (`extract_statlines.py`): Extract stats from datacards PDFs
9. **Embed Stats** (`embed_datacard_stats.py`): Inject stats into TTS cards
10. **Metadata** (`generate_tts_metadata.py`): Generate deployment metadata

---

## Problems with Current Architecture

### 1. **Inconsistent Artifact Locations**
- `processed/` - Some intermediate files
- `metadata/` - Legacy metadata (barely used)
- `tts_objects/` - Final TTS output
- Mixed responsibility: some files are intermediate, others are final

### 2. **Multiple Metadata Formats**
- `metadata/{team}/extraction_metadata.json` - Legacy, barely used
- `output_v2/tts-card-boxes.json` - Card box URLs
- `output_v2/tts-metadata.json` - Combined cards + tokens with timestamps
- `output_v2/{faction}/{team}/statlines/roster.json` - Statline data
- No unified change detection or hash tracking

### 3. **Illogical Step Ordering**
- Tokens embedded (5.25) BEFORE statlines extracted (5.4)
- Statlines extracted (5.4) BEFORE stats embedded (5.5)
- TTS objects generated (5) before they have stats (5.5)
- Box textures (3.5) done before we know what cards exist

### 4. **Redundant Processing**
- Cards extracted twice in some flows
- Metadata generated multiple times
- No hash-based change detection except in warcom Step 5

### 5. **Scattered Logic**
- Pipeline logic split between `run_pipeline.py`, `script/src/pipeline.py`, and individual scripts
- Subprocess calls instead of proper module integration
- No clear separation of concerns

---

## Proposed Structure

### New Directory Layout
```
pipelines/kt-app/
├── steps/
│   ├── 1_process_pdfs.py              # Identify & organize raw PDFs
│   ├── 2_classify_structure.py        # Analyze PDF content structure
│   ├── 3_extract_statlines.py         # Extract stats from PDFs
│   ├── 4_extract_cards.py             # Extract card images
│   ├── 5_extract_tokens.py            # Extract & process tokens
│   ├── 6_generate_tts_objects.py      # Build TTS JSON with stats
│   └── 7_generate_deployment_metadata.py  # Public deployment metadata
├── docs/
│   ├── PIPELINE_OVERVIEW.md
│   ├── STEP_1_PROCESS.md
│   ├── STEP_2_CLASSIFICATION.md
│   ├── STEP_3_STATLINES.md
│   ├── STEP_4_CARDS.md
│   ├── STEP_5_TOKENS.md
│   ├── STEP_6_TTS_GENERATION.md
│   └── STEP_7_DEPLOYMENT.md
└── run_kt_app_pipeline.py             # Main orchestrator

layers/kt-app/                          # ALL intermediate artifacts
├── processed/{team}/                   # Step 1 output
│   ├── {team}-datacards.pdf
│   └── {team}-faction-rules.pdf
├── extracted/{team}/                   # Step 1 page splits
│   └── cards/
│       ├── {team}-datacards-page_0.pdf    # Prefixed with source PDF
│       ├── {team}-datacards-page_1.pdf
│       ├── {team}-faction-rules-page_0.pdf
│       └── ...
├── classified/{team}/                  # Step 2 output
│   └── structure.json                 # Card combinations, pairs, etc.
└── metadata.json                       # Hash tracking (updated by ALL steps)

output_v3/{faction}/{team}/             # Final output (v3 for dev validation)
├── cards/*.jpg                         # Final cards with backsides
├── tokens/*.png                        # Final processed tokens
└── statlines/roster.json               # Extracted statlines

tts_objects_v3/{team}/                  # TTS JSON output (v3 for dev)
└── {Team Name} Cards.json              # With embedded stats

config/                                 # Config (unchanged)
input/                                  # Raw PDFs (unchanged)
```

**Note**: Using `output_v3/` and `tts_objects_v3/` during development to validate against existing `output_v2/`.

### Unified Metadata Format

**Single file**: `layers/kt-app/metadata.json`

```json
{
  "pipeline_version": "2.0",
  "last_full_run": "2026-05-02T12:00:00Z",
  "teams": {
    "kasrkin": {
      "canonical_name": "Kasrkin",
      "faction": "imperium",
      "steps": {
        "1_process": {
          "outputs": {
            "kasrkin-datacards.pdf": {
              "path": "layers/kt-app/processed/kasrkin/kasrkin-datacards.pdf",
              "hash": "abc123...",
              "modified": "2026-05-02T11:00:00Z"
            }
          },
          "completed": "2026-05-02T11:00:00Z"
        },
        "2_classify": {
          "outputs": {
            "structure.json": {
              "path": "layers/kt-app/classified/kasrkin/structure.json",
              "hash": "def456...",
              "modified": "2026-05-02T11:01:00Z"
            }
          },
          "card_count": 18,
          "front_back_pairs": 9,
          "completed": "2026-05-02T11:01:00Z"
        },
        "3_extract_cards": {
          "outputs": {
            "kasrkin-kasrkin-sergeant.jpg": {
              "path": "output_v2/imperium/kasrkin/cards/kasrkin-kasrkin-sergeant.jpg",
              "hash": "ghi789...",
              "modified": "2026-05-02T11:02:00Z",
              "url": "https://raw.githubusercontent.com/.../kasrkin-kasrkin-sergeant.jpg"
            }
          },
          "completed": "2026-05-02T11:02:00Z"
        },
        "4_extract_tokens": {
          "outputs": {},
          "skipped": "tokens_ready: true (locked)",
          "completed": "2026-05-02T11:03:00Z"
        },
        "5_extract_statlines": {
          "outputs": {
            "roster.json": {
              "path": "output_v2/imperium/kasrkin/statlines/roster.json",
              "hash": "jkl012...",
              "modified": "2026-05-02T11:04:00Z",
              "operative_count": 9
            }
          },
          "completed": "2026-05-02T11:04:00Z"
        },
        "6_generate_tts": {
          "outputs": {
            "Kasrkin Cards.json": {
              "path": "tts_objects/kasrkin/Kasrkin Cards.json",
              "hash": "mno345...",
              "modified": "2026-05-02T11:05:00Z",
              "url": "https://raw.githubusercontent.com/.../Kasrkin%20Cards.json",
              "card_count": 18,
              "has_stats": true
            }
          },
          "completed": "2026-05-02T11:05:00Z"
        }
      }
    }
  }
}
```

**Key Features:**
- Single source of truth for ALL pipeline artifacts
- Content hashes for every file (skip unchanged)
- Timestamps for cache busting
- URLs for deployment
- Step completion tracking
- Hierarchical structure (team → step → outputs)

---

## New Pipeline Flow

**Key Insight**: Metadata tracking happens **continuously** in Steps 1-6, updating `layers/kt-app/metadata.json` with hashes. Step 7 just generates the public deployment file.

### Step 1: Process PDFs
**Script**: `pipelines/kt-app/steps/1_process_pdfs.py`  
**Input**: `input/*.pdf` (raw PDFs)  
**Output**: 
- `layers/kt-app/processed/{team}/{team}-*.pdf` (organized PDFs)
- `layers/kt-app/extracted/{team}/cards/page_N.pdf` (single-page PDFs)  
**Function**: 
- Identify team, organize by type (datacards/faction-rules)
- Split datacards PDF intoextracted/{team}/cards/page_N.pdf` (single-page PDFs)  
**Output**: `layers/kt-app/classified/{team}/structure.json`  
**Function**:
- Analyze each page PDF (text extraction)
- Identify front/back card pairs (fronts have stats, backs have abilities)
- Detect multi-card operatives (e.g., Gore Tank, Big Mek)
- Identify card types (operative, equipment, rules, etc.)
- Build extraction plan with page-to-card mappings

**Example structure.json**:
```json
{
  "team": "kasrkin",
  "total_pages": 18,
  "cards": [
    {
      "card_id": "kasrkin-sergeant",
      "operative_name": "Kasrkin Sergeant",
      "front_page_pdf": "kasrkin-datacards-page_0.pdf",
      "back_page_pdf": "kasrkin-datacards-page_1.pdf",
      "type": "operative",
      "has_stats": true
    },
    {
      "card_id": "kasrkin-trooper",
      "operative_name": "Kasrkin Trooper",
      "front_page_pdf": "kasrkin-datacards-page_2.pdf",
      "back_page_pdf": "kasrkin-datacards-page_3.pdf",
      "type": "operative",
      "has_stats": true
    }
  ],
  "faction_rules": [
    {
      "page_pdf": "kasrkin-faction-rules-page_0.pdf"
    }
  ]
}
```

### Step 3: Extract Statlines
**Script**: `pipelines/kt-app/steps/3_extract_statlines.py`  
**Input**: 
- `layers/kt-app/extracted/{team}/cards/{team}-datacards-page_N.pdf` (single-page PDFs)
- `layers/kt-app/extracted/{team}/cards/{team}-faction-rules-page_N.pdf` (faction rules)
- `layers/kt-app/classified/{team}/structure.json` (to know which are fronts/backs)  
**Output**: `output_v2/{faction}/{team}/statlines/roster.json`  
**Function**:
- Read classification to identify front pages with stats
- Extract operative stats (APL, Move, Save, Wounds) from front page PDFs
- Extract weapons (ATK, HIT, DMG, WR) from front pages
- Extract abilities and unique actions from back page PDFs
- Extract faction rules from faction-rules page PDFs
- Coordinate-based extraction from single-page PDFs (much easier than multi-page!)
- Update `layers/kt-app/metadata.json` with hash of roster.json
- **Moved earlier**: Can extract stats immediately after classification, don't need card images

### Step 4: Extract Cards
**Script**: `pipelines/kt-app/steps/4_extract_cards.py`  
**Input**: 
- `layers/kt-app/extracted/{team}/cards/{team}-datacards-page_N.pdf` (single-page PDFs)
- `layers/kt-app/classified/{team}/structure.json` (card mappings)  
**Output**: `output_v2/{faction}/{team}/cards/*.jpg` (properly named)  
**Function**:
- Read classification plan to know which pages are which cards
- Extract each page PDF to JPG with proper naming (e.g., `kasrkin-kasrkin-sergeant-front.jpg`)
- Apply backsides based on card type from classification
- Generate box textures
- Add rounded corners
- Update `layers/kt-app/metadata.json` with hashes for all card images
- Similar to warcom's classify → output flow

### Step 5: Extract Tokens
**Script**: `pipelines/kt-app/steps/5_extract_tokens.py`  
**Input**: 
- `processed/extracted-tokens/{team}/*.png` (from manual extraction)
- Team config (tokens_ready flag)  
**Output**: `output_v2/{faction}/{team}/tokens/*.png`  
**Function**:
- Skip if `tokens_ready: true` (locked teams)
- Process raw tokens (transparency, shapes)
- Generate token bags
- Update `layers/kt-app/metadata.json` with hashes for all token images

### Step 6: Generate TTS Objects
**Script**: `pipelines/kt-app/steps/6_generate_tts_objects.py`  
**Input**:
- `output_v2/{faction}/{team}/cards/*.jpg`
- `output_v2/{faction}/{team}/tokens/*.png`
- `output_v2/{faction}/{team}/statlines/roster.json`  
**Output**: `tts_objects/{team}/*.json`  
**Function**:
- Generate TTS card box JSON
- Embed operative stats from roster.json (GMNotes + Lua)
- Inject faction rules (Chapter Tactics, etc.)
- Inject operative counters (Gore Tank)
- Embed token bags (for tokens_ready teams)
- Use hash-based change detection (like warcom Step 5)
- Update `layers/kt-app/metadata.json` with hashes for TTS objects

### Step 7: Generate Deployment Metadata
**Script**: `pipelines/kt-app/steps/7_generate_deployment_metadata.py`  
**Input**: `layers/kt-app/metadata.json` (hash tracking from all steps)  
**Output**: `output_v2/tts-metadata.json` (public deployment file)  
**Function**:
- Read `layers/kt-app/metadata.json` (internal tracking)
- Generate `output_v2/tts-metadata.json` for TTS consumption (URLs + timestamps)
- Format: `{"team": "kasrkin", "name": "Kasrkin", "cards_url": "...", "cards_last_modified": "2026-05-02T12:00:00", ...}`
- Use file modification times from metadata for cache busting
- Validate all required files exist
- **Note**: This is NOT metadata generation for tracking - that happens during Steps 1-6

---

## Refactoring Steps

### Phase 1: Create New Structure
1. Create `pipelines/kt-app/` directory
2. Create `pipelines/kt-app/steps/` directory
3. Create `pipelines/kt-app/docs/` directory
4. Create `layers/kt-app/` directory structure

### Phase 2: Extract & Refactor Step 1 (Process PDFs)
**Source**: 
- `script/process_pdfs.py`
- `script/src/processors/pdf_processor.py`
- `script/src/processors/team_identifier.py`

**Target**: `pipelines/kt-app/steps/1_ (organized PDFs)
- **NEW**: Split datacards PDF into single-page PDFs → `layers/kt-app/extracted/{team}/cards/page_N.pdf`
- Use PyMuPDF to extract pages: `doc[page_num]` → save to new PDF
- Update metadata with hashes for both processed and extracted fil
**Changes**:
- Self-contained module (no src/ imports)
- Output to `layers/kt-app/processed/`
- Update metadata with hashes
- CLI interface matching warcom style

### Phase 3: Create Step 2 (Classification)
**New Script**: `pipelines/kt-app/steps/2_classify_structure.py`
Read single-page PDFs from `layers/kt-app/extracted/{team}/cards/`
- Extract text from each page using PyMuPDF
- Identify fronts (have "NAME", "HIT", "WR" header keywords from statline extraction)
- Identify backs (pair with previous front, contain abilities)
- Detect multi-card operatives (multiple fronts with same operative name)
- Build structure.json mapping page PDFs to card IDs and names
- Similar to warcom's `3_card_classification.py` but simpler (already single pages)
- Build extraction plan in JSON
- No image extraction, just analysis

### Phase 4: Extract & Refactor Step 3 (Extract Cards)
**Source**:
- `script/src/processors/image_extractor.py`
- `script/src/processors/backside_processor.py`
- `script/src/processors/box_texture_processor.py`

### Phase 4: Create Step 3 (Extract Statlines)
**Source**: `script/extract_statlines.py`

**Target**: `pipelines/kt-app/steps/3_extract_statlines.py`

**Changes**:
- **Moved earlier**: Runs after classification (Step 2), before card extraction (Step 4)
- Read structure.json to get front/back page mappings
- Process single-page PDFs from `layers/kt-app/extracted/{team}/cards/`
- Coordinate-based extraction is simpler with single-page PDFs
- Update `layers/kt-app/metadata.json` with hash of roster.json
- Self-contained module

### Phase 5: Extract & Refactor Step 4 (Extract Cards)
**Source**:
- `script/src/processors/image_extractor.py`
- `script/src/processors/backside_processor.py`
- `script/src/processors/box_texture_processor.py`

**Target**: `pipelines/kt-app/steps/4_extract_cards.py`

**Changes**:
- Read structure.json to get page-to-card mappings
- Load single-page PDFs (much simpler than multi-page extraction!)
- Convert PDF page to image → save as `{team}-{card_id}-front.jpg`
- Apply backsides based on card type
- Generate box textures
- Self-contained (inline all logic)
- Hash-based skip for unchanged cards
- Update `layers/kt-app/metadata.json`

### Phase 6: Extract & Refactor Step 5 (Extract Tokens)
**Source**:
- `script/generate_team_tokens.py`
- `script/tools/extract_tokens.py`
- `script/src/processors/token_integration.py`

**Target**: `pipelines/kt-app/steps/5_extract_tokens.py`

**Changes**:
- Respect `tokens_ready` lock
- Process from `processed/extracted-tokens/`
- Output to `output_v2/{faction}/{team}/tokens/`
- Update `layers/kt-app/metadata.json` with token hashes

### Phase 7: Extract & Refactor Step 6 (Generate TTS Objects)
**Source**:
- `script/embed_datacard_stats.py`
- `script/generate_tts_objects.py`
- `script/src/generators/tts_generator.py`

**Target**: `pipelines/kt-app/steps/6_generate_tts_objects.py`

**Changes**:
- Combine generation + stat embedding into single step
- Use warcom Step 5 as model (has hash-based change detection)
- Read from Step 3's roster.json (statlines now extracted earlier)
- Inject stats during generation, not after
- Update `layers/kt-app/metadata.json` with TTS object hashes
- Self-contained module

### Phase 8: Create Step 7 (Generate Deployment Metadata)
**Source**:
- `script/generate_tts_metadata.py`
- `script/generate_urls.py`

**Target**: `pipelines/kt-app/steps/7_generate_deployment_metadata.py`

**Changes**:
- **Not** for tracking metadata - that's in `layers/kt-app/metadata.json` updated by Steps 1-6
- This generates the **public deployment file**: `output_v2/tts-metadata.json`
- Format for TTS consumption (team name, URLs, timestamps)
- Read hashes and timestamps from `layers/kt-app/metadata.json`
- Validate all required files exist
- No `script/generate_metadata.py` - that's legacy, replaced by continuous metadata updates

### Phase 9: Create Main Orchestrator
**Target**: `pipelines/kt-app/run_kt_app_pipeline.py`

**Features**:
- CLI like warcom: `--step 1`, `--step all`, `--teams kasrkin,blooded`
- Load and update `layers/kt-app/metadata.json`
- Run steps in order
- Skip unchanged files based on hashes
- Progress reporting

### Phase 10: Documentation
Create docs in `pipelines/kt-app/docs/`:
- `PIPELINE_OVERVIEW.md`
- `STEP_1_PROCESS.md` through `STEP_7_METADATA.md`
- Migration guide from old pipeline

### Phase 11: Deprecation
1. Update main `script/run_pipeline.py` to show deprecation warning
2. Add redirect: `python script/run_pipeline.py` → `python pipelines/kt-app/run_kt_app_pipeline.py`
3. After validation period, remove old `script/` files

---

## Migration Strategy

### Gradual Migration
1. Build new pipeline alongside old one
2. Test with single team (kasrkin)
3. Compare outputs (should be identical)
4. Expand to all teams
5. Switch to new pipeline as default
6. Deprecate old pipeline

### Data Migration
```bash
# Move processed PDFs
mv processed/{team}/* layers/kt-app/processed/{team}/

# Move extracted tokens (keep location for now)
# processed/extracted-tokens/ stays for manual extraction

# Metadata: generate fresh from scratch
python pipelines/kt-app/steps/7_generate_metadata.py --rebuild
```

---

## Benefits of Refactoring

1. **Clear Step Progression**: Numbered steps with logical dependencies
2. **Unified Metadata**: Single JSON file with hashes and timestamps
3. **Change Detection**: Skip unchanged files automatically
4. **Better Organization**: All intermediate files in `layers/kt-app/`
5. **Self-Contained Steps**: Each step is independent, no complex src/ dependencies
6. **Consistent with Warcom**: Similar structure and patterns
7. **Easier Debugging**: Clear separation of concerns
8. **Better Documentation**: Each step has detailed docs

---

## Success Criteria

- [ ] All 7 steps created and working
- [ ] Main orchestrator functional
- [ ] Metadata system with hashes working
- [ ] Full pipeline run produces identical output to old pipeline
- [ ] Documentation complete
- [ ] Old pipeline deprecated

---

**Next Actions**: Review this plan, then begin Phase 1 (create structure)
