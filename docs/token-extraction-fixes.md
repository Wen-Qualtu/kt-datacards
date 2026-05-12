# Token Extraction Issues and Fixes

## Fixed Issues

### 1. Ratlings - Swapped Tokens ✓
**Problem**: `evade.png` showed rations can, `purloined-rations.png` showed evade arrow  
**Fix**: Files swapped manually  
**Status**: FIXED

### 2. Mandrakes - Artifact Token ✓
**Problem**: `token-03.png` was incorrectly pointing to custom soul harvest area  
**Fix**: File deleted  
**Status**: FIXED

## Remaining Shape Detection Issues

### Root Causes

1. **White Content Elements Causing Mask Issues**
   - Tokens with white design elements (skulls, icons) confuse background removal
   - Current threshold: `v > 235 & s < 20` treats white content as background
   - Result: Incorrect content bounds, distorted aspect ratios

2. **Text Inclusion**
   - Text near tokens gets included in contour detection
   - Connected components capture text as part of token
   - Result: Weirdly shaped tokens with extra content

3. **Aspect Ratio Distortion**
   - Template fitting scales based on incorrect content bounds
   - When white areas are included, bounds are too wide/tall
   - Result: Compressed or stretched tokens

### Affected Tokens

| Team | Token | Issue |
|------|-------|-------|
| hierotek-circle | augment-weapon.png | Distorted hexagon (trapezoidal) |
| mandrakes | shadow-glyph.png | Squashed vertically (complex shape) |
| nemesis-claw | nemexix-claw-prescience-points.png | White in top left causes bad bounds |
| phobos-strike-team | vanguard.png | Cone shaped, white skull causes bad mask |
| raveners | subterranean-ambush.png | Cone with weird aspect ratio |
| wrecka-krew | breach.png | Includes text at bottom |
| pathfinders | multiple | Light grey shadows captured (acceptable for now) |

## Proposed Fixes

### Short-term Manual Fixes

1. **Add per-token overrides in config**
   ```yaml
   tokens:
   - name: Vanguard
     shape: operative
     extraction_params:
       background_threshold: 220  # Lower threshold to keep white skull
       crop_padding: 10  # Add padding to bounds
   ```

2. **Manual mask correction**
   - Pre-process problem tokens with custom masks
   - Store corrected masks in `config/token-masks/{team}/`

### Medium-term Code Improvements

1. **Improve Background Removal**
   ```python
   # Add adaptive thresholding based on token content
   # Use histogram analysis to detect true background vs white content
   # Consider edge detection to find token boundaries
   ```

2. **Better Text Filtering**
   ```python
   # Add OCR-based text detection
   # Remove text regions before contour detection
   # Use aspect ratio filtering (text is typically wide and short)
   ```

3. **Aspect Ratio Preservation**
   ```python
   # Calculate original token aspect ratio from PDF
   # Preserve AR during template fitting
   # Use content-aware cropping to exclude text/labels
   ```

### Long-term Solutions

1. **Machine Learning Approach**
   - Train model on known good tokens
   - Detect token boundaries more accurately
   - Handle complex shapes better

2. **Manual Review Tool**
   - Build UI for reviewing/correcting extracted tokens
   - Allow manual mask adjustment
   - Store corrections for reuse

## Implementation Priority

1. **High Priority** (manual fixes for now):
   - vanguard.png - white skull issue
   - breach.png - text inclusion
   - nemexix-claw-prescience-points.png - white area

2. **Medium Priority** (can work with current):
   - augment-weapon.png - distortion
   - shadow-glyph.png - squashed
   - subterranean-ambush.png - aspect ratio

3. **Low Priority** (acceptable):
   - pathfinders tokens - shadow capture issue
   - Complex shapes that need manual review anyway

## Next Steps

1. For problematic tokens: Add config overrides or manual corrections
2. Improve background removal algorithm to handle white content
3. Add text detection/removal step
4. Implement aspect ratio preservation
5. Consider building a review tool for batch correction
