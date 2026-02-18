# Step 2: Card and Token Extraction

## Purpose

Extract individual cards and tokens from warcom PDFs using template matching. Outputs both rough-cropped cards (as PDFs) and tokens (as PNGs) for further processing.

---

##Script

`pipelines/warcom/steps/2_card_extractor.py`

---

## Input

- **Source**: `layers/warcom/staging/*.pdf` (downloaded from Step 1)
- **Templates**: `config/pipelines/warcom/extraction-templates.json`
- **Config**: `config/team-config.yaml`

---

## Output

### Cards (PDFs)
- **Directory**: `layers/warcom/extracted/{team}/cards/*.pdf`
- **Filename**: `{team}_page{XX}_card{Y}.pdf`
  - Example: `kommandos_page02_card1.pdf`

### Tokens (PNGs)
- **Directory**: `layers/warcom/extracted/{team}/tokens/*.png`
- **Filename**: `{team}_page{XX}_card{Y}_token{ZZ}.png`
  - Example: `kommandos_page06_card1_token02.png`

### Token Name Mapping
- **File**: `layers/warcom/extracted/{team}/tokens/token-names.json`
- **Format**:
  ```json
  {
    "kommandos_page06_card1_token01.png": "Breach",
    "kommandos_page06_card1_token02.png": "Smoke grenade"
  }
  ```

### Team Icons
- **Directory**: `layers/warcom/extracted/{team}/icons/`
- **Files**:
  - `portrait-icon.jpg` - Portrait card backside icon
  - `landscape-icon.jpg` - Landscape card backside icon
  - `token-bag-icon.jpg` - Token bag icon

---

## Execution Order

### 1. Load Team Configuration

```python
team_config = load_team_config('config/team-config.yaml')
```

**Purpose:** Map extracted team names to canonical names and aliases.

**Example:**
```yaml
teams:
  kommandos:
    canonical_name: "Kommandos"
    aliases:
      - "ork kommandos"
      - "greenskin kommandos"
```

### 2. Load Extraction Templates

```python
templates = load_templates('config/pipelines/warcom/extraction-templates.json')
```

**Template structure:**
```json
{
  "300dpi": {
    "4_cards_portrait": {
      "grid": [[x1, y1, x2, y2], ...]
    },
    "4_cards_landscape": { ... },
    "2_cards_portrait": { ... }
  }
}
```

**Coordinates:** Normalized DPI-independent percentages (0.0 to 1.0).

### 3. Extract Team Name from PDF

```python
def extract_team_name_from_pdf(pdf_path: Path) -> str
```

**Logic:**
1. Check last 5 pages of PDF
2. Find largest text on page
3. Look for text near "KILL TEAM" heading
4. Extract and normalize (lowercase, spaces to hyphens)

**Matching:**
1. Try exact match against canonical names
2. Try matching against aliases
3. Return normalized team name or empty string

**Note:** This function is fragile and may extract incorrect text. Works for current PDF structure but should be improved for better reliability.

### 4. Extract Team Icons

**Purpose:** Extract small icons from card backsides and token bag page.

**Icon types:**
- Portrait card backside icon (page 1)
- Landscape card backside icon (page 1)
- Token bag icon (last page with tokens)

**Coordinates (as percentage of page):**

```python
# Portrait icon
PORTRAIT_ICON_X1 = 0.0243
PORTRAIT_ICON_Y1 = 0.0006
PORTRAIT_ICON_X2 = 0.1620
PORTRAIT_ICON_Y2 = 0.1324

# Landscape icon
LANDSCAPE_ICON_X1 = 0.0008
LANDSCAPE_ICON_Y1 = 0.0232
LANDSCAPE_ICON_X2 = 0.1839
LANDSCAPE_ICON_Y2 = 0.1027

# Token bag icon
TOKEN_ICON_X1 = 0.1288
TOKEN_ICON_Y1 = 0.1625
TOKEN_ICON_X2 = 0.2724
TOKEN_ICON_Y2 = 0.2613
```

**Output:** JPEG images at 95% quality.

### 5. Template Matching for Cards

**For each page:**

1. **Render page at 300 DPI**:
   ```python
   mat = page.get_pixmap(dpi=300)
   img = np.frombuffer(mat.samples, dtype=np.uint8)
   ```

2. **Try each template pattern**:
   - `4_cards_portrait` (2x2 grid)
   - `4_cards_landscape` (2x2 grid)
   - `2_cards_portrait` (1x2 grid)
   - `1_card_portrait` (single card)
   - `1_card_landscape` (single card)

3. **Extract card regions using grid coordinates**:
   ```python
   for (x1_pct, y1_pct, x2_pct, y2_pct) in template['grid']:
       x1 = int(page_width * x1_pct)
       y1 = int(page_height * y1_pct)
       x2 = int(page_width * x2_pct)
       y2 = int(page_height * y2_pct)
   ```

4. **Create new PDF for each card**:
   - Use PyMuPDF to crop page to card coordinates
   - Save as separate PDF

**Team prefix:**
- Cards get team prefix: `{team}_page02_card1.pdf`
- Only added when team name is successfully extracted

### 6. Token Extraction from Card

**Conditions for token extraction:**
- Card must contain "TOKEN GUIDE" or "EQUIPMENT TOKENS" in text
- Only process token guide cards

**Token detection:**

1. **Render card at 150 DPI** (lower DPI for faster processing):
   ```python
   pixmap = page.get_pixmap(dpi=150)
   ```

2. **Convert to grayscale**:
   ```python
   gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
   ```

3. **Apply binary threshold**:
   ```python
   _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
   ```
   - Threshold: 240 (near-white becomes black, everything else white)
   - Inverts: tokens become white on black background

4. **Find contours**:
   ```python
   contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
   ```

5. **Filter contours by area**:
   - Minimum area: 1000 pixels² (removes noise)
   - Maximum area: 70% of page (removes page border)

6. **Merge nearby contours**:
   - See "Token Merging Algorithm" section below

7. **Extract each token**:
   ```python
   x, y, w, h = cv2.boundingRect(contour)
   token_img = img[y:y+h, x:x+w]
   ```

8. **Save as PNG**:
   - Filename: `{team}_page{XX}_card{Y}_token{ZZ}.png`
   - ZZ: Zero-padded token number (01, 02, ...)

### 7. Extract Token Names

**For each token guide card:**

1. **Extract text elements from PDF**:
   ```python
   text_dict = page.get_text("dict")
   ```

2. **Find token name labels**:
   - Text blocks near token images
   - Usually positioned RIGHT or BELOW tokens
   - Font size filter (not too small, not too large)

3. **Match tokens to names**:
   - Calculate distance from token to each text label
   - Assign closest label to each token
   - 1-to-1 matching (each token gets one name)

4. **Save mapping**:
   ```json
   {
     "kommandos_page06_card1_token01.png": "Breach",
     "kommandos_page06_card1_token02.png": "Smoke grenade"
   }
   ```

---

## Token Merging Algorithm

**Problem:** Some tokens are split across multiple contours (e.g., octagon tokens with central hole).

**Solution:** Union-Find algorithm to merge nearby similar-sized contours.

### Merging Criteria

All conditions must be met:

1. **Distance threshold**: `20 pixels * (150 DPI / 72 DPI) = 41.67 pixels`
   - Scaled based on DPI

2. **Size similarity**: `area_ratio < 3.0`
   - Larger contour / smaller contour < 3
   - Prevents merging tiny fragments with large pieces

3. **Aspect ratio**: `merged_aspect < 2.5`
   - Merged result width/height ratio < 2.5
   - Prevents elongated merged shapes

### Merge Process

1. **Initialize Union-Find**:
   - Each contour starts as its own set

2. **Check all pairs**:
   - For each pair (i, j), check distance and size criteria
   - If pass, union(i, j)

3. **Group by root**:
   - All contours with same root belong to same group

4. **Combine bounding boxes**:
   ```python
   min_x = max(0, min(xs) - 2)  # 2-pixel padding
   min_y = max(0, min(ys) - 2)
   max_x = max(x + w for x, w in zip(xs, ws)) + 2
   max_y = max(y + h for y, h in zip(ys, hs)) + 2
   ```

**Padding:** 2 pixels added to all sides to prevent edge cutoff.

---

## Special Cases

### Custom Tokens (Config-Defined)

**Problem:** Some teams have custom token images in PDF that aren't part of standard tokens.

**Solution:** Filter out tokens matching custom token names from config.

**Example** (`config/team-config.yaml`):
```yaml
teams:
  hearthkyn-salvagers:
    tokens:
      - name: "Void Armor"
        shape: "round"
      - name: "Breach marker"
        shape: "octagon"
```

Tokens named "Void Armor" or "Breach marker" will be extracted separately.

### Team Name Extraction Failures

**Fallback:** If team name can't be extracted:
- Cards saved without team prefix: `page02_card1.pdf` instead of `kommandos_page02_card1.pdf`
- Warning logged
- Continues processing (cards still usable)

---

## Error Handling

### PDF Access Errors

```python
def _safe_unlink(path: Path, retries: int = 3, delay: float = 0.2)
```

**Handles:** Windows file locking issues when deleting/recreating PDFs.

**Strategy:**
- Remove read-only flag: `os.chmod(path, stat.S_IWRITE)`
- Retry up to 3 times with 0.2s delay
- Raise exception if still fails

### Template Matching Failures

**Logs warning if no templates match:**
```
WARNING: No cards extracted from page X
```

**Common causes:**
- PDF structure different from expected
- Page is notes/fluff (not datacards)
- Template coordinates need adjustment

---

## Configuration Files

### Extraction Templates

`config/pipelines/warcom/extraction-templates.json`:

```json
{
  "300dpi": {
    "4_cards_portrait": {
      "grid": [
        [0.0, 0.0, 0.5, 0.5],    // Top-left
        [0.5, 0.0, 1.0, 0.5],    // Top-right
        [0.0, 0.5, 0.5, 1.0],    // Bottom-left
        [0.5, 0.5, 1.0, 1.0]     // Bottom-right
      ]
    }
  }
}
```

**Coordinates:** Normalized (0.0 - 1.0) for DPI independence.

### Team Config

See `config/team-config.yaml` for:
- Canonical team names
- Aliases for matching
- Token shapes
- Custom token definitions

---

## Performance

**Typical runtime (single team):**
- Card extraction: ~30-60 seconds
- Token extraction: ~10-20 seconds per token guide card

**Bottleneck:** PDF rendering at 300 DPI (CPU-bound)

**Parallelization:** Use `--workers N` in pipeline orchestrator.

---

## Design Decisions

### Why Template Matching Instead of OCR?

**Advantages:**
- Deterministic (same input = same output)
- Fast (no ML models)
- Reliable for standardized layouts

**Disadvantages:**
- Breaks if PDF structure changes
- Requires pre-defined templates

**Chosen because:** Warcom PDFs have consistent structure.

### Why 300 DPI for Cards?

- High quality for printing
- Matches TTS requirements
- Standard for PDF rendering

### Why 150 DPI for Token Detection?

- Faster processing (1/4 pixels)
- Sufficient for contour detection
- Tokens re-rendered later at target resolution

### Why Union-Find for Merging?

**Alternative:** Iterative greedy merging

**Union-Find advantages:**
- O(n log n) complexity
- Transitive merging (A→B, B→C means A→C automatically)
- Prevents duplicate merges

---

**Last Updated**: February 16, 2026
