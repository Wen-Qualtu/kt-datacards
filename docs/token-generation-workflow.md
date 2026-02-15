# Token Generation Workflow

This document describes the complete token generation workflow for Kill Team datacards, including lessons learned and best practices.

## Overview

The token generation process has multiple stages:
1. **Extraction** - Extract token images from PDF
2. **Processing** - Background removal and cleanup
3. **Asset Generation** - Create TTS-compatible files (.png, .obj, -dispenser.png)
4. **Individual Bags** - Generate individual token infinite bag JSONs
5. **Master Bag** - Generate master token bag with Lua scripts
6. **Embedding** - Add token bag to card box
7. **Metadata** - Update metadata and URLs

## Quick Start

For teams with `tokens_ready: true` in config:

```bash
# Generate tokens for a single team
poetry run python script/generate_team_tokens.py --team murderwings

# Generate tokens for multiple teams
poetry run python script/generate_team_tokens.py --team murderwings celestian-insidiant

# Extract from PDF and generate everything
poetry run python script/generate_team_tokens.py --team murderwings --extract
```

## Prerequisites

### 1. Token Images
Tokens must be in `processed/{team}/token/` as PNG files with transparent backgrounds.

File naming: `{token-slug}.png` (e.g., `warp.png`, `challenge.png`)

### 2. Configuration
Tokens must be defined in `config/team-config.yaml`:

```yaml
teams:
  murderwings:
    faction: chaos
    tokens_ready: true  # REQUIRED
    tokens:
      - name: "Warp"
        shape: round
      - name: "Challenge"
        shape: operative
      - name: "Damnation Points"
        shape: octagon
      - name: "Warp Fuel"
        shape: diamond
      - name: "Vox-casters"
        shape: diamond
```

**Supported shapes:**
- `round` - Circular tokens (e.g., Warp, Psyk-Out Grenades)
- `operative` - Elongated tokens (default for most operatives)
- `octagon` - 8-sided tokens (e.g., Damnation Points)
- `diamond` - Rotated square tokens (e.g., Warp Fuel, Vox-casters)

## File Structure

The token system uses multiple file locations:

### Input/Processing
```
processed/{team}/token/
  ├── {token-slug}.png            # Processed token images
  ├── warp.png
  └── challenge.png
```

### Output Assets
```
output_v2/{faction}/{team}/tts/token/
  ├── {team}-{token}-slug}.png           # Token image
  ├── {team}-{token-slug}.obj            # 3D mesh
  ├── {team}-{token-slug}-dispenser.png  # Dispenser image
  └── {team}-tokens.json                 # Master token bag
```

**Important:** Note the singular `token/` folder in output_v2 (not `tokens/`)

### TTS Objects
```
tts_objects/{team}/
  ├── {Team Display Name} Cards.json     # Card box with embedded tokens
  └── tokens/                            # Note: plural
      ├── {token-slug}.json              # Individual token infinite bags
      ├── challenge.json
      ├── warp.json
      └── {team}-tokenbag.json           # Copy of master bag for metadata
```

**Important:** Note the plural `tokens/` folder in tts_objects

## Detailed Workflow

### Stage 1: Extraction (Optional)

Extract tokens from PDF if not already processed:

```bash
poetry run python script/tools/extract_tokens.py --team murderwings
```

Input: `input/{team}.pdf`
Output: `dev/extracted-tokens-pdf/{team}/*.png`

### Stage 2: Processing

Remove backgrounds and prepare tokens:

```bash
poetry run python script/tools/add_token_transparency_bg_sample.py --team murderwings
```

Then manually move to `processed/{team}/token/`

### Stage 3: Asset Generation

**Master Script** (recommended):
```bash
poetry run python script/generate_team_tokens.py --team murderwings
```

**Or individual steps:**

#### 3a. Generate TTS Assets
Creates PNG, OBJ, and dispenser files with team prefixes:

```bash
poetry run python script/src/token_tools/generate_tts_tokens.py --team murderwings
```

Output: `output_v2/{faction}/{team}/tts/token/{team}-{token-slug}.*`

**Critical:** Files MUST have team prefix: `murderwings-warp.png`, NOT just `warp.png`

#### 3b. Generate Individual Token Bags
Creates individual infinite bag JSONs:

Output: `tts_objects/{team}/tokens/{token-slug}.json`

**Critical:** Files go in `tokens/` subdirectory (plural)

#### 3c. Generate Master Token Bag
Creates master bag with Lua scripts for Setup/Place/Recall:

```bash
poetry run python script/src/token_tools/generate_team_token_bag.py --team murderwings
```

Output: `output_v2/{faction}/{team}/tts/token/{team}-tokens.json`

This file contains:
- All individual token bags as ContainedObjects
- Lua script for token management
- Preset positions in 5-column grid
- GMNotes for identification

**Critical:** The script now correctly looks in the `tokens/` subdirectory

#### 3d. Embed Token Bag in Card Box
Adds token bag to card box ContainedObjects:

```bash
poetry run python script/src/token_tools/add_tokens_to_box.py --team murderwings --box-dir tts_objects/murderwings --output-dir output_v2
```

This step:
- Adds token bag to card box ContainedObjects
- Updates LuaScriptState with token bag position
- Positions token bag at x=5.5, z=-8.5

**Critical:** This step must run AFTER generating the master token bag

#### 3e. Copy for Metadata
Copy master bag to tts_objects for metadata generation:

```bash
Copy-Item "output_v2/{faction}/{team}/tts/token/{team}-tokens.json" "tts_objects/{team}/tokens/{team}-tokenbag.json"
```

### Stage 4: Update Metadata

Generate metadata and URLs:

```bash
poetry run python script/generate_tts_metadata.py
poetry run python script/generate_urls.py
```

## Common Issues & Solutions

### Issue 1: Wrong Folder Name
**Problem:** Tokens in `tokens/` instead of `token/` in output_v2
**Solution:** Output assets go in singular `token/`, TTS objects go in plural `tokens/`

### Issue 2: Missing Team Prefix
**Problem:** Files named `warp.png` instead of `murderwings-warp.png`
**Solution:** Always use `{team}-{token-slug}` naming in output_v2

### Issue 3: Missing .obj Files
**Problem:** Only PNG files created
**Solution:** Copy template .obj from existing team (e.g., blooded)

### Issue 4: Missing -dispenser.png Files
**Problem:** Only base token images
**Solution:** Copy from base token image with `-dispenser` suffix

### Issue 5: Token Bag Not in Card Box
**Problem:** Token bag exists but not embedded in card box
**Solution:** Run `add_tokens_to_box.py` script

### Issue 6: generate_team_token_bag.py Can't Find Tokens
**Problem:** Script reports "Only found 1 file"
**Solution:** Script now correctly looks in `tokens/` subdirectory (fixed in this session)

### Issue 7: Wrong Token Count in Metadata
**Problem:** Teams with tokens show 35 instead of 37
**Solution:** Ensure `{team}-tokenbag.json` exists in `tts_objects/{team}/tokens/`

## Token Shape Detection

When adding tokens to config, use this guide:

1. **Round** - Circularity > 0.75, looks circular
   - Examples: Warp tokens, Psyk-Out Grenades
   
2. **Octagon** - 8 detected corners
   - Examples: Damnation Points
   
3. **Diamond** - 4 corners, rotated square appearance
   - Examples: Warp Fuel, Vox-casters
   
4. **Operative** - Default for elongated tokens
   - Examples: Most character/operative tokens

Use `extract_token_shapes_from_images.py` to auto-detect shapes (in archive, not production).

## Validation Checklist

Before marking a team as complete:

- [ ] `tokens_ready: true` in config
- [ ] All tokens defined with correct names and shapes
- [ ] Processed PNGs in `processed/{team}/token/`
- [ ] Output assets with team prefix in `output_v2/{faction}/{team}/tts/token/`
- [ ] Individual bags in `tts_objects/{team}/tokens/`
- [ ] Master bag at `output_v2/{faction}/{team}/tts/token/{team}-tokens.json`
- [ ] Tokenbag copy at `tts_objects/{team}/tokens/{team}-tokenbag.json`
- [ ] Token bag embedded in card box (check ContainedObjects)
- [ ] Metadata updated (check timestamp in tts-metadata.json)
- [ ] URLs generated (check datacards-urls.json)

## Architecture Notes

### Why Two Locations for Token Bags?

1. **output_v2/{faction}/{team}/tts/token/{team}-tokens.json**
   - Published to GitHub
   - Used for in-game updates via URL
   - Contains complete token bag with all tokens
   
2. **tts_objects/{team}/tokens/{team}-tokenbag.json**
   - Used by metadata generation script
   - Contains timestamp in LuaScriptState for versioning
   - Local copy for change tracking

### Token Bag Lua Scripts

The master token bag includes Lua scripts for:
- **Setup** - Spawns all token bags in preset positions (5 columns)
- **Place** - Places one copy of each token on the table
- **Recall** - Returns all tokens to their bags

Position grid: 5 columns, spaced 2.5 units apart, starting at relative position (0, 1, 0)

## Script Reference

### Primary Script
- `script/generate_team_tokens.py` - **Master script for complete workflow**

### Individual Scripts
- `script/tools/extract_tokens.py` - Extract from PDF
- `script/tools/add_token_transparency_bg_sample.py` - Background removal
- `script/src/token_tools/generate_tts_tokens.py` - Generate individual token bags
- `script/src/token_tools/generate_team_token_bag.py` - Generate master token bag
- `script/src/token_tools/add_tokens_to_box.py` - Embed token bag in card box
- `script/generate_tts_metadata.py` - Generate metadata
- `script/generate_urls.py` - Generate URL mappings

### Archived Scripts (Dev Folder)
- `dev/extract_token_shapes_from_images.py` - Auto-detect token shapes (used once)

## Configuration Reference

### Team Config Schema

```yaml
teams:
  {team-slug}:
    name: "Team Display Name"
    faction: chaos|imperium|eldar|other
    tokens_ready: true|false
    tokens:
      - name: "Token Display Name"
        shape: round|operative|octagon|diamond
```

### Token Bag URLs

Tokens are published to:
```
https://raw.githubusercontent.com/{user}/kt-datacards/main/output_v2/{faction}/{team}/tts/token/{team}-tokens.json
```

Cache busting: `?v={timestamp_numbers_only}`

## Troubleshooting

### Metadata Script Shows "No LuaScriptState" Warning
**Cause:** The tokenbag file doesn't have a LuaScriptState with timestamp
**Solution:** This is expected for most teams, script falls back to file modification time

### Card Box Has Wrong Tokens
**Cause:** Stale token bag embedded
**Solution:** Re-run `add_tokens_to_box.py` to replace with latest

### Token Assets Not Found in TTS
**Cause:** URLs not generated or incorrect paths
**Solution:** Run `generate_urls.py` and check GitHub file paths match exactly

## Future Improvements

Potential enhancements for the workflow:
1. Integrate token generation into main pipeline
2. Add validation checks at each stage
3. Automatic shape detection during processing
4. Generate token mesh files instead of copying template
5. Batch processing for multiple teams
6. Rollback capability for failed generations
