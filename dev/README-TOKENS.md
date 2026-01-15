# Dev Scripts - Token Generation

Quick reference for token generation scripts.

## Token Workflow

### New Single-Pass Method (Recommended)

**1. Extract with Transparency**
```bash
python dev/extract_tokens_v2.py --team farstalker-kinband --dpi 300 --threshold 50
```
- Extracts directly from PDF at high DPI
- Applies transparency immediately
- Output: `dev/extracted-tokens/{team}/*.png`

**2. Generate Bags**
```bash
python dev/generate_infinite_bags.py --team farstalker-kinband --create-master-bag
```
- Creates infinite bag for each token
- Optional master bag
- Output: `tts_objects/tokens/{team}/*.json`

### Legacy Two-Pass Method

**1. Extract Tokens**
```bash
python dev/extract_tokens.py --team farstalker-kinband
```
- Extracts tokens from JPG marker guide
- Output: `dev/extracted-tokens/{team}/*.png`

**2. Add Transparency**
```bash
python dev/add_token_transparency.py --team farstalker-kinband --threshold 50
```
- Removes backgrounds using flood fill
- Overwrites PNGs

**3. Generate Bags**
```bash
python dev/generate_infinite_bags.py --team farstalker-kinband --create-master-bag
```

## Files

### Token Extraction
- `extract_tokens_v2.py` - **NEW!** Extract from PDF with transparency (single pass)
- `extract_tokens.py` - Legacy: Extract from JPG
- `analyze_token_shapes.py` - Analyze token shapes

### Transparency (Legacy)
- `add_token_transparency.py` - Add transparency to extracted tokens
  - Only needed if using legacy `extract_tokens.py`
  - Not needed with `extract_tokens_v2.py`!

### TTS Generation
- `generate_infinite_bags.py` - Generate infinite bag objects (NEW!)
- `generate_tts_tokens.py` - Generate standalone token objects (legacy)

### Legacy/Utility
- `manage_token_meshes.py` - Download/manage mesh files
- `update_grid_mesh_urls.py` - Update mesh URLs in grid
- `update_tts_mesh_urls.py` - Update mesh URLs in TTS objects

## Output Locations

```
dev/extracted-tokens/
  {team}/
    *.png                    # Extracted tokens with transparency
    extraction-metadata.json # Token names and metadata

output_v2/
  {faction}/
    {team}/
      tts/
        token/
          {team}-*.png       # Final token images (GitHub hosted)

tts_objects/
  tokens/
    {team}/
      *-bag.json             # Individual infinite bags
      {team}-all-tokens.json # Master bag (optional)
```

## Common Issues

### Transparency not working?
```bash
# Try different thresholds
python dev/add_token_transparency.py --team farstalker-kinband --threshold 30   # Less aggressive
python dev/add_token_transparency.py --team farstalker-kinband --threshold 70   # More aggressive

# Or use simple brightness method
python dev/add_token_transparency.py --team farstalker-kinband --threshold 235 --simple
```

### Token names wrong?
- Check PDF has embedded text (not scanned)
- Tokens fallback to filename if name not found

### Bags not working in TTS?
- Ensure PNGs pushed to GitHub
- Check URLs are accessible via GitHub raw
- Verify transparency applied (RGBA mode)

## Documentation

See [docs/token-generation.md](../docs/token-generation.md) for complete documentation.
