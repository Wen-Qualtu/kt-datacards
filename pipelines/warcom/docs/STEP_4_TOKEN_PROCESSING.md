# Step 4: Token Name Matching and Processing

## Purpose

Match rough-cropped tokens from Step 2 to their display names, apply shape-specific templates, make backgrounds transparent, and scale to target resolution (512×512px).

---

## Script

`pipelines/warcom/steps/4_token_extraction.py`

---

## Input

- **Tokens**: `layers/warcom/extracted/{team}/tokens/*.png` (rough crops from Step 2)
- **Names**: `layers/warcom/extracted/{team}/tokens/token-names.json` (name mapping from Step 2)
- **Config**: `config/team-config.yaml` (token shapes)
- **Templates**: `config/defaults/tts-token/*.png` (shape cutters)

---

## Output

- **Directory**: `output/{team}/tokens/*.png`
- **Filename**: `{team}_{token-name}.png`
  - Example: `kommandos_breach.png`
- **Format**: PNG with transparent background, 512×512px

---

## Execution Order

### 1. Load Team Configuration

```python
config = yaml.safe_load(open('config/team-config.yaml'))
tokens = config['teams'][team_name].get('tokens', [])
```

**Token configuration format:**
```yaml
teams:
  hearthkyn-salvagers:
    tokens:
      - name: "Void Armor"
        shape: "round"
      - name: "Breach marker"
        shape: "octagon"
```

**Supported shapes:**
- `round` - Circular tokens
- `octagon` - Octagonal tokens
- `diamond` - Diamond-shaped tokens
- `operative` - Operative portrait tokens (square with rounded corners)

### 2. Load Token Names from JSON

```python
with open('layers/warcom/extracted/{team}/tokens/token-names.json') as f:
    token_names = json.load(f)
```

**Format:**
```json
{
  "kommandos_page06_card1_token01.png": "Breach",
  "kommandos_page06_card1_token02.png": "Smoke grenade"
}
```

### 3. Match Tokens to Configured Shapes

**For each token file:**

1. **Get token name from JSON**:
   ```python
   token_name = token_names.get(filename, "")
   ```

2. **Look up shape in config**:
   ```python
   shape = get_token_shape(team_config, token_name)
   ```

3. **Matching logic**:
   - Normalize both names (lowercase, strip suffixes like "token", "marker")
   - Compare: `"Breach marker"` matches config name `"Breach"`
   - Return shape or `None` if no match

4. **Default shape**:
   - If no config match: `round` (most common)

### 4. Load Shape Template

**Template files:**
```
config/defaults/tts-token/input/
├── template-round-cutter.png         # Circular mask
├── template-octagon-cutter.png       # Octagonal mask
├── template-diamond-cutter.png       # Diamond mask
└── template-operative-cutter.png     # Square with rounded corners
```

**Template properties:**
- Size: 512×512px
- Format: PNG with alpha channel
- Black regions = cut (transparent)
- White regions = keep (opaque)

### 5. Process Each Token

#### 5.1 Load Token Image

```python
token_img = cv2.imread(token_path, cv2.IMREAD_UNCHANGED)
```

**Format:** PNG from Step 2 (rough crop, variable size)

#### 5.2 Resize to 512×512

```python
token_resized = cv2.resize(token_img, (512, 512), interpolation=cv2.INTER_LANCZOS4)
```

**Interpolation:** LANCZOS4 (high quality resampling)

**Aspect ratio:** Not preserved (may distort). Tokens are assumed to be roughly square.

#### 5.3 Make Background Transparent

**Color threshold method:**

```python
# Convert to HSV
hsv = cv2.cvtColor(token_img, cv2.COLOR_BGR2HSV)

# Define white color range
lower_white = np.array([0, 0, 200])
upper_white = np.array([180, 30, 255])

# Create mask (white pixels → True)
mask = cv2.inRange(hsv, lower_white, upper_white)

# Apply transparency
alpha = np.where(mask == 255, 0, 255).astype(np.uint8)
token_rgba = cv2.cvtColor(token_img, cv2.COLOR_BGR2BGRA)
token_rgba[:, :, 3] = alpha
```

**Why HSV?**
- Better for color-based selection than RGB
- Hue-independent brightness detection

**Thresholds:**
- Value (brightness): 200-255 (near white)
- Saturation: 0-30 (low color intensity)
- Hue: 0-180 (all colors, irrelevant for white detection)

#### 5.4 Apply Shape Template

```python
# Load template (black/white mask)
template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)

# Resize template to match token size
template_resized = cv2.resize(template, (512, 512))

# Apply template to alpha channel
alpha_final = cv2.bitwise_and(token_rgba[:, :, 3], template_resized)
token_rgba[:, :, 3] = alpha_final
```

**Effect:** Cuts token into configured shape.

**Template encoding:**
- Black (0) = Make transparent
- White (255) = Keep opaque

#### 5.5 Save Final Token

```python
output_path = f"output/{team}/tokens/{team}_{slugified_name}.png"
cv2.imwrite(output_path, token_rgba)
```

**Filename:** Slugified display name (lowercase, spaces→hyphens).

---

## Token Name Matching Algorithm

**Problem:** Token images and display names need to be paired.

**Approach:** Spatial proximity matching (from Step 2).

### Coordinate Scale Detection

**Issue:** Tokens detected at 150 DPI, text extracted at 300 DPI → 2:1 scale difference.

**Solution:**
1. Calculate coordinate ranges for both tokens and text
2. Detect scale ratio: `label_range / token_range ≈ 2.0`
3. Scale text coordinates to match token coordinates

### Matching Criteria

**Constraints:**
1. Same source card (page + card number)
2. Text RIGHT of token's right edge OR BELOW token's bottom edge
3. Distance within thresholds:
   - Horizontal: `max_x_distance = 600px`
   - Vertical: `max_y_distance = 1200px`

**Prioritization:**
- Labels BELOW token: Prioritize horizontal alignment (column matching)
  - `priority = (dx * 1.5) + (dy * 0.3)`
- Labels RIGHT of token: Prioritize vertical alignment (row matching)
  - `priority = (dy * 1.5) + (dx * 0.3)`

**Assignment:**
- 1-to-1 matching (each token gets one label)
- Greedy: Assign lowest priority (closest) first
- Prevent duplicate assignments

---

## Custom Token Filtering

**Problem:** Some teams have custom tokens (non-standard shapes/designs).

**Solution:** Define custom tokens in config, filter during processing.

**Example:**
```yaml
teams:
  hearthkyn-salvagers:
    tokens:
      - name: "Void Armor"
        shape: "round"
        custom: true  # Special processing
```

**Effect:** Custom tokens are handled separately (not matched to standard templates).

---

## Error Handling

### Missing Token Names

**Symptom:**
```
WARNING: No name mapping found for kommandos_page06_card1_token01.png
```

**Cause:** Step 2 didn't extract token names (text matching failed).

**Recovery:**
- Token skipped
- Log warning
- Continue processing other tokens

### Template Not Found

**Symptom:**
```
ERROR: Template not found: config/defaults/tts-token/round-cutter.png
```

**Cause:** Missing shape template file.

**Recovery:**
- Skip token
- Log error
- Requires manual fix (add template file to `config/defaults/tts-token/input/`)

### Invalid Image Format

**Symptom:**
```
WARNING: Failed to load token image: kommandos_page06_card1_token01.png
```

**Cause:**
- Corrupted PNG
- Unsupported format
- File locked

**Recovery:** Skip token, log warning.

---

## Output Structure

```
output/kommandos/tokens/
├── kommandos_breach.png              # 512×512, transparent background, round shape
├── kommandos_smoke-grenade.png       # 512×512, transparent background, round shape
├── kommandos_conceal.png
└── kommandos_engage.png
```

**Properties:**
- Format: PNG with alpha channel
- Size: 512×512 pixels
- Background: Transparent
- Shape: Applied via template
- Filename: Team + slugified token name

---

## Performance

**Typical runtime (per team):**
- Token matching: ~1-2 seconds
- Image processing: ~0.5 seconds per token
- Total: ~10-20 seconds for 20 tokens

**Bottleneck:** Image resizing and template application (CPU-bound)

**Not parallelized:** Single-threaded processing (fast enough).

---

## Design Decisions

### Why 512×512 Resolution?

**Requirements:**
- TTS token minimum: 256×256
- Visual clarity: Higher is better
- File size: Must be reasonable

**Chosen:** 512×512 balances quality and file size (~50-100KB per token).

### Why Template-Based Shape Cutting?

**Alternatives:**
1. Procedural shape generation → Complex math
2. Contour tracing → Inaccurate for imperfect tokens
3. Template masking → Simple, reliable

**Advantages:**
- Consistent shapes across all tokens
- Easy to add new shapes (just add PNG)
- High quality anti-aliasing

### Why White Background → Transparent?

**Problem:** Tokens cropped from PDF have white backgrounds.

**Solution:** HSV threshold to detect near-white pixels.

**Why not chroma key?**
- Tokens have variety of colors
- White is consistent background color
- Simple threshold works reliably

### Why Normalize Token Names?

**Problem:** Text extraction may include suffixes like "token", "marker".

**Solution:** Strip common suffixes before matching:
```python
for suffix in [' token', ' marker', ' tokens', ' markers']:
    if name.endswith(suffix):
        name = name[:-len(suffix)]
```

**Benefit:** More flexible matching (config doesn't need exact text).

---

## Maintenance

### Adding New Token Shapes

1. Create template PNG (512×512):
   - Black regions = transparent after application
   - White regions = opaque after application
2. Save to `config/defaults/tts-token/input/{shape}-cutter.png`
3. Add to config:
   ```yaml
   tokens:
     - name: "New Token"
       shape: "new-shape"
   ```

### Updating Matching Algorithm

**Common scenarios:**
- Text layout changes: Adjust distance thresholds
- New coordinate scales: Update scale detection
- Custom matching rules: Add special cases

### Debugging Token Matching

**Enable debug logging:**
```bash
python pipelines/warcom/steps/4_token_extraction.py --log-level DEBUG
```

**Check:**
- Coordinate scales (should be ~2.0 ratio)
- Distance calculations
- Priority scores
- Assignment results

---

**Last Updated**: February 16, 2026
