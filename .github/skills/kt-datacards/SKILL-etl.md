---
description: kt-datacards ETL pipeline — PDF extraction with PyMuPDF, statline parsing, image extraction, token detection with OpenCV, pipeline steps and orchestration. Load when working on extraction, processing, or pipeline logic.
tags: [kill-team, etl, pdf-extraction, pymupdf, opencv, image-processing, pipeline, tokens]
---

# kt-datacards — ETL Pipeline & Extraction

## When to Use This Skill

Load when working on:
- PDF extraction or statline parsing
- Image extraction and processing
- Token extraction / detection
- Pipeline step orchestration
- Debugging extraction issues

Also load **SKILL-project.md** for directory structure and naming conventions.

---

## Pipeline Overview

### Three Pipeline Systems

**kt-app pipeline** (PRODUCTION — main branch):
- Entry: `script/run_pipeline.py`
- Orchestrator: `script/src/pipeline.py`
- Output: `output_v2/` (faction-organized), `tts_objects/`
- Processes PDFs from the Kill Team mobile app (UUID filenames)
- Requires content analysis to identify team and card types

**kt-app refactor** (REFACTOR — refactor-kt-app-pipeline branch):
- Entry: `pipelines/kt-app/steps/1_process_pdfs.py` through `7_generate_tts_objects.py`
- Output: `output_v3/` (team-organized), intermediate data in `layers/kt-app/`
- Modular 7-step architecture with clean separation of concerns
- Uses classification-based structure (structure.json)
- Run individual steps or use pipeline orchestrator
- **Stats embedded automatically in step 7** (no separate embedding step)

**warcom pipeline** (LEGACY — kept for reference):
- Entry: `pipelines/warcom/pdf_process_pipeline.py`
- Steps: `pipelines/warcom/steps/` (numbered 1–9)
- Processes official PDFs from Warhammer Community website
- 4 cards per page in a grid layout
- Includes token guide cards alongside datacards

> **Main vs Refactor**: Main branch uses `script/` (production), refactor branch uses `pipelines/kt-app/steps/` (new architecture).

---

## Pipeline Steps (kt-app)

| Step | Name | Script/Module |
|------|------|---------------|
| 1 | Process raw PDFs | `script/process_pdfs.py` |
| 2 | Extract images (parallel) | `script/src/processors/image_extractor.py` + token integration |
| 3 | Add backsides | `script/src/processors/backside_processor.py` |
| 3.5 | Process box textures | `script/src/processors/box_texture_processor.py` |
| 4 | Generate V2 URLs JSON | `script/generate_urls.py` |
| 5 | Generate TTS objects | `script/generate_tts_objects.py` |
| 5.25 | Embed ready team tokens | Locked teams only |
| 5.4 | Extract statlines | From datacard PDFs → `output/{team}/statlines/roster.json` |
| 5.5 | Embed datacard stats | Patches TTS objects with GMNotes + LuaScript |
| 6 | Generate metadata | `script/generate_metadata.py` |
| 6.5 | Generate TTS metadata | `script/generate_tts_metadata.py` (with timestamps) |
| 7 | Display table generation | Deployment only |

### Running Specific Steps
```powershell
poetry run python script/run_pipeline.py --step all
poetry run python script/run_pipeline.py --step extract --teams kasrkin
poetry run python script/run_pipeline.py --step extract --teams angels-of-death,kommandos
```

---

## Pipeline Steps (kt-app refactor)

**Location**: `pipelines/kt-app/steps/`

| Step | Name | Script | Output |
|------|------|--------|--------|
| 1 | Process PDFs | `1_process_pdfs.py` | `layers/kt-app/processed/`, `layers/kt-app/extracted/` |
| 2 | Classify Structure | `2_classify_structure.py` | `layers/kt-app/classified/{team}/structure.json` |
| 3 | Extract Team Data | `3_extract_team_data.py` | `output_v3/{team}/data/{team}-team-data.json` |
| 4 | Extract Card Images | `4_extract_card_images.py` | `output_v3/{team}/cards/{type}/*.png` |
| 5 | Extract Tokens | `5_extract_tokens.py` | `output_v3/{team}/tokens/*.png` |
| 6 | Generate TTS Assets | `6_generate_tts_assets.py` | `output_v3/{team}/cardbox/`, `output_v3/{team}/tokens/*.obj` |
| 7 | Generate TTS Objects + Embed Stats | `7_generate_tts_objects.py` | `output_v3/{team}/tts_object/*.json` (with embedded GMNotes) |

### Running Refactor Steps
```powershell
# Run all steps for a team
cd pipelines/kt-app/steps
python 1_process_pdfs.py --team spectre-squad --force
python 2_classify_structure.py --team spectre-squad --force
python 3_extract_team_data.py --team spectre-squad --force
python 4_extract_card_images.py --team spectre-squad --force
python 5_extract_tokens.py --teams spectre-squad
python 6_generate_tts_assets.py --teams spectre-squad
python 7_generate_tts_objects.py --teams spectre-squad  # Embeds stats automatically
```

### Refactor Pipeline Key Features

**Classification-Based**: Step 2 creates `structure.json` mapping all cards:
```json
{
  "team": "spectre-squad",
  "datacards": [...],
  "equipment": [...],
  "faction_rules": [...],
  "firefight_ploys": [...],
  "strategy_ploys": [...],
  "operatives_selection": [...]
}
```

**Team-Organized Output** (`output_v3/{team}/`):
```
{team}/
  ├── cards/
  │   ├── datacards/          # {operative-name}-front.png, -back.png
  │   ├── equipment/          # {equipment-name}-front.png, -back.png
  │   ├── faction_rules/      # {rule-name}-front.png, -back.png
  │   ├── firefight_ploys/    # {ploy-name}-front.png, -back.png
  │   ├── strategy_ploys/     # {ploy-name}-front.png, -back.png
  │   └── operatives_selection/ # operatives-front.png, -back.png
  ├── tokens/                 # {team}-{token-name}.png (with transparency)
  ├── cardbox/                # card-box.obj, card-box-texture.jpg, icon.png
  ├── data/                   # {team}-team-data.json
  └── tts_object/             # {Team Name} Cards.json
```

**Intermediate Layers** (`layers/kt-app/`):
```
layers/kt-app/
  ├── processed/{team}/       # Copied and renamed PDFs
  ├── extracted/{team}/cards/{type}/  # Single-page PDFs
  ├── classified/{team}/      # structure.json
  └── metadata.json           # Pipeline state tracking
```

---

## Data Flow

```
input/*.pdf (UUID filenames)
  ↓ Step 1
processed/{team}/{team}-datacards.pdf
  ↓ Step 2 (parallel)
output_v2/{faction}/{team}/datacards/*.jpg   ← card images
  ↓ Step 5.4
output/{team}/statlines/roster.json          ← extracted statlines
  ↓ Step 5.5
tts_objects/{team}/*.json                    ← patched with GMNotes + LuaScript
```

---

## PDF Extraction — Core Patterns

### Library
```python
import fitz  # PyMuPDF
```

### Rendering
```python
# Detection pass — fast
matrix_150 = fitz.Matrix(150/72, 150/72)
pix = page.get_pixmap(matrix=matrix_150, clip=card_rect)

# Extraction pass — quality
matrix_300 = fitz.Matrix(300/72, 300/72)
pix = page.get_pixmap(matrix=matrix_300, clip=card_rect)
```

Always use 150 DPI for detection/contours and 300 DPI for final image output. Scale coordinates between them:
```python
scale_factor = 300 / 150  # = 2.0
high_res_x = low_res_x * scale_factor
```

### Text Extraction
Prefer word-level extraction for positioning:
```python
words = page.get_text("words", clip=card_rect)
# Each word: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
```

---

## Statline Extraction

### Front Page Detection
A card page is a "front page" if it contains these keywords:
- `"NAME"` AND `"HIT"` AND `"WR"`

Two header formats:
```
NAME  ATK  HIT  DMG  WR   ← full format
NAME  A    HIT  D    WR   ← abbreviated format
```

### Coordinate-Based Region Extraction
Stats are extracted from known coordinates on the page. Front page contains: `NAME`, `ATK/A`, `HIT`, `DMG/D`, `WR`. Back pages contain abilities, actions, weapon rules.

### Multi-Line Text Heuristics (proven values)
```python
text_gap_max = 6.0              # Max horizontal gap within same line
same_line_y_max = 15.0          # Max Y variance considered same line
next_line_y_min = 5.0           # Min Y distance for a new line
next_line_y_max = 25.0          # Max Y distance for continuation
next_line_x_overlap_ratio = 0.25 # Min X overlap for multi-line grouping
```

---

## Token Extraction

Tokens are extracted from special "Token Guide" / "Marker" cards.

### Step 1 — Detect Token Guide Cards
```python
def is_token_guide_card(page, card_coords) -> bool:
    text = page.get_text("text", clip=card_rect)
    first_line = text.split('\n')[0].strip().upper()
    return 'MARKER' in first_line or 'TOKEN GUIDE' in first_line
```

### Step 2 — Contour Detection (150 DPI image)
```python
import cv2

gray = cv2.cvtColor(card_img, cv2.COLOR_BGR2GRAY)
thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=3)
morph = cv2.morphologyEx(morph, cv2.MORPH_OPEN, kernel, iterations=2)
contours = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]

min_token_area = 3000  # Empirically proven — works at 150 DPI
```

### Step 3 — Skip Header Region
The "MARKER / TOKEN GUIDE" header text interferes with detection:
```python
skip_header_percent = 15.0
header_height = int(card_height * (skip_header_percent / 100.0))
# Only process contours below y > header_height
```

### Step 4 — Extract at 300 DPI
Use detected bounding boxes from 150 DPI, scale by `2.0`, extract from 300 DPI render.

### Step 5 — Extract Token Names (word-level)
```python
words = page.get_text("words", clip=card_rect)
# Group words by Y proximity and X overlap using heuristics above
# Split token names by: r'\s+(token|marker)\s*'
```

### Output Structure (warcom pipeline)
```
layers/warcom/extracted/{team}/tokens/
  page{XX}_card{X}_token{XX}.png   # Token images
  tokens_metadata.json              # Combined metadata
```

**tokens_metadata.json**:
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

> **Critical**: `source_card` is required when multiple token guide cards exist in the same PDF (e.g., `celestian-insidiants` has 2).

### Multi-Card Accumulation Pattern
```python
all_tokens_metadata = []
all_text_elements = []

for page in pdf_pages:
    for card in page_cards:
        if not is_token_guide_card(page, card):
            continue
        card_base = f"page{page_num:02d}_card{card_num}"

        for token in extract_tokens(page, card):
            token['source_card'] = card_base
            all_tokens_metadata.append(token)

        for text_elem in extract_text_elements(page, card):
            text_elem['source_card'] = card_base
            all_text_elements.append(text_elem)

# Save once at the end — never save inside the loop
combined = {'tokens': all_tokens_metadata, 'text_elements': all_text_elements}
```

---

## Common Extraction Debugging

### Issue: Malformed extraction_metadata.json
Known broken teams: `battleclade`, `deathwatch`, `exaction-squad`
```python
try:
    metadata = json.loads(path.read_text())
except json.JSONDecodeError:
    logger.warning(f"Malformed metadata for {team}, using empty")
    metadata = {}
```

### Issue: Unicode in Operative Names
Names like `Ô`, `â`, `'`, `‑` (non-breaking hyphen) break file matching.
```python
def roster_slug(s: str) -> str:
    return re.sub(r"[^\x00-\x7f]", "", s)
```

### Issue: Token Contours Missing or Noisy
- Under-detection: Lower `min_token_area` below 3000
- Over-detection: Raise `min_token_area` or adjust morphology kernel size

### Issue: Second Token Card Overwrites First
Symptom: Only tokens from the last guide card survive in metadata.
Fix: Use the accumulation pattern above — never re-initialize lists inside the card loop.

### Issue: DPI Coordinate Mismatch
Detection uses 150 DPI; extraction uses 300 DPI. Always scale:
```python
coords_300 = [(x * 2, y * 2, w * 2, h * 2) for (x, y, w, h) in coords_150]
```

---

## Performance

- **Parallel processing**: Use `concurrent.futures.ThreadPoolExecutor` for multi-team PDF processing
- **Memory**: `del page_img` after each page to avoid accumulation
- **DPI**: Never use 300 DPI for detection/contour passes — too slow
- **Batch**: Process all teams in one pass when possible (`--teams` filter for targeted runs)

---

## Special Case: Multi-Card Faction Rules (Elite Fieldcraft Fix)

### Problem
Cards with "(CARD X/Y)" notation (e.g., "ELITE FIELDCRAFT (CARD 2/3)") were incorrectly paired as front/back when they should be separate cards.

**Example**: Spectre Squad has 4 faction rules cards:
- ELITE FIELDCRAFT (CARD 1/3) — should be front + back
- ELITE FIELDCRAFT (CARD 2/3) — should be separate (front + default back)
- ELITE FIELDCRAFT (CARD 3/3) — should be separate (front + default back)
- CAMO CLOAKS — single card (front + default back)

### Root Cause
Name extraction stripped "(CARD X/Y)" → all extracted as "elite-fieldcraft" → pairing logic saw matching names → paired cards 2/3 and 3/3 as front/back.

### Solution

**Step 1: Enhanced Name Extraction** (both pipelines)
```python
import re

# Detect multi-card pattern and append card number
card_num_match = re.search(r'FACTION\\s+RULE\\s+([A-Z\\s]+?)\\s*\\(CARD\\s+(\\d+)/(\\d+)\\)', text_normalized)
if card_num_match:
    rule_name = card_num_match.group(1).strip()
    card_num = card_num_match.group(2)
    # Slugify and append card number
    cleaned = re.sub(r'[^A-Z0-9\\s]', '', rule_name)
    cleaned = re.sub(r'\\s+', '-', cleaned.strip()).lower()
    return f"{cleaned}-card-{card_num}"  # e.g., "elite-fieldcraft-card-2"
```

**Step 2: Prevent Incorrect Pairing**
```python
def has_multi_card_pattern(page_text: str) -> bool:
    """Check if page has (CARD X/Y) pattern"""
    return bool(re.search(r'\\(CARD\\s+\\d+/\\d+\\)', page_text))

# In pairing logic:
current_has_card_num = has_multi_card_pattern(current_page_text)
next_has_card_num = has_multi_card_pattern(next_page_text)

if current_has_card_num and next_has_card_num:
    # Don't pair — treat as separate cards
    pass
```

### Implementation Locations
- **Main pipeline**: `script/src/processors/image_extractor.py`
  - Lines 397-417: `extract_card_name()` with regex
  - Lines 172-203: Pairing logic with pattern check
- **Refactor pipeline**: `pipelines/kt-app/steps/2_classify_structure.py`
  - `extract_card_name()`: Enhanced regex extraction
  - `has_multi_card_pattern()`: New helper method
  - Pairing logic: Check both pages before pairing

### Result
```
elite-fieldcraft-card-1-front.png, elite-fieldcraft-card-1-back.png
elite-fieldcraft-card-2-front.png, elite-fieldcraft-card-2-back.png (default)
elite-fieldcraft-card-3-front.png, elite-fieldcraft-card-3-back.png (default)
camo-cloaks-front.png, camo-cloaks-back.png (default)
```

---

## Token Processing: Background Removal & Cleanup

### Problem
Small pixel islands (2-5 pixels) appearing outside token boundaries — typically in corners. These survive background removal and end up in the final token image.

**Example**: `spectre-squad-patience.png` had stray pixels in bottom-right corner.

### Root Cause
Conservative white detection threshold allowed slightly off-white pixels (HSV value 235-244) to survive background removal. These pixels were:
- Outside the main token content
- Light gray or off-white (not pure white)
- Below saturation threshold for color detection

### Token Processing Flow (Refactor Pipeline)

**Location**: `pipelines/kt-app/steps/5_extract_tokens.py`

```
1. Extract rough token from PDF (contour detection)
   └─> layers/kt-app/extracted/_tuning/{team}/
   
2. Remove background (white/gray detection)
   └─> HSV thresholds: v > 235, s < 25
   
3. Crop to content bounds
   └─> Remove excess transparent areas
   
4. Fit template to content
   └─> Scale template (operative/round/diamond) to match token
   
5. Apply template as alpha mask
   └─> Force pixels outside template to white/transparent
   
6. Fill transparent holes inside template
   └─> White fill for background-removed areas
   
7. Resize to standard size
   └─> 439x414 (operative), 235x235 (round/diamond)
```

### Solution

**Threshold Adjustments** (lines ~128):
```python
# Before: Too conservative
is_white = ((v > 245) & (s < 15)) | (bgr > 245)

# After: More aggressive
is_white = ((v > 235) & (s < 25)) | (bgr > 235)
```

**Hard Template Boundary** (lines ~313):
```python
# Step 4: Create alpha from fitted template
template_area = fitted_template > 127

# SAFETY: Force remove stray pixels outside template
cropped_bgr[~template_area] = [255, 255, 255]  # Set to white
```

### Result
- ✓ Stray pixels completely removed
- ✓ White icons preserved (skull, wings, medical symbols)
- ✓ White numbers preserved (fieldcraft points, numeric tokens)

### Testing
After changes, verify tokens with white content:
```powershell
python pipelines/kt-app/steps/5_extract_tokens.py --teams spectre-squad
# Check: medic.png (skull, wings), fieldcraft-points.png (rifles, numbers)
```
