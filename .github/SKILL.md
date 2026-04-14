---
description: DEPRECATED — use the focused skills in .github/skills/kt-datacards/ instead
tags: [kill-team, deprecated]
---

# kt-datacards Project Skill — DEPRECATED

This file has been replaced by three focused skills:

- [SKILL-project.md](skills/kt-datacards/SKILL-project.md) — Directory structure, critical rules, naming conventions, config system
- [SKILL-etl.md](skills/kt-datacards/SKILL-etl.md) — PDF extraction, statline parsing, token detection, pipeline steps
- [SKILL-tts.md](skills/kt-datacards/SKILL-tts.md) — TTS JSON structure, Lua scripts, hash/timestamp system, deployment

---

<!-- Original content preserved below for reference during transition -->


## When to Use This Skill

Use this skill when working on:
- Kill Team datacard PDF extraction and processing
- Tabletop Simulator (TTS) save file generation
- Token extraction from PDF marker/token guides
- Card image generation with statlines
- Team configuration and metadata management
- Pipeline orchestration and debugging
- TTS Lua script integration for stat loading

Do NOT use for:
- General Python project setup (use Python skills)
- Generic PDF processing (use PyMuPDF docs)
- Unrelated TTS modding projects

## Project Architecture

### Two Pipeline Systems

**kt-app pipeline** (PRIMARY - `script/`):
- Entry point: `script/run_pipeline.py` CLI
- Orchestrator: `script/src/pipeline.py`
- Numbered steps with parallel processing support
- Full team processing from PDF to TTS objects

**warcom pipeline** (LEGACY - `pipelines/warcom/steps/`):
- Numbered step files (1-9)
- Kept for reference and standalone tools
- ROSZ generation, web scraping utilities

### Directory Structure

```
input/                    # Raw PDF sources (datacards)
processed/{team}/         # Organized PDFs: {team}-datacards.pdf
output_v2/{faction}/      # Final extracted images & metadata
  imperium/
  chaos/
  xenos/
metadata/{team}/          # Per-team metadata JSONs
  card_index.json         # Card number → operative name mapping
  extraction_metadata.json # Extraction details (OFTEN MALFORMED - wrap in try/except)
  token_index.json        # Token inventory
tts_objects/{team}/       # TTS save JSON files (card boxes, token bags)
config/
  team-config.yaml        # Master team registry (canonical names, factions, aliases, tokens)
  team-guids.json         # TTS GUID mappings per team
  weapon_rules.json       # Weapon rule definitions with descriptions
  teams/{team}.yaml       # Individual team overrides
  defaults/               # Templates (box, card-backside, tts-image, tts-script, tts-token)
layers/                   # Image layers for card composition
archive/                  # Original processed PDFs
```

### Script Modules (`script/src/`)

```
pipeline.py               # Pipeline orchestrator with numbered steps
generators/               # Card/token image generation
managers/                 # Management utilities
models/                   # Data models/schemas
processors/               # Data processing
token_tools/              # Token-specific utilities
utils/                    # Common utilities
```

## Team Identification & Naming

**Critical Conventions:**

1. **Team slugs**: lowercase-hyphenated
   - Examples: `angels-of-death`, `corsair-voidscarred`, `tempestus-aquilons`

2. **Canonical names**: From `team-config.yaml`
   - Examples: "Angels of Death", "Corsair Voidscarred"

3. **Faction grouping**: `imperium`, `chaos`, `xenos`

4. **Name normalization** (`roster_slug()`):
   ```python
   re.sub(r"[^\x00-\x7f]", "", s)  # Strip non-ASCII
   ```
   - Handles: ô, â, ', ‑ (non-breaking hyphen)

5. **Card nickname matching**: Strip order prefix and wounds from TTS nickname
   - Format: `[FF5500]E[-] {8/8} Stalker Alpha`

## PDF Extraction Patterns

### Core Technology
- **PyMuPDF (fitz)** for text extraction and rendering
- Coordinate-based region extraction
- Multi-DPI rendering (150 DPI for detection, 300 DPI for final extraction)

### Front Page Detection
Look for header keywords:
- "NAME" + "HIT" + "WR"
- Two formats: `NAME ATK HIT DMG WR` (full) or `NAME A HIT D WR` (abbreviated)

### Statline Extraction
- Region-based coordinate extraction
- Front page: Stats (NAME, ATK, HIT, DMG, WR)
- Back pages: Abilities, actions, weapon rules

### Text Extraction Heuristics
When combining multi-line text (proven from `tools/extract_tokens.py`):
```python
text_gap_max = 6.0              # Max horizontal gap within same line
same_line_y_max = 15.0          # Max Y variance for same line
next_line_y_min = 5.0           # Min Y distance for new line
next_line_y_max = 25.0          # Max Y distance for continuation
next_line_x_overlap_ratio = 0.25 # Min X overlap for multi-line
```

Use `get_text("words")` for word-level extraction with bbox data.

## Token Extraction (Step 2 Integration)

### Detection
Check if first text line contains:
- "MARKER" OR "TOKEN GUIDE"

```python
def is_token_guide_card(page, card_coords):
    text = page.get_text("text", clip=card_rect)
    first_line = text.split('\n')[0].strip().upper()
    return 'MARKER' in first_line or 'TOKEN GUIDE' in first_line
```

### Extraction Process

**Phase 1 - Position Detection** (on card image at 150 DPI):
```python
# Contour detection
gray = cv2.cvtColor(card_img, cv2.COLOR_BGR2GRAY)
thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=3)
morph = cv2.morphologyEx(morph, cv2.MORPH_OPEN, kernel, iterations=2)
contours = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]

# Filter by area
min_token_area = 3000  # Empirically proven threshold
```

**Phase 2 - High-Res Extraction** (from PDF at 300 DPI):
```python
# Render card at high resolution
matrix = fitz.Matrix(300/72, 300/72)  # 300 DPI
pix = page.get_pixmap(matrix=matrix, clip=card_rect)

# Extract token regions using detected positions
# Scale coordinates from 150 DPI detection to 300 DPI extraction
```

**Phase 3 - Text Element Extraction**:
```python
# Extract token names from PDF
words = page.get_text("words", clip=card_rect)

# Group words into multi-line token names
# Split by delimiter: r'\s+(token|marker)\s*'
# Each text element gets unique bbox from word positions
```

### Output Structure

**Files:**
```
layers/warcom/extracted/{team}/tokens/
  page{XX}_card{X}_token{XX}.png  # Token images
  tokens_metadata.json             # Metadata with source_card field
```

**Metadata JSON:**
```json
{
  "tokens": [
    {
      "filename": "page05_card3_token01.png",
      "bbox": {"x": 123, "y": 456, "width": 89, "height": 101},
      "area": 8989,
      "source_card": "page05_card3"
    }
  ],
  "text_elements": [
    {
      "text": "Psyk-Out Grenades token",
      "bbox": {"x": 120, "y": 450, "width": 200, "height": 30},
      "source_card": "page05_card3"
    }
  ]
}
```

**Critical**: Each element must have `source_card` field for per-card matching when multiple token guide cards exist.

### Accumulation Pattern
```python
# Initialize at PDF level
all_tokens_metadata = []
all_text_elements = []

# Accumulate during card loop
for token in tokens_metadata.get('tokens', []):
    token['source_card'] = card_base
    all_tokens_metadata.append(token)

for text_elem in text_elements:
    text_elem['source_card'] = card_base
    all_text_elements.append(text_elem)

# Save once after all pages processed
combined_metadata = {
    'tokens': all_tokens_metadata,
    'text_elements': all_text_elements
}
```

## TTS Integration

### TTS Save JSON Structure
```json
{
  "ObjectStates": [
    {
      "Name": "Bag",  // CardBox container
      "ContainedObjects": [
        {
          "Name": "Deck",  // or "Card"
          "Nickname": "[FF5500]E[-] {8/8} Stalker Alpha",
          "GMNotes": "{...json stats...}",
          "LuaScript": "...datacard script...",
          "CustomDeck": {...},
          "DeckIDs": [...]
        }
      ]
    }
  ]
}
```

### Card Nickname Format
```
[FF5500]E[-] {8/8} Stalker Alpha
│       │ │  │     └─ Operative name
│       │ │  └─ Current/max wounds
│       │ └─ Order state indicator
│       └─ Order type (E=Engage, C=Conceal)
└─ Color code
```

### Lua Script Integration

**Location**: `config/defaults/tts-script/datacard-load-stats.lua`

**Purpose**: "Load stats to model" context menu functionality

**Key Functions**:
```lua
function onLoad(script_state)
    -- Load stats from script_state JSON
    state.stats = {...}
    state.info = {weapons={}, abilities={}, actions={}, categories=[], rules=[]}
    state.wounds = {current=8, max=8}
end

function diffAndApply(card_stats, model_stats)
    -- Compare and report changes per field
    -- Returns array of change descriptions
end

function findModelOnCard()
    -- Uses Physics.cast to find models on card
    -- Returns first non-card object found
end
```

**Script State Structure**:
```json
{
  "stats": {"M": "6\"", "APL": "2", "GA": "1", "DF": "3", "SV": "3+", "W": "8"},
  "info": {
    "weapons": [...],
    "abilities": [...],
    "actions": [...],
    "categories": ["IMPERIUM", "PHOBOS"],
    "rules": [...]
  },
  "wounds": {"current": 8, "max": 8}
}
```

## Data Flow

```
input/*.pdf
  ↓
processed/{team}/{team}-datacards.pdf
  ↓
extract_statlines.py → output/{team}/statlines/roster.json
  ↓
extract images → output_v2/{faction}/{team}/cards/
  ↓
embed_datacard_stats.py → tts_objects/{team}/*.json
  (patches with GMNotes + LuaScript)
```

## Common Debugging Patterns

### 1. Malformed Extraction Metadata
**Problem**: Some teams have malformed `extraction_metadata.json`
- Known teams: battleclade, deathwatch, exaction-squad

**Solution**: Always wrap in try/except
```python
try:
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
except json.JSONDecodeError:
    logger.warning(f"Malformed metadata for {team}")
    metadata = {}
```

### 2. Unicode in Operative Names
**Problem**: Names contain special characters (ô, â, ', ‑)

**Solution**: Use `roster_slug()` for matching
```python
def roster_slug(s):
    return re.sub(r"[^\x00-\x7f]", "", s)
```

### 3. Multiple Token Guide Cards
**Problem**: Second card overwrites first card's metadata

**Solution**: Accumulate with `source_card` field (implemented in step 2)

### 4. Token Area Threshold
**Problem**: Contour detection missing small tokens or catching noise

**Solution**: Empirically proven value
```python
min_token_area = 3000  # Works for 150 DPI detection
```

### 5. Header Skipping for Tokens
**Problem**: "MARKER/TOKEN GUIDE" header interferes with content detection

**Solution**: Skip top percentage
```python
skip_header_percent = 15.0
header_height = int(card_height * (skip_header_percent / 100.0))
```

## Pipeline Steps (kt-app)

1. **Process raw PDFs** - Organize and validate
2. **Extract images** - Parallel processing with token integration
3. **Add backsides** - Apply card back templates
3.5. **Process box textures** - Generate team-specific box textures
4. **Generate V2 URLs JSON** - Create URL mappings
5. **Generate TTS objects** - Create save files
5.25. **Embed ready team tokens** - For locked teams only
5.4. **Extract statlines** - From datacard PDFs
5.5. **Embed datacard stats** - Patch TTS objects with GMNotes + LuaScript
6. **Generate metadata** - Compile team metadata
6.5. **Generate TTS metadata** - With timestamps
7. **Display table generation** - Deployment only

## Key Dependencies

```toml
python = "^3.9"
pymupdf = "*"        # PDF text extraction and rendering
pillow = "*"         # Image manipulation
pypdf2 = "*"         # PDF processing
pytesseract = "*"    # OCR (backup)
pyyaml = "*"         # Config parsing
pandas = "*"         # Data processing
requests = "*"       # Web scraping (warcom)
beautifulsoup4 = "*" # HTML parsing (warcom)
opencv-python = "*"  # Image processing, contour detection
```

## Config File Patterns

### team-config.yaml
```yaml
teams:
  angels-of-death:
    name: "Angels of Death"
    faction: imperium
    aliases: ["aod", "space-marines-phobos"]
    tokens:
      - type: "order"
        count: 10
```

### team-guids.json
```json
{
  "angels-of-death": {
    "card-box": "abc123",
    "token-bag": "def456"
  }
}
```

### weapon_rules.json
```json
{
  "Lethal 5+": {
    "description": "Critical hits on 5+ instead of 6",
    "icon": "lethal"
  }
}
```

## Testing Patterns

### Test Single Team
```powershell
# Copy specific team PDF
Copy-Item layers/archive/{team}/warcom/*.pdf layers/warcom/staging/

# Run extraction
poetry run python pipelines/warcom/steps/2_card_extractor.py
```

### Verify Token Extraction
```powershell
# Check token images
Get-ChildItem layers/warcom/extracted/{team}/tokens/*.png

# Check metadata
$meta = Get-Content layers/warcom/extracted/{team}/tokens/tokens_metadata.json | ConvertFrom-Json
$meta.tokens | Group-Object source_card | Format-Table Count, Name
```

### Test Multi-Card Scenarios
Known multi-card teams:
- celestian-insidiants (2 token guide cards)

```powershell
# Verify both cards captured
$meta.tokens | Select-Object filename, source_card | Format-Table
$meta.text_elements | Select-Object text, source_card | Format-Table
```

## Known Issues & Workarounds

### Issue: Box Texture Text Wrapping
**Problem**: Long team names overflow box texture
**Solution**: Word-split optimization in `dev/generate_box_texture.py`
```python
# Split team name into balanced lines
# Target: Arial Bold 50pt, area (533,15-999,120)
```

### Issue: Token Name Multi-Line
**Problem**: Token names span multiple lines in PDF
**Solution**: Word-level extraction with proximity heuristics
```python
# Group words based on Y proximity and X overlap
# Use proven thresholds from tools/extract_tokens.py
```

### Issue: DPI Mismatch
**Problem**: Detection at one DPI, extraction at another
**Solution**: Scale coordinates appropriately
```python
detection_dpi = 150
extraction_dpi = 300
scale_factor = extraction_dpi / detection_dpi
```

## Performance Considerations

1. **Parallel Processing**: Use `concurrent.futures` for multi-PDF processing
2. **Memory Management**: `del page_img` after processing each page
3. **DPI Selection**: 
   - 150 DPI for detection (faster, sufficient for contours)
   - 300 DPI for extraction (quality, final output)
4. **Batch Operations**: Process all teams in one pass when possible

## File Naming Conventions

```
# PDFs
{team}-datacards.pdf

# Card images
page{XX}_card{X}_{type}.png
page01_card1_portrait.png

# Token images
page{XX}_card{X}_token{XX}.png
page05_card3_token01.png

# Metadata
tokens_metadata.json
card_index.json
extraction_metadata.json
```

## Next Steps / Enhancements

1. **Token-Name Matching**: Match tokens to names by proximity within same source_card
2. **Background Removal**: Clean token backgrounds (transparency)
3. **Batch Processing**: Run all 46 teams with token extraction
4. **Validation**: Verify token counts match expected values
5. **Integration**: Link token extraction into main pipeline flow
