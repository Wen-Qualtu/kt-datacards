# Step 3: Card Classification and Image Generation

## Purpose

Classify extracted cards by type based on text content, convert PDFs to high-quality JPG images with rounded corners, and organize into final output structure.

---

## Script

`pipelines/warcom/steps/3_card_classification.py`

---

## Input

- **Source**: `layers/warcom/extracted/{team}/cards/*.pdf`
- **Templates**: `config/pipelines/warcom/template-card-{orientation}-cutter.png`
- **Config**: `config/team-config.yaml`

---

## Output

- **Directory**: `output/{team}/cards/{type}/*.jpg`
- **Filename**: `{team}-{card-name}-{side}.jpg`
  - Example: `kommandos-kommando-boy-front.jpg`

**Card type folders:**
- `datacards/` - Operative datacards
- `equipment/` - Equipment cards
- `faction-rules/` - Faction-specific rules
- `operative-selection/` - Operative selection reference
- `ploys/firefight/` - Firefight tactical ploys
- `ploys/strategy/` - Strategic ploys
- `token-guide/` - Token reference guide

---

## Execution Order

### 1. Load Team Configuration

```python
config = yaml.safe_load(open('config/team-config.yaml'))
```

**Purpose:** Validate team names and get metadata.

### 2. For Each Card PDF

#### 2.1 Extract Text from PDF

```python
doc = fitz.open(pdf_path)
text_blocks = page.get_text("blocks")
```

**Block structure:**
- Blocks sorted by position (Y, then X)
- Each block: `(x0, y0, x1, y1, "text", block_no, block_type)`
- Lines extracted and cleaned

#### 2.2 Check for NOTES Cards

```python
if text.strip().upper() == 'NOTES':
    skip_card()
```

**Why first?** NOTES cards have no game data and should be skipped before any processing.

#### 2.3 Determine Orientation

**From filename:**
- Contains `landscape` → landscape orientation
- Otherwise → portrait orientation

**Purpose:** Determines classification path.

#### 2.4 Classify Card

**Classification tree:**

```
┌─ Is NOTES card?
│  └─ Yes → Skip (no output)
│
├─ Is LANDSCAPE?
│  └─ Yes → ALWAYS datacards
│     └─ Extract operative name from line 1
│
└─ Is PORTRAIT
   ├─ Contains "KILL TEAM" + "ARCHETYPE"?
   │  └─ Yes → operative-selection
   │
   └─ Check header line 2:
      ├─ "MARKER/TOKEN GUIDE" → token-guide
      ├─ "FACTION RULE" → faction-rules
      ├─ "EQUIPMENT" → equipment
      ├─ "FIREFIGHT PLOY" → ploys/firefight
      ├─ "STRATEGY PLOY" → ploys/strategy
      └─ None match → Skip (unknown type)
```

---

## Classification Rules

### Landscape Cards (Datacards)

**Always datacards** regardless of content.

**Name extraction:**
1. Read first 10 text lines
2. Skip stat keywords: `APL`, `WOUNDS`, `SAVE`, `MOVE`, `GA`, `DF`, `SV`
3. Skip pure numbers: `3+`, `4+`, `6"`, etc.
4. First meaningful text = operative name
5. Clean: remove non-alphanumeric, lowercase, spaces→hyphens

**Example:**
- Line 1: `KOMMANDO BOY`
- Output name: `kommando-boy`

### Portrait Cards

**Header structure:**
- Line 0: Team name (e.g., `KOMMANDOS`)
- Line 1: Card type (e.g., `EQUIPMENT`, `STRATEGY PLOY`)
- Line 2: Card name (e.g., `KUSTOM SHOOTA`)

**Type detection (line 1):**

| Line 1 Text | Card Type | Output Folder |
|-------------|-----------|---------------|
| `MARKER/TOKEN GUIDE` | token-guide | `token-guide/` |
| `FACTION RULE` | faction-rules | `faction-rules/` |
| `EQUIPMENT` | equipment | `equipment/` |
| `FIREFIGHT PLOY` | firefight-ploys | `ploys/firefight/` |
| `STRATEGY PLOY` | strategy-ploys | `ploys/strategy/` |

**Name extraction:**
- Regular cards: Use line 2
- Token guide: Hardcoded as `token-guide`
- Multi-option faction rules: Special handling (see below)

### Special Case: Operative Selection

**Pattern detection:**
- First ~300 chars contain "KILL" AND "TEAM"
- Anywhere in card contains "ARCHETYPE" or "ARCHETYPES"

**Result:**
- Type: `operative-selection`
- Name: `operative-selection`

### Special Case: Multi-Option Faction Rules

**Pattern:** Cards like "ACCURSED GIFTS" or "SANGUAVITAE" with numbered options.

**Example:**
```
ACCURSED GIFTS
1. Deformed Wings
  ...
```

**Logic:**
1. Detect main rule name: `ACCURSED GIFTS`
2. Find numbered option: `1. Deformed Wings`
3. Combine: `accursed-gifts-deformed-wings`

**Alternative patterns:**
- Non-numbered options (e.g., "Rejuvenate")
- Extract option name and combine with main rule

---

## Front/Back Detection

**Purpose:** Pair card fronts with backs.

### Front Cards

**Marker text:**
- "CONTINUES ON OTHER SIDE"
- "CONTINUE ON THE OTHER SIDE"

**Process:**
1. Extract all text
2. Search for marker text (case-insensitive)
3. If found, next sequential card is the back

### Back Cards

**Filename pattern:**
- Next card after a front card with marker text

**Naming:**
- Front: `{team}-{card-name}-front.jpg`
- Back: `{team}-{card-name}-back.jpg`

### Cards Without Backs

**Fallback:** Use default backside image.

**Priority:**
1. Team-specific: `config/teams/{team}/card-backside/{team}-backside-{orientation}.jpg`
2. Default: `config/defaults/card-backside/default-backside-{orientation}.jpg`

**Orientation:**
- `landscape` for datacards
- `portrait` for all others

---

## Image Processing

### 1. Render PDF to Image

```python
mat = page.get_pixmap(dpi=300)
img = np.frombuffer(mat.samples, dtype=np.uint8).reshape(mat.height, mat.width, 3)
```

**DPI:** 300 (high quality for printing and TTS)

### 2. Apply Rounded Corners

**Method:** Inpainting (fills corner regions intelligently).

**Corner radius by card type:**
- Datacards (landscape): 45 pixels
- Operative selection: 33 pixels
- Other portrait cards: 40 pixels

**Process:**
1. Create mask (white circles at each corner)
2. Apply inpainting to fill masked regions
3. Algorithm: `cv2.INPAINT_TELEA` (Fast Marching Method)

**Why inpainting?**
- Eliminates white edges around corners
- More natural than simple alpha masking
- Blends with card background colors

### 3. Save as JPG

```python
cv2.imwrite(output_path, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
```

**Quality:** 95 (high quality, reasonable file size)

---

## Filename Generation

### Card Name Normalization

**Steps:**
1. Extract name from card text
2. Convert to uppercase
3. Remove special characters (keep alphanumeric, spaces, hyphens)
4. Convert to lowercase
5. Replace spaces with hyphens
6. Remove duplicate hyphens

**Examples:**
- `KOMMANDO BOY` → `kommando-boy`
- `Da Kommanda!` → `da-kommanda`
- `Kustom  Shoota` → `kustom-shoota`

### Duplicate Name Handling

**Problem:** Multiple cards with same name in same type folder.

**Solution:** Append suffix to duplicates.

**Examples:**
- First occurrence: `kustom-shoota-front.jpg`
- Second occurrence: `kustom-shoota-2-front.jpg`
- Third occurrence: `kustom-shoota-3-front.jpg`

**Tracking:** Per card type (same name OK in different types).

---

## Error Handling

### PDF Read Errors

**Symptom:**
```
WARNING: Text extraction failed for kommandos_page02_card1.pdf
```

**Causes:**
- Corrupted PDF
- File locked by another process
- Insufficient permissions

**Recovery:** Skip card, log warning, continue processing.

### Unknown Card Types

**Symptom:**
```
WARNING: Could not classify kommandos_page05_card3.pdf
```

**Causes:**
- Text extraction failure
- Unexpected header structure
- New card type not in classification rules

**Recovery:** Skip card, log warning, continue processing.

### Missing Default Backside

**Symptom:**
```
WARNING: No backside image found for landscape orientation
```

**Recovery:**
- Card front is saved
- Back is skipped
- Logged for manual review

---

## Output Structure

```
output/kommandos/cards/
├── datacards/
│   ├── kommandos-kommando-boy-front.jpg
│   ├── kommandos-kommando-boy-back.jpg
│   ├── kommandos-kommando-grot-front.jpg
│   └── kommandos-kommando-grot-back.jpg
├── equipment/
│   ├── kommandos-kustom-shoota-front.jpg
│   └── kommandos-kustom-shoota-back.jpg
├── faction-rules/
│   ├── kommandos-da-kommanda-front.jpg
│   └── kommandos-infiltration-front.jpg
├── operative-selection/
│   └── kommandos-operative-selection-front.jpg
├── ploys/
│   ├── firefight/
│   │   ├── kommandos-get-stuck-in-front.jpg
│   │   └── kommandos-surprise-attack-front.jpg
│   └── strategy/
│       ├── kommandos-opportunist-front.jpg
│       └── kommandos-recon-front.jpg
└── token-guide/
    ├── kommandos-token-guide-front.jpg
    └── kommandos-token-guide-back.jpg
```

---

## Performance

**Typical runtime (single team):**
- Card classification: ~1-2 minutes
- Image processing: ~5-10 seconds per card
- Total: ~3-5 minutes for 25 cards

**Bottleneck:** PDF rendering at 300 DPI (CPU-bound)

**Parallelization:** Use `--workers N` for parallel processing.

---

## Design Decisions

### Why JPG Instead of PNG?

**Advantages:**
- Smaller file size (3-5x reduction)
- Faster to upload/download from GitHub
- Sufficient quality at 95%

**Disadvantages:**
- No transparency support

**Decision:** Cards don't need transparency (handled by rendering corners).

### Why 300 DPI?

**Requirements:**
- TTS card quality: 200+ DPI recommended
- Printing quality: 300 DPI standard
- File size: Manageable at 300 DPI (~500KB per card)

**Alternatives:**
- 150 DPI: Too low for printing
- 600 DPI: Excessive file sizes

### Why Inpainting for Corners?

**Alternatives:**
1. Alpha masking → Transparent PNGs (larger files)
2. Overlay template → Visible borders
3. Simple crop → Square corners

**Inpainting advantages:**
- Maintains JPG format
- No visible edges
- Natural blending with card colors

### Why Text-Based Classification?

**Alternatives:**
1. OCR → Unreliable, slow
2. Image recognition ML → Overkill for standardized PDFs
3. Filename patterns → Too fragile

**Text extraction advantages:**
- Reliable (PDFs have embedded text)
- Fast (no ML needed)
- Deterministic (same input = same output)

---

## Maintenance

### Adding New Card Types

1. Add type detection in `_extract_card_type_from_header()`:
   ```python
   elif 'NEW CARD TYPE' in type_line:
       return 'new-card-type'
   ```

2. Add folder mapping in classification logic

3. Test with sample PDFs

### Updating Classification Logic

**Common scenarios:**
- New header format: Update line indices
- New team name patterns: Update config YAML
- New special cases: Add to classification tree

---

**Last Updated**: February 16, 2026
