# TTS Timestamp & Hash System Knowledge

## Overview
The kt-datacards project uses a hash-based timestamp system to track changes to card images and enable smart cache-busting for TTS (Tabletop Simulator) updates.

## Key Concepts

### Timestamp Format
- **Format**: `yyyyMMddHHmm` (e.g., `202602271715`)
- **Converted from**: Previously used Unix timestamps
- **Purpose**: Human-readable, sortable timestamps for URL cache-busting parameters

### Hash-Based Change Detection
- **Algorithm**: MD5 hash (first 8 characters)
- **Purpose**: Detect actual visual changes in image files, not just file modification times
- **Benefit**: Prevents unnecessary timestamp updates when files are regenerated but content is identical (idempotency)

## System Architecture

### Core Files
1. **`.tts-image-hashes.json`** - Persistent cache mapping URLs to `{hash, timestamp}` objects
   - Location: `output_v2/.tts-image-hashes.json`
   - Structure: `{"url": {"hash": "86b9c446", "timestamp": "202602271335"}}`

2. **TTS Box Files** - Generated TTS objects with `lastCardUpdate` in `LuaScriptState`
   - Location: `tts_objects/{team}/{Team Name} Cards.json`
   - Box timestamp = max of all image timestamps for that team

3. **`tts-metadata.json`** - Master metadata file for TTS update checking
   - Location: `output_v2/tts-metadata.json`
   - Used by TTS Lua script to check for updates
   - Structure: `{"team": "...", "cards_last_modified": "202602271715"}`

### Pipeline Flow
```
1. Edit PDF → processed/{team}/{team}-datacards.pdf
2. Extract images → poetry run python script/run_pipeline.py --step extract --teams {team}
   - Generates JPG files in output_v2/{faction}/{team}/datacards/
3. Generate TTS objects → poetry run python script/generate_tts_objects.py {team}
   - Computes MD5 hashes of all images
   - Compares with cached hashes
   - Updates timestamps only for changed images
   - Generates/updates TTS box JSON file
4. Generate metadata → poetry run python script/generate_tts_metadata.py
   - Extracts timestamps from all TTS box files
   - Generates tts-metadata.json for TTS update checking
5. Push to GitHub → git add/commit/push
   - Deploys updated images, TTS boxes, and metadata
```

## Key Implementation Details

### Hash Computation (`_compute_url_hash`)
- Reads local file from workspace based on GitHub URL
- Computes MD5 hash in 8KB chunks
- Handles both `/main/` and `/acc/` branch URLs
- Returns 8-character hex hash

### Timestamp Caching (`_get_cached_timestamp`)
- Computes current hash of file
- Compares with cached hash
- **If hashes match**: Returns cached timestamp (no change)
- **If hashes differ**: Generates new timestamp, logs "Image changed"
- **If no cache entry**: Tries to extract timestamp from existing URL, or generates new one

### Box Timestamp Calculation (`_get_box_timestamp`)
- Collects ALL timestamps from team-specific images during URL application
- Returns max timestamp (string comparison works for yyyyMMddHHmm)
- Ensures box shows as updated if ANY image in the team changed

### Preloading Logic (`_preload_timestamps_from_existing_tts_files`)
- **Purpose**: Preserve timestamps for assets not in datacards-urls.json (icons, token bags)
- **IMPORTANT FIX**: Only runs if hash cache is empty
- **Why**: Previously it computed fresh hashes from current files but paired them with old timestamps from TTS URLs, preventing change detection

## Common Issues & Solutions

### Issue: "PDF changed but no timestamp update detected"
**Cause**: PDF extraction produced pixel-identical images despite source changes
**Debug Steps**:
1. Compare file sizes: `git show HEAD:{file} | Measure-Object -Character` vs current
2. Compute hashes: `python -c "import hashlib; from pathlib import Path; print(hashlib.md5(Path('...').read_bytes()).hexdigest()[:8])"`
3. Check if visual changes are in extracted regions (not cropped metadata areas)

**Solution**: Make actual visual changes to datacard content, re-extract images

### Issue: "TTS shows update on first click, then 'no changes'"
**Cause**: Metadata file has old timestamps while TTS box has new ones
**Solution**: Regenerate metadata to sync with box files:
```powershell
poetry run python script/generate_tts_metadata.py
git add output_v2/tts-metadata.json
git commit -m "Sync metadata timestamps"
git push origin acc
```

### Issue: "Hash cache not detecting changes after regeneration"
**Cause**: Preloading logic was computing fresh hashes from current (changed) files but storing old timestamps
**Fixed**: 2026-02-27 - Preloading now skips if hash cache exists
**Code**: [script/src/generators/tts_generator.py](../script/src/generators/tts_generator.py#L214)

### Issue: "datacards-urls.json changes every time I run pipeline"
**Cause**: Old code removed all TTS box entries and re-added only regenerated ones
**Fixed**: 2026-02-27 - Now updates TTS entries in-place preserving order
**Code**: [script/src/generators/tts_generator.py](../script/src/generators/tts_generator.py#L588)

## Testing Changes

### Manual Testing Workflow
```powershell
# 1. Edit PDF and copy to processed folder
Copy-Item "dev\{team}-datacards.pdf" -Destination "processed\{team}\{team}-datacards.pdf" -Force

# 2. Extract images and generate TTS objects
poetry run python script/run_pipeline.py --step extract --teams {team}
poetry run python script/generate_tts_objects.py {team}

# 3. Check what changed
git status --short
git diff output_v2/.tts-image-hashes.json | Select-String "{card-name}" -Context 2

# 4. Verify timestamps updated
python -c "import json; obj = json.load(open('tts_objects/{team}/{Team} Cards.json')); state = json.loads(obj['ObjectStates'][0]['LuaScriptState']); print(f'lastCardUpdate: {state[\"lastCardUpdate\"]}')"

# 5. Generate metadata and push
poetry run python script/generate_tts_metadata.py
git add -A
git commit -m "Update {team} cards"
git push origin acc
```

### Verifying Hash Changes
```powershell
# Save current hashes before changes
python -c "import hashlib; from pathlib import Path; cards = sorted(Path('output_v2/{faction}/{team}/datacards').glob('*.jpg')); [print(f'{c.name}: {hashlib.md5(c.read_bytes()).hexdigest()[:8]}') for c in cards]"

# Make changes to images...

# Compare after changes - should see different hashes for changed cards
```

## TTS Update Mechanism

### In-Game Update Check
1. User clicks "Update" button on TTS card box
2. Lua script fetches `tts-metadata.json` from GitHub
3. Compares `lastCardUpdate` (local) vs `cards_last_modified` (remote)
4. Downloads new box if remote timestamp is newer
5. Replaces box with updated version

### Timestamp Comparison Logic
```lua
local function toTimestampNumber(ts)
  local num = tostring(ts or ""):gsub("[^%d]", "")
  return tonumber(num) or 0
end

local localStamp = toTimestampNumber(lastCardUpdate)
local remoteStamp = toTimestampNumber(remoteTimestamp)

if localStamp >= remoteStamp then
  -- Already up to date
else
  -- Update available
end
```

## Best Practices

1. **Always extract images before generating TTS objects** - Don't just regenerate TTS from old JPGs
2. **Check hash changes** - Verify hashes actually changed before expecting timestamp updates
3. **Regenerate metadata after TTS objects** - Keeps timestamps in sync
4. **Test with actual visual changes** - PDF metadata changes may not affect extracted images
5. **Commit hash cache** - The `.tts-image-hashes.json` file should be committed to preserve timestamps
6. **Use team filter** - `--teams {team}` to regenerate only what changed

## File Locations Reference

```
kt-datacards/
├── .github/
│   ├── copilot-instructions.md          # Main project knowledge
│   └── tts-timestamp-system.md          # This file
├── config/
│   ├── team-config.yaml                 # Team registry
│   └── team-guids.json                  # TTS GUID mappings
├── processed/{team}/                    # PDFs used by extraction
│   └── {team}-datacards.pdf
├── output_v2/
│   ├── .tts-image-hashes.json          # Hash cache (COMMIT THIS)
│   ├── tts-metadata.json               # Update metadata (COMMIT THIS)
│   └── {faction}/{team}/datacards/     # Extracted card images
├── tts_objects/{team}/
│   └── {Team Name} Cards.json          # Generated TTS bags
└── script/
    └── src/generators/
        ├── tts_generator.py            # Main TTS generation logic
        └── ...
```

## Recent Fixes (2026-02-27)

1. **Preloading Bug**: Fixed preloading computing fresh hashes but storing old timestamps
2. **In-Place Updates**: datacards-urls.json now updates entries in-place instead of removing all and re-adding
3. **Hash Change Detection**: Added logging when images change: "Image changed: ...jpg... (updating timestamp)"

## Troubleshooting Commands

```powershell
# Check if file exists and get hash
Test-Path "output_v2/{path}"; python -c "import hashlib; from pathlib import Path; print(hashlib.md5(Path('output_v2/{path}').read_bytes()).hexdigest()[:8])"

# View cached hash for URL
python -c "import json; cache = json.load(open('output_v2/.tts-image-hashes.json')); print(cache.get('https://...', 'not found'))"

# Extract timestamp from TTS box
Select-String -Path "tts_objects/{team}/*.json" -Pattern "lastCardUpdate" | Select-Object -First 1

# Check metadata timestamp
python -c "import json; meta = json.load(open('output_v2/tts-metadata.json')); gp = [t for t in meta if t['team'] == '{team}']; print(gp[0] if gp else 'not found')"

# Compare file hashes between two versions
git show HEAD:output_v2/{path} | python -c "import hashlib, sys; print(hashlib.md5(sys.stdin.buffer.read()).hexdigest()[:8])"
```
