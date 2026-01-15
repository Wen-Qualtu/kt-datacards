# Token Generation for TTS

## Overview

This document describes the automated pipeline for generating Kill Team token objects for Tabletop Simulator (TTS). Tokens are extracted from PDF marker/token guide pages and converted into infinite bags that can spawn unlimited copies.

## Architecture

### Components

1. **Token Extraction with Transparency** (`extract_tokens_v2.py`) ⭐ NEW
   - Extracts directly from PDF marker guide (last page)
   - Renders PDF at high DPI for maximum quality
   - Identifies token names from PDF text
   - Detects token shapes (operative vs round)
   - **Applies transparency immediately** (single pass)
   - Outputs PNG images with metadata

2. **Legacy Extraction** (`extract_tokens.py` + `add_token_transparency.py`)
   - Old two-step process (extract from JPG, then add transparency)
   - Still available but not recommended

3. **Infinite Bag Generation** (`generate_infinite_bags.py`)
   - Creates TTS infinite bag objects for each token
   - Generates master bag containing all token bags
   - Outputs TTS-compatible JSON files

### Data Flow

**New Single-Pass Method (Recommended):**
```
PDF (Faction Rules) → extract_tokens_v2.py → Transparent Token PNGs
                                                      ↓
                                          generate_infinite_bags.py
                                                      ↓
                                          TTS JSON bags + output_v2 assets
```

**Legacy Two-Pass Method:**
```
PDF → JPG extraction → extract_tokens.py → PNGs → add_token_transparency.py → Transparent PNGs
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

**Recommended - Single Pass:**
```bash
python dev/extract_tokens_v2.py --team farstalker-kinband --dpi 300 --threshold 50
```

**Parameters:**
- `--dpi`: PDF rendering resolution (default: 300)
  - Higher DPI = better quality but larger files
  - 300 DPI recommended for tokens
- `--threshold`: Transparency threshold (default: 50)
- `--no-transparency`: Skip transparency (extract only)

**Output:**
- `dev/extracted-tokens/{team}/*.png` - Individual token images (with transparency)
- `dev/extracted-tokens/{team}/extraction-metadata.json` - Token metadata

**Benefits:**
- ✅ Extracts directly from PDF (better quality)
- ✅ No JPG intermediate (no double conversion)
- ✅ Transparency applied immediately
- ✅ Single command instead of two

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

### 2. ~~Add Transparency~~ (No longer needed!)

**Not needed with extract_tokens_v2.py** - transparency is applied during extraction!

If using legacy `extract_tokens.py`, you can still use:
```bash
python dev/add_token_transparency.py --team farstalker-kinband --threshold 50
```

See legacy workflow section below for details.

### 2. Generate Infinite Bags

```bash
python dev/generate_infinite_bags.py --team farstalker-kinband --create-master-bag
```

**Options:**
- `--create-master-bag`: Create a master bag containing all token bags
- `--output-dir`: Base output directory (default: output_v2)
- `--tts-json-dir`: TTS JSON output (default: tts_objects/tokens)

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

dev/
  extracted-tokens/
    {team}/
      {token-name}.png             # Extracted tokens (with transparency)
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
python dev/add_token_transparency.py --team farstalker-kinband --threshold 30

# More aggressive (removes more background, may lose some detail)
python dev/add_token_transparency.py --team farstalker-kinband --threshold 70

# Use simple brightness method
python dev/add_token_transparency.py --team farstalker-kinband --threshold 235 --simple
```

### Bags Not Working in TTS
- Verify PNG files uploaded to GitHub50
- Check GitHub raw URLs are accessible
- Ensure transparency properly applied (RGBA mode)

## Example Workflow

Complete workflow for a new team:

```bash
# 1. Extract tokens with transparency (single command!)
python dev/extract_tokens_v2.py --team farstalker-kinband --dpi 300 --threshold 50

# 2. Generate bags
python dev/generate_infinite_bags.py --team farstalker-kinband --create-master-bag

# 4. Commit to GitHub
git add output_v2/xenos/farstalker-kinband/tts/token/*.png
git add tts_objects/tokens/farstalker-kinband/*.json
git commit -m "Add tokens for Farstalker Kinband"
git push

# 5. Test in TTS
# Objects → Saved Objects → Import
# Select: tts_objects/tokens/farstalker-kinband/farstalker-kinband-all-tokens.json
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
