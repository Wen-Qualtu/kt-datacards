# Warcom Pipeline - Design Decisions and Architecture

## Overview

The Warcom pipeline is a modular data processing system designed to extract, classify, and organize Kill Team datacards from official Warhammer Community PDF documents. The pipeline is built with independence and flexibility in mind - each step can be run standalone or as part of the complete workflow, with support for processing all teams or selected teams only.

## Architecture Principles

### 1. Step Independence
Each pipeline step is designed to be independently executable:
- Steps can run individually without requiring prior steps to have completed
- Each step has clearly defined inputs and outputs
- Steps read from and write to predictable directory structures
- Failed steps don't block subsequent steps for other teams

### 2. Team-Level Granularity
All processing supports team-level filtering:
- `--all` flag processes all available teams
- `--teams <team1> <team2>` processes specific teams
- Steps automatically discover available teams from their input directories
- Teams processed successfully are tracked for downstream steps

### 3. Idempotent Operations
Steps can be re-run safely:
- Existing outputs can be overwritten or skipped based on flags
- No side effects from running the same step multiple times
- Clear logging of what was processed vs skipped

## Pipeline Steps

### Step 1: Website Scraping and PDF Download
**Script:** `steps/1_scrape_warcom_killteam_downloads.py`

**Purpose:** Download Kill Team rules PDFs from Warhammer Community website.

**Input:**
- Website URL: `https://www.warhammer-community.com/en-gb/downloads/kill-team/`

**Output:**
- `layers/warcom/staging/{team}/*.pdf` - Downloaded PDF files organized by team

**Logic:**
1. Scrape the Warhammer Community downloads page
2. Extract PDF download links for Kill Team rules
3. Parse team names from the page structure
4. Download PDFs to staging directory organized by team
5. Handle URL redirects and validation

**Design Notes:**
- This step is intentionally "messy" as web scraping often requires site-specific logic
- Logic focuses on getting correct URLs even if code isn't elegant
- No team filtering at this stage - downloads all available PDFs
- Works as-is and doesn't require refactoring

---

### Step 2: Card Extraction
**Script:** `steps/2_card_extractor.py`

**Purpose:** Extract individual card images from multi-card PDF pages using template-based coordinates.

**Input:**
- `layers/warcom/staging/{team}/*.pdf` - Source PDF files
- `config/pipelines/warcom/card_templates.json` - Card coordinate templates

**Output:**
- `layers/warcom/extracted/{team}/cards/page{XX}_card{Y}.pdf` - Individual card PDFs
- `layers/archive/{team}/warcom/*.pdf` - Archived source PDFs (after successful extraction)

**Card Naming Convention:**
```
page{XX}_card{Y}.pdf
```
- `{XX}` - Zero-padded page number (e.g., 01, 02, 15)
- `{Y}` - Card number on the page (1, 2, 3, or 4)

**Processing Flow:**

```
For each PDF file:
  For each page:
    1. Determine page type (layout pattern)
    2. Look up template for that page type
    3. Extract cards using template coordinates
    4. Save each card with sequential naming
    5. Maintain extraction order for downstream processing
```

**Page Type Detection:**
The pipeline uses template matching to identify:
- Portrait single card pages
- Portrait multi-card pages (2-4 cards)
- Landscape single card pages
- Landscape multi-card pages

**Template Structure:**
```json
{
  "portrait_2x2": {
    "layout": "2x2 grid",
    "coordinates": [
      {"card": 1, "x": 0, "y": 0, "width": 50, "height": 50},
      {"card": 2, "x": 50, "y": 0, "width": 50, "height": 50},
      ...
    ]
  }
}
```

**Critical Requirements:**
- **Maintain extraction order** - Cards numbered sequentially as they appear on pages
- Card numbering must be consistent for classification step
- Original page number preserved in filename for traceability

**Design Decisions:**
- Use PDF format for extracted cards (not images) to maintain quality
- Template-based approach allows easy adjustment of coordinates
- Archive source PDFs only after successful extraction

---

### Step 3: Card Classification and Organization
**Script:** `steps/3_card_classification.py`

**Purpose:** Identify team, type, and name of each card, then organize into proper output structure.

**Input:**
- `layers/warcom/extracted/{team}/cards/page{XX}_card{Y}.pdf`

**Output:**
- `output_v2/{faction}/{team}/{type}/{name}.png` - Final organized card images

**Processing Flow:**

```
For each card PDF:
  1. Convert to image for OCR
  2. Extract text content
  3. Classify card TYPE
  4. Extract card NAME
  5. Determine TEAM (from directory structure)
  6. Convert to PNG with proper formatting
  7. Save to final location
```

#### Type Classification Logic

**Order of type detection:**

1. **Skip "Notes" cards**
   - Extract all text from card
   - If the only text content is "notes" (case-insensitive) → Skip card entirely
   - Purpose: Filter out blank note-taking cards

2. **Landscape cards are ALWAYS datacards**
   - Check card orientation (width > height)
   - If landscape → Type = `datacards`
   - No further type checking needed

3. **Check for "Operative Selection" type**
   - Read line 1 (and line 2 if needed)
   - Pattern: `{TEAM_NAME} KILL TEAM`
   - Read next line
   - If contains `ARCHETYPES` → Type = `operative-selection`

4. **Default type from line 2**
   - For all other portrait cards
   - Line 2 always contains the card type
   - Extract and normalize (lowercase, remove spaces)

**Supported Types:**
- `datacards` - Operative stat cards (landscape)
- `operative-selection` - Team roster/archetype cards
- `tac-ops` - Tactical operation cards
- `rare-equipment` - Special equipment cards
- `strategic-asset` - Strategic assets
- `deployment` - Deployment maps
- `token-guide` - Token reference cards
- `spec-ops` - Special operation cards

#### Name Extraction Logic

Name extraction varies by card type:

**Datacards (landscape):**
- Name is in the first text block (usually top-left)
- Extract line 1 of the card
- Clean and normalize

**Operative Selection:**
- Hardcoded name: `"operative-selection"`
- These cards don't have unique names per se
- Used for team composition rules

**All Other Types:**
- Name is in row 3 of the card
- Line 1: Card series/category
- Line 2: Card type
- Line 3: Card name ← Extract this

**Name Normalization:**
- Convert to lowercase
- Replace spaces with hyphens
- Remove special characters
- Example: "Vox Operative" → "vox-operative"

#### Team Detection

- Team name extracted from directory path
- Path pattern: `layers/warcom/extracted/{team}/cards/`
- Team name normalized to match output structure

#### Output Organization

Final structure:
```
output_v2/
  {faction}/          # imperium, chaos, xenos
    {team}/           # e.g., phobos-strike-team
      datacards/
        {name}.png
      operative-selection/
        operative-selection.png
      tac-ops/
        {name}.png
      rare-equipment/
        {name}.png
      ...
```

**Design Decisions:**
- OCR performed on PNG conversion of PDF for accuracy
- Line-based text extraction (not region-based) for consistency
- Type detection order matters - most specific rules first
- Maintain team directory structure from extraction step
- PNG output with optional processing (rounded corners, etc.)

---

### Step 4: Token Extraction (To Be Developed)
**Script:** `steps/4_token_extraction.py`

**Purpose:** Extract individual token images from token guide cards with shape classification.

**Input:**
- Token guide cards identified from step 3: `output_v2/{faction}/{team}/token-guide/*.png`

**Output:**
- `output_v2/{faction}/{team}/tokens/{name}_{shape}.png` - Individual token images
- Token metadata JSON with shapes, types, and coordinates

**Processing Flow:**

```
For each token-guide card:
  1. Extract token text labels (names)
  2. Determine token type (token vs marker)
  3. Detect token contours/boundaries
  4. Classify token shape
  5. Apply shape-specific template for uniform cutting
  6. Match tokens to names
  7. Output individual token images
```

#### Token Name Extraction

- Use OCR to extract text labels from token guide
- Parse format: `"{Name} Token"` or `"{Name} Marker"`
- Remove `"Token"` / `"Marker"` postfix from name
- Store postfix as `type` field (`"token"` or `"marker"`)

**Example:**
- Text: "Concealed Token" → Name: "Concealed", Type: "token"
- Text: "Objective Marker" → Name: "Objective", Type: "marker"

#### Shape Classification

**Detection order** (may be adjusted for better resolution):

1. **Perfect Circle** → Shape: `"round"`
   - Calculate circularity ratio: `4π × area / perimeter²`
   - If ratio > 0.95 → Perfect circle
   - Most common for many tokens

2. **Octagon** → Shape: `"octagon"`
   - Count vertices/corners in contour
   - If 8 vertices with roughly equal angles → Octagon
   - Less common but distinctive

3. **Diamond (Rotated Square)** → Shape: `"diamond"`
   - 4 vertices at ~45° rotation
   - Square oriented on corner
   - Width ≈ Height

4. **Operative Shape** → Shape: `"operative"`
   - Default for complex/irregular shapes
   - Typically elongated hexagon or modified circle
   - Used for operative activation tokens

**Shape-Specific Templates:**

Each shape has a cutting template to ensure uniform output:
- `round`: Circular mask
- `octagon`: 8-sided polygon mask
- `diamond`: 45° rotated square mask
- `operative`: Custom mask following operative token shape

Templates ensure:
- Consistent sizing
- Clean edges
- Proper aspect ratios
- Transparent backgrounds where needed

#### Token-to-Name Matching

- Use spatial positioning to match extracted tokens to text labels
- Typically tokens arranged in a grid with labels nearby
- Match based on proximity (nearest label to token center)
- Validate all tokens have matching names

**Design Considerations:**
- Shape classification order can be adjusted based on accuracy testing
- Template-based cutting ensures consistent output
- Shape metadata preserved for downstream TTS object generation
- Handle edge cases (overlapping tokens, unclear boundaries)

---

### Step 5: Metadata Generation (To Be Developed)
**Script:** `steps/5_metadata_generator.py`

**Purpose:** Combine all extracted assets (cards, tokens) per team into a structured metadata JSON file that references raw image URLs in the repository.

**Input:**
- All processed cards: `output_v2/{faction}/{team}/{type}/*.png`
- All extracted tokens: `output_v2/{faction}/{team}/tokens/*.png`
- Team configuration: `config/teams/{team}/`

**Output:**
- `output_v2/{faction}/{team}/cardbox.json` - Team card box metadata
- References GitHub raw content URLs for all images

**Metadata Structure:**

```json
{
  "team": "phobos-strike-team",
  "faction": "imperium",
  "display_name": "Phobos Strike Team",
  "datacards": [
    {
      "name": "intercessor",
      "display_name": "Intercessor",
      "image_url": "https://raw.githubusercontent.com/.../phobos-strike-team/datacards/intercessor.png"
    }
  ],
  "tac_ops": [...],
  "rare_equipment": [...],
  "tokens": [
    {
      "name": "concealed",
      "type": "token",
      "shape": "round",
      "image_url": "https://raw.githubusercontent.com/.../tokens/concealed_round.png"
    }
  ],
  "operative_selection": {
    "image_url": "..."
  }
}
```

**Processing Logic:**

1. Discover all teams with processed outputs
2. For each team:
   - Enumerate all card types and images
   - Enumerate all tokens with shapes
   - Generate GitHub raw URLs for each image
   - Load team display names from config
   - Combine into cardbox JSON structure
3. Write cardbox.json to team output directory
4. Validate all referenced images exist

**URL Generation:**
- Base URL: `https://raw.githubusercontent.com/{owner}/{repo}/{branch}/output_v2/`
- Full path: `{base_url}/{faction}/{team}/{type}/{filename}`
- URLs must be publicly accessible

**Design Decisions:**
- Single JSON file per team for easy consumption
- URLs point to repository to avoid hosting separately
- Metadata includes shape info for proper TTS rendering
- Display names separated from file names for presentation

---

### Step 6: TTS Object Generation (To Be Developed)
**Script:** `steps/6_tts_generator.py`

**Purpose:** Generate Tabletop Simulator (TTS) object files for each team based on cardbox metadata.

**Input:**
- `output_v2/{faction}/{team}/cardbox.json` - Team metadata
- TTS templates: `config/defaults/tts-*/*.json`

**Output:**
- `tts_objects/{team}/deck.json` - TTS deck object
- `tts_objects/{team}/tokens.json` - TTS token bag object
- TTS script files for custom behaviors

**Processing Logic:**

1. Load cardbox metadata for team
2. Generate TTS deck object:
   - Create card entries with image URLs
   - Configure deck properties (size, back image, etc.)
   - Apply custom scripts for card interactions
3. Generate TTS token bag:
   - Create token objects with proper shapes
   - Set model/mesh based on shape classification
   - Configure physics properties
4. Apply team-specific customizations from config
5. Write TTS object JSON files

**Design Decisions:**
- Separate objects for cards and tokens
- Use metadata URLs directly in TTS objects
- Template-based generation for consistency
- Custom scripts for advanced interactions

---

## Directory Structure

```
pipelines/warcom/
  ├── pdf_process_pipeline.py        # Main orchestrator
  ├── steps/
  │   ├── 1_scrape_warcom_killteam_downloads.py
  │   ├── 2_card_extractor.py
  │   ├── 3_card_classification.py
  │   ├── 4_token_extraction.py      # To be developed
  │   ├── 5_metadata_generator.py    # To be developed
  │   └── 6_tts_generator.py         # To be developed
  ├── DESIGN.md                      # This document
  └── README.md                      # User guide

config/pipelines/warcom/
  └── card_templates.json            # Card extraction templates

layers/warcom/
  ├── staging/{team}/*.pdf           # Downloaded PDFs
  └── extracted/{team}/cards/*.pdf   # Extracted cards

layers/archive/{team}/warcom/*.pdf  # Archived source PDFs

output_v2/
  └── {faction}/{team}/
      ├── cardbox.json              # Team metadata
      ├── datacards/*.png
      ├── tac-ops/*.png
      ├── tokens/*.png
      └── ...

tts_objects/{team}/
  ├── deck.json
  └── tokens.json
```

## Pipeline Orchestration

### Main Script: `pdf_process_pipeline.py`

**Purpose:** Coordinate execution of all pipeline steps with flexible team selection.

**Usage Examples:**

```bash
# Run all steps for all teams
python pipelines/warcom/pdf_process_pipeline.py --all

# Run specific step for all teams
python pipelines/warcom/pdf_process_pipeline.py --step 2 --all

# Run specific step for specific teams
python pipelines/warcom/pdf_process_pipeline.py --step 3 --teams phobos-strike-team kommandos

# Run steps 1-3 for one team
python pipelines/warcom/pdf_process_pipeline.py --steps 1 2 3 --teams battleclade
```

**Key Features:**

1. **Step Chaining:**
   - Steps can pass successful team lists to subsequent steps
   - Failed teams don't block processing of other teams
   - Each step reports success/failure per team

2. **Dynamic Module Loading:**
   - Steps loaded at runtime using `importlib`
   - Allows easy addition of new steps without modifying orchestrator
   - Each step module must have a `run()` function

3. **Logging and Reporting:**
   - Detailed logging per step
   - Summary reports after each step
   - Final pipeline summary with overall success/failure

4. **Error Handling:**
   - Per-team error isolation
   - Continue processing other teams on failure
   - Detailed error logs for debugging

---

## Key Design Decisions

### 1. Why Step Independence?

**Problem:** Long-running pipelines often fail partway through, requiring complete re-runs.

**Solution:** Independent steps allow:
- Debugging specific steps without running entire pipeline
- Re-running failed steps without re-processing successful ones
- Development and testing of new steps in isolation
- Parallel development of different steps

### 2. Why Template-Based Card Extraction?

**Problem:** PDF cards have varying layouts, sizes, and positions.

**Solution:** Template system provides:
- Precise coordinate-based extraction
- Easy adjustment of coordinates without code changes
- Support for multiple page layouts
- Consistent extraction quality

**Alternative Considered:** Computer vision-based detection
- **Rejected because:** PDF parsing is more reliable and faster than image processing
- Templates are deterministic and don't require training data
- Coordinate-based approach works perfectly for standardized PDF layouts

### 3. Why Line-Based Type Classification?

**Problem:** Cards have varying layouts and visual styles.

**Solution:** Text line extraction is:
- Consistent across all card types
- Easy to understand and debug
- Reliable with OCR
- Works with standardized Warhammer card templates

**Key Insight:** Warhammer cards follow strict layout conventions:
- Type always on line 2 (portrait cards)
- Landscape cards are always datacards
- "ARCHETYPES" keyword reliably identifies operative-selection

### 4. Why Token Shape Classification?

**Problem:** TTS needs different 3D models for different token shapes.

**Solution:** Classify shapes during extraction:
- Enables correct TTS model selection
- Allows shape-specific cutting templates
- Improves visual quality in TTS
- Metadata preserved for rendering

### 5. Why Separate Archive Directory?

**Problem:** Need to preserve original PDFs but keep staging clean for re-runs.

**Solution:** Archive after successful extraction:
- Staging directory can be cleared for fresh downloads
- Archived PDFs serve as backup and audit trail
- Clear separation between "working" and "archived" data

---

## Data Flow Diagram

```
[Warhammer Community Website]
            ↓
    [Step 1: Scrape & Download]
            ↓
  layers/warcom/staging/{team}/*.pdf
            ↓
    [Step 2: Extract Cards]
            ↓                ↘
layers/warcom/extracted/      layers/archive/ (backup)
    {team}/cards/*.pdf
            ↓
    [Step 3: Classify Cards]
            ↓
  output_v2/{faction}/{team}/
       {type}/*.png
            ↓
    [Step 4: Extract Tokens]
            ↓
  output_v2/{faction}/{team}/
       tokens/*.png
            ↓
    [Step 5: Generate Metadata]
            ↓
  output_v2/{faction}/{team}/
       cardbox.json
            ↓
    [Step 6: Generate TTS Objects]
            ↓
  tts_objects/{team}/*.json
```

---

## Configuration Management

### Team Configuration
- **Location:** `config/teams/{team}/`
- **Purpose:** Team-specific overrides and metadata
- **Contents:** Display names, faction assignment, special rules

### Pipeline Configuration
- **Location:** `config/pipelines/warcom/`
- **Purpose:** Pipeline-wide settings
- **Contents:**
  - `card_templates.json` - Extraction coordinates
  - `sources.yaml` - PDF source URLs (future)

### Default Templates
- **Location:** `config/defaults/`
- **Purpose:** Default TTS object templates
- **Contents:** Deck backs, token templates, script templates

---

## Error Handling Strategy

### Per-Team Isolation
- Errors in one team don't stop processing of others
- Each team's processing is independent
- Failed teams logged and reported separately

### Validation Checkpoints
- Validate inputs before processing (file exists, readable, etc.)
- Validate outputs after processing (correct format, all cards extracted, etc.)
- Log validation failures with details

### Graceful Degradation
- Missing optional data doesn't fail the step
- Steps skip already-processed items (unless forced)
- Clear warnings for non-critical issues

---

## Future Enhancements

### Potential Improvements:

1. **Parallel Team Processing:**
   - Process multiple teams concurrently
   - Utilize multiple CPU cores
   - Requires thread-safe logging

2. **Incremental Processing:**
   - Only process new/changed PDFs
   - Track file modification times
   - Skip unchanged teams

3. **Quality Validation:**
   - Automated checks for extraction quality
   - OCR confidence scoring
   - Missing card detection

4. **Configuration UI:**
   - Web interface for template adjustment
   - Visual coordinate picking
   - Live preview of extraction

5. **Alternative Sources:**
   - Support for other PDF sources besides warcom
   - Plugin system for different extractors
   - Unified output format

---

## Testing Strategy

### Unit Tests
- Test individual functions (type classification, name extraction)
- Mock file I/O for speed
- Cover edge cases

### Integration Tests
- Test complete steps with sample PDFs
- Verify output directory structure
- Check file naming conventions

### End-to-End Tests
- Run full pipeline on small team subset
- Verify complete data flow
- Validate final TTS objects load in TTS

---

## Conclusion

The Warcom pipeline is designed with modularity, independence, and maintainability as core principles. Each step is self-contained and can be understood, tested, and modified independently. The template-based extraction and rule-based classification provide reliable, deterministic results while remaining flexible enough to accommodate new card types and formats.

The pipeline architecture supports both complete automated runs and targeted manual processing, making it suitable for initial bulk processing as well as ongoing maintenance and updates.
