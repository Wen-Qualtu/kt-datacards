# Token Extraction Analysis - Existing Pipelines

## Overview
Analysis of token extraction approaches in existing kt-datacards pipelines to understand what worked and inform the new kt-app pipeline implementation.

---

## Warcom Pipeline (pipelines/warcom/)

### Step 2b: Initial Token Detection (`2b_card_extractor.py`)

**Purpose**: Rough extraction of token regions from token guide cards

**Detection Method**:
```python
# 1. Convert to grayscale
gray = cv2.cvtColor(img_no_header, cv2.COLOR_BGR2GRAY)

# 2. FIXED threshold (200) - NOT Otsu
_, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

# 3. Light morphological CLOSE (3x3 ellipse, 1 iteration)
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

# 4. Find contours
contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# 5. Pre-filter noise (min 500 pixels)
contours_to_merge = [c for c in contours if cv2.contourArea(c) >= 500]

# 6. Merge split tokens (intelligent union-find algorithm)
merged_contours = _merge_nearby_contours(contours_to_merge)

# 7. Filter by area and aspect ratio
min_area = 1000
max_aspect_ratio = 3.0
token_contours = [c for c in merged if area >= min_area and (w/h) <= max_aspect_ratio]

# 8. Statistical text filtering (remove short, wide elements)
# Height < 62% median, AR >= 1.25, Area < 80% median = text-like
```

**Smart Contour Merging** (`_merge_nearby_contours`):
- Only merge if at least ONE contour is undersized (<70% of median area)
- Calculate median from top 60% of contours to avoid small pieces lowering baseline
- Scale merge distance based on token size (30% of typical size)
- Uses union-find algorithm to group nearby undersized pieces
- Prevents merging normal-sized tokens in grid layouts

**Output**: Rough-cropped token images saved to `layers/warcom/extracted/{team}/tokens/`

**Key Insights**:
- ✅ Fixed threshold (200) more consistent than Otsu across different card layouts
- ✅ Intelligent merging handles tokens split by white decorative bands
- ✅ Statistical filtering removes text rows without losing tokens
- ⚠️ Still struggles with columnar layouts (pathfinders: 12 tokens merge into 2 columns)

---

### Step 4: Template-Based Shape Extraction (`4_token_extraction.py`)

**Purpose**: Apply precise shape cutouts to rough-extracted tokens

**Key Approach - Token != Detection Shape**:
```
ROUGH DETECTION → FIND CONTENT BOUNDS → APPLY PERFECT SHAPE → SCALE TO FIXED SIZE
```

**Workflow**:

1. **Match tokens to text labels**:
   - Text positioned RIGHT or BELOW tokens (never left/above)
   - Handle coordinate scale differences (detection DPI vs text extraction DPI)
   - Calculate distances with column/row alignment priorities
   - Greedy 1-to-1 assignment (best matches first)

2. **Look up shape from team config**:
   ```yaml
   tokens:
     - name: "Breach"
       shape: "round"
     - name: "Omniscanner"  
       shape: "octagon"
     - name: "Damnation Points"
       shape: "operative"
   ```

3. **Load shape template** (from `config/defaults/tts-token/input/`):
   - `round-template.png`
   - `octagon-template.png`
   - `diamond-template.png`
   - `operative-template.png` (larger, rounded square)

4. **Detect content bounds** (multi-strategy scoring):
   ```python
   # Strategy 1: Simple white removal (HSV, s<20 v>235)
   # Strategy 2: Tight threshold + minimal dilation
   # Strategy 3: Tight + moderate dilation  
   # Strategy 4: Loose threshold + minimal dilation
   
   # Score by: coverage (20-70%), aspect ratio (0.7-1.4), edge margins
   # Pick best strategy
   ```

5. **Create perfect shape mask**:
   ```python
   if shape == 'round':
       # Perfect circle at content center
       radius = min(content_width, content_height) / 2.0
   else:
       # Scale template to match content size
       scale_x = content_width / template_width
       scale_y = content_height / template_height
       # Resize and place at content center
   ```

6. **Apply 5% inset** (shrink mask inward to avoid edge artifacts)

7. **Fill small transparent holes** (<2% of template area, 2 passes)

8. **Crop to template bounds**

9. **Resize to fixed size** (512x512 for all tokens)

**Output**: Clean tokens with perfect shapes, transparent backgrounds, consistent size

**Key Insights**:
- ✅ **Separation of concerns**: Detection doesn't need to be perfect, just good enough to find content
- ✅ **Fixed shape templates**: Guarantees perfect shape regardless of detection quality
- ✅ **Multi-strategy content detection**: Handles varying token designs (solid fills, gradients, decorations)
- ✅ **Statistical scoring**: Objective criteria (coverage, aspect, margins) picks best detection
- ✅ **Consistent output**: All tokens normalized to same dimensions

---

## Script/Tools Pipeline (`script/tools/extract_tokens.py`)

**Similar Approach**:
- Uses contour detection for initial rough extraction
- Applies shape templates from config
- Handles split token images (Values 1/2 double-tokens)
- Post-processes text labels to improve matching

**Differences**:
- More focus on text extraction heuristics (grouping multi-line labels)
- Split detection for adjacent tokens mistakenly merged
- Uses cached template alpha masks for cookie-cutter extraction
- Integrates directly with team config for shape lookup

---

## Current kt-app Pipeline Issues

**What We Have Now** (Step 2 classification):
- Contour detection with filters
- Text extraction with coordinates
- **PROBLEM**: Trying to get perfect 1:1 match between text and contours

**Why This Fails**:
- ❌ Columnar layouts merge tokens (pathfinders: 12 names → 2 images)
- ❌ Decorative elements create extra detections (mandrakes: 11 names → 17 images)
- ❌ No shape templates applied yet
- ❌ Overly dependent on detection accuracy

---

## Recommended Approach for kt-app

### Phase 1: Rough Detection (Step 2 - Classification)
**Goal**: Find approximate token regions, don't worry about perfect matches

```python
# Extract metadata for token extraction step:
{
  "tokens": {
    "names": [
      {"name": "Omniscanner", "position": {"x": 41, "y": 105}, "type": "token"}
    ],
    "regions": [  # Rough contour detections
      {"position": {"x": 135, "y": 232}, "dimensions": {"width": 167, "height": 160}}
    ]
  }
}
```

**Don't require equal counts** - mismatches are expected and handled in extraction step

### Phase 2: Token Extraction (Step 3 - NEW)
**Goal**: Extract clean tokens with perfect shapes

**Workflow**:
1. **Match text to regions** (spatial proximity, flexible matching)
2. **Look up shape** from team config (or infer from name patterns)
3. **Extract rough region** from high-res PDF (with padding)
4. **Detect content bounds** (multi-strategy white removal)
5. **Apply shape template** (scaled to content, perfect circle/octagon/etc)
6. **Apply inset** (5% shrink)
7. **Fill holes** (2 passes)
8. **Resize to 512x512**

**Key Benefits**:
- ✅ Flexible text-to-region matching handles mismatches
- ✅ Shape templates guarantee perfect output regardless of detection
- ✅ High-res PDF extraction (300+ DPI) for quality
- ✅ Consistent output dimensions for TTS

---

## Summary

**What Works**:
- Fixed threshold (200) > Otsu for consistency
- Intelligent contour merging for split tokens
- Statistical text filtering
- **Template-based shape extraction** (not relying on perfect detection)
- Multi-strategy content detection with scoring
- Separation of rough detection from final extraction

**What Doesn't Work**:
- Requiring 1:1 match between text and contours in classification step
- Relying on contour detection for final token shape
- Otsu thresholding (inconsistent across layouts)

**Path Forward**:
1. Keep current Step 2 for rough detection (accept mismatches)
2. Implement Step 3 (token extraction) with template-based approach
3. Use team config for shape definitions
4. Apply proven warcom strategies (content detection, template scaling, insets)
