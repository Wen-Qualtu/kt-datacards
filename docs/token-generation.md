# Token Generation for TTS

## Overview

This document describes the automated pipeline for generating Kill Team token objects for Tabletop Simulator (TTS). Tokens are extracted from PDF marker/token guide pages and converted into infinite bags that can spawn unlimited copies.

## Architecture

### Components

1. **Token Extraction** (`script/tools/extract_tokens.py`)
  - Extracts individual token images from marker/token guide pages
  - Uses PDF text extraction for token names (falls back to OCR)
  - Writes extracted PNGs under `processed/extracted-tokens/{team}/`

2. **Transparency Pass** (`script/tools/add_token_transparency_bg_sample.py`)
  - Learns the background greys from `config/defaults/token-bg-sample.png`
  - Removes only border-connected background (avoids punching holes in art)
  - Overwrites extracted token PNGs in-place (adds/updates alpha)

3. **Packaging + Embedding** (main pipeline)
  - Packages ready tokens into `output_v2/{faction}/{team}/tts/token/`
  - Embeds token bags into ready team boxes during `script/run_pipeline.py`

### Data Flow

**Current Method:**
```
PDF marker/token guide → script/tools/extract_tokens.py → processed/extracted-tokens/{team}/*.png
                                                      ↓
                             script/tools/add_token_transparency_bg_sample.py (in-place alpha)
                                                      ↓
                                   script/run_pipeline.py (packages + embeds into output_v2)
```

## Token Types

### Operative Tokens
- Pentagon/hexagon shaped ability markers
- Scale: 0.24
- Tags: `KTUIToken`, `KTUITokenSimple`
- Examples: "Victory Shriek", "Call the Kill"

### Round Tokens
- Circular condition/objective markers
- Scale: 0.228
- Tags: `KTUIMarker`, `KTUIToken`
- Examples: "Meat", "Trophy", "Pechra"

## Usage

### 1. Extract Tokens from PDF (with Transparency)

**Extract tokens:**
```bash
poetry run python script/tools/extract_tokens.py --team farstalker-kinband
```

**Output:**
- `processed/extracted-tokens/{team}/*.png` - Individual token images
- `processed/extracted-tokens/{team}/extraction-metadata.json` - Token metadata

**Benefits:**
- ✅ Extracts directly from PDF (better quality)
- ✅ No JPG intermediate (no double conversion)
- ✅ Deterministic output for downstream tooling

**Metadata Format:**
```json
{
  "team": "farstalker-kinband",
  "tokens_extracted": 10,
  "tokens": [
    {
      "filename": "meat.png",
      "name": "Meat",
      "shape": "round",
      "dimensions": {"width": 200, "height": 199}
    }
  ]
}
```

### 2. Add Transparency

Apply alpha to extracted token PNGs (in-place):
```bash
poetry run python script/tools/add_token_transparency_bg_sample.py --team farstalker-kinband \
  --bg-sample config/defaults/token-bg-sample.png
```

### 3. Package + Embed Tokens

Run the pipeline to package/embed ready tokens:
```bash
poetry run python script/run_pipeline.py --step all
```

**Output:**
- `output_v2/{faction}/{team}/tts/token/*.png` - Token images (GitHub hosted)
- `tts_objects/tokens/{team}/*-bag.json` - Individual infinite bags
- `tts_objects/tokens/{team}/{team}-all-tokens.json` - Master bag (optional)

## TTS Object Structure

### Custom_Token (Individual Token)

```json
{
  "Name": "Custom_Token",
  "CustomImage": {
    "ImageURL": "https://raw.githubusercontent.com/.../token.png",
    "CustomToken": {
      "Thickness": 0.1,
      "MergeDistancePixels": 10.0,
      "StandUp": false,
      "Stackable": false
    }
  }
}
```

### Custom_Model_Infinite_Bag

```json
{
  "Name": "Custom_Model_Infinite_Bag",
  "CustomMesh": {
    "MeshURL": "https://steamusercontent-a.akamaihd.net/ugc/.../",
    "TypeIndex": 7
  },
  "ContainedObjects": [/* token object */],
  "ChildObjects": [/* token object template */]
}
```

- **ContainedObjects**: Initial contents (one token)
- **ChildObjects**: Template for spawned tokens
- **MeshURL**: Invisible container mesh from Hearthkyn Salvagers

### Master Bag Structure

Regular TTS `Bag` object containing all infinite bags:
- Bags arranged in 4-column grid
- Spacing: 2.5 units between bags
- Tags: `KTUITokenBag`

## File Structure

```
output_v2/
  {faction}/
    {team}/
      tts/
        token/
          {team}-{token-name}.png  # Token images (transparent)

tts_objects/
  tokens/
    {team}/
      {token-name}-bag.json        # Individual infinite bags
      {team}-all-tokens.json       # Master bag (optional)

assets/
  extracted-tokens/
    {team}/
      {token-name}.png             # Extracted tokens
      extraction-metadata.json     # Metadata
```

## Integration with Main Pipeline

### Future Integration

The token generation should be integrated into the main processing pipeline:

1. **After PDF processing**: Extract tokens from faction-rules PDF
2. **Apply transparency**: Automatically process all extracted tokens
3. **Generate bags**: Create TTS objects alongside card decks

### Configuration

Add to `config/team-config.yaml`:

```yaml
teams:
  farstalker-kinband:
    faction: xenos
    tokens:
      enabled: true
      transparency_threshold: 235
      generate_master_bag: true
```

## Quality Checks

### Token Extraction
- ✅ All tokens identified with correct names
- ✅ Shapes correctly classified (operative vs round)
- ✅ Token boundaries properly detected

### Transparency
- ✅ White background fully removed
- ✅ Token edges smooth (no jagged artifacts)
- ✅ Token content preserved (no detail loss)

### TTS Objects
- ✅ Individual bags spawn correct tokens
- ✅ Master bag contains all token bags
- ✅ URLs point to correct GitHub raw files

## Troubleshooting

### Token Names Not Detected
- Check PDF has embedded text (not scanned image)
- Verify marker guide is last page of PDF
- Fallback: Uses filename as token name

### Transparency Issues
- Adjust `--threshold` parameter
- Lower threshold (30-40) for less aggressive removal
- Higher threshold (60-80) for more aggressive removal
- Use `--simple` flag for brightness-based method if flood fill doesn't work
- Check source image quality

**Testing different thresholds:**
```bash
# Less aggressive (keeps more detail, may leave some background)
poetry run python script/tools/add_token_transparency_bg_sample.py --team farstalker-kinband \
  --bg-sample config/defaults/token-bg-sample.png --threshold 14

# More aggressive (removes more background, may lose some detail)
poetry run python script/tools/add_token_transparency_bg_sample.py --team farstalker-kinband \
  --bg-sample config/defaults/token-bg-sample.png --threshold 22
```

### Bags Not Working in TTS
- Verify PNG files uploaded to GitHub50
- Check GitHub raw URLs are accessible
- Ensure transparency properly applied (RGBA mode)

## Example Workflow

Complete workflow for a new team:

```bash
# 1. Extract token PNGs
poetry run python script/tools/extract_tokens.py --team farstalker-kinband

# 2. Apply transparency (in-place)
poetry run python script/tools/add_token_transparency_bg_sample.py --team farstalker-kinband \
  --bg-sample config/defaults/token-bg-sample.png

# 3. Package + embed tokens
poetry run python script/run_pipeline.py --step all

# 4. Commit to GitHub
git add output_v2/xenos/farstalker-kinband/tts/token/*.png
git add tts_objects/tokens/farstalker-kinband/*.json
git commit -m "Add tokens for Farstalker Kinband"
git push

# 5. Test in TTS
# Objects → Saved Objects → Import
# Select the generated team object(s) under tts_objects/
```

## Technical Details

### Mesh URL Origin
- Source: Hearthkyn Salvagers TTS workshop mod
- URL: `https://steamusercontent-a.akamaihd.net/ugc/1666858152071990826/9AD455F2CBAEC01B2CBCDDB8B6DC4CE48D14B545/`
- Type: Invisible container mesh for infinite bags
- No external dependency - URL is stable Steam content

### Token Scales
- Operative: 0.24 (larger, complex shapes)
- Round: 0.228 (slightly smaller, circular)
- Based on Kill Team token physical sizes

### Image Requirements
- Format: PNG with RGBA
- Transparency: Required for proper TTS cutout
- Resolution: ~200x200 pixels (extracted from PDF)
- Compression: Standard PNG compression

## Future Enhancements

### Short Term
- [ ] Integrate into main processing pipeline
- [ ] Add validation checks for generated objects
- [ ] Support custom token shapes/scales

### Long Term
- [ ] Download and host our own mesh files
- [ ] Support multi-sided tokens (flip tokens)
- [ ] Generate token preview images
- [ ] Batch processing for all teams

## References

- TTS Custom Token Documentation
- TTS Infinite Bag Mechanics
- Kill Team Token Types
- Hearthkyn Salvagers Workshop Mod (reference implementation)
