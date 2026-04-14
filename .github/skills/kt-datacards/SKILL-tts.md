---
description: kt-datacards TTS integration — TTS save JSON structure, card nickname format, Lua scripts, hash-based image change detection, timestamp cache-busting, deployment workflow, and TTS update mechanism. Load when generating TTS objects, debugging updates, or working on Lua scripts.
tags: [kill-team, tabletop-simulator, tts, lua, hash, timestamps, deployment, cache-busting]
---

# kt-datacards — TTS Objects & Timestamp System

## When to Use This Skill

Load when working on:
- TTS save JSON generation
- Lua script integration
- Image hash / timestamp change detection
- TTS update mechanism debugging
- Deploying card updates to GitHub

Also load **SKILL-project.md** for directory structure and naming conventions.

---

## TTS Save JSON Structure

### Top-Level Layout
```json
{
  "ObjectStates": [
    {
      "Name": "Bag",
      "Nickname": "Angels of Death Cards",
      "ContainedObjects": [
        {
          "Name": "Deck",
          "Nickname": "[FF5500]E[-] {8/8} Stalker Alpha",
          "GMNotes": "{...json stats...}",
          "LuaScript": "...datacard script...",
          "LuaScriptState": "{...json state...}",
          "CustomDeck": { ... },
          "DeckIDs": [100]
        }
      ]
    }
  ]
}
```

- Container: `Bag` (CardBox)
- Contents: `Deck` objects (or `Card` for single cards)
- Each card: `Nickname`, `GMNotes` (JSON stats), `LuaScript`, `LuaScriptState`

### Card Nickname Format
```
[FF5500]E[-] {8/8} Stalker Alpha
│       │ │  │     └─ Operative name
│       │ │  └─ Wound display: current/max (same on creation)
│       │ └─ Order state (- = uncommitted)
│       └─ Order type (E = Engage, C = Conceal)
└─ TTS color code
```
When matching card names back to operatives, strip the entire prefix up to and including `} `.

### GMNotes — Stats JSON
```json
{
  "stats": {
    "M": "6\"",
    "APL": "2",
    "GA": "1",
    "DF": "3",
    "SV": "3+",
    "W": "8"
  }
}
```

### LuaScriptState — Full State
```json
{
  "stats": {"M": "6\"", "APL": "2", "GA": "1", "DF": "3", "SV": "3+", "W": "8"},
  "info": {
    "weapons": [...],
    "abilities": [...],
    "actions": [...],
    "categories": ["IMPERIUM", "PHOBOS"],
    "rules": [...]
  },
  "wounds": {"current": 8, "max": 8},
  "lastCardUpdate": "202602271715"
}
```

---

## Lua Scripts

### Location
`config/defaults/tts-script/datacard-load-stats.lua`

### Key Functions
```lua
function onLoad(script_state)
    -- Deserialize JSON state into local vars
    -- state.stats, state.info, state.wounds, lastCardUpdate
end

function diffAndApply(card_stats, model_stats)
    -- Per-field comparison between card data and model
    -- Returns array of change description strings
    -- Used by "Load stats to model" context menu
end

function findModelOnCard()
    -- Uses Physics.cast to locate a model object on the card
    -- Returns first non-card object found at card position
end
```

### TTS Update Check (in-game)
```lua
local function toTimestampNumber(ts)
    local num = tostring(ts or ""):gsub("[^%d]", "")
    return tonumber(num) or 0
end

local localStamp  = toTimestampNumber(lastCardUpdate)
local remoteStamp = toTimestampNumber(remoteTimestamp)

if localStamp >= remoteStamp then
    -- Already up to date
else
    -- Update available — download new box
end
```

---

## Hash & Timestamp System

### Purpose
Detect actual visual changes in card images to enable smart cache-busting. Prevents spurious timestamp updates when files are regenerated but content is pixel-identical.

### Timestamp Format
- Format: `yyyyMMddHHmm` (e.g., `202602271715`)
- String comparison works for ordering because format is zero-padded and sortable
- Used as URL cache-busting parameter and as TTS update sentinel

### Core Files

| File | Location | Purpose |
|------|----------|---------|
| `.tts-image-hashes.json` | `output_v2/.tts-image-hashes.json` | Hash cache: URL → `{hash, timestamp}` |
| TTS box JSON | `tts_objects/{team}/{Team Name} Cards.json` | Contains `lastCardUpdate` in `LuaScriptState` |
| `tts-metadata.json` | `output_v2/tts-metadata.json` | Remote metadata checked by TTS update button |

### Hash Cache Format
```json
{
  "https://raw.githubusercontent.com/.../output_v2/imperium/angels-of-death/datacards/card-01.jpg": {
    "hash": "86b9c446",
    "timestamp": "202602271335"
  }
}
```
- Hash: MD5 of file bytes, first 8 hex chars
- Commit this file — it's the source of truth for timestamps

### How Change Detection Works (`_get_cached_timestamp`)

```
1. Compute current MD5 hash of local file
2. Look up URL in cache
   a. If cache miss → generate new timestamp, store hash+timestamp
   b. If hash matches cache → return cached timestamp (no change)
   c. If hash differs → generate new timestamp, update cache entry, log "Image changed"
```

### Box Timestamp (`_get_box_timestamp`)
The box timestamp = `max()` of all image timestamps for the team. If ANY card image changes, the box shows as updated.

### Preload Logic — IMPORTANT FIX
`_preload_timestamps_from_existing_tts_files` only runs when the hash cache is **empty**.

**Why**: Previously it computed fresh hashes from current files but stored old box timestamps, which broke change detection. Fixed: 2026-02-27.  
Code: `script/src/generators/tts_generator.py` ~L214.

### tts-metadata.json Format
```json
{
  "teams": {
    "angels-of-death": {
      "team": "Angels of Death",
      "cards_last_modified": "202602271715"
    }
  }
}
```

---

## Key Scripts

| Script | Purpose |
|--------|---------|
| `script/generate_tts_objects.py` | Generate TTS box JSON for one or all teams |
| `script/generate_tts_metadata.py` | Generate `tts-metadata.json` from box files |
| `script/src/generators/tts_generator.py` | Core TTSGenerator class |
| `script/src/generators/tts_boxes_json_generator.py` | Box JSON helpers |

---

## Standard Deployment Workflow

```powershell
# 1. Edit PDF and copy to processed folder
Copy-Item "dev\{team}-datacards.pdf" -Destination "processed\{team}\{team}-datacards.pdf" -Force

# 2. Extract images (regenerates JPGs in output_v2/)
poetry run python script/run_pipeline.py --step extract --teams {team}

# 3. Generate TTS objects (computes hashes, updates timestamps)
poetry run python script/generate_tts_objects.py {team}

# 4. Verify timestamps changed
python -c "
import json
obj = json.load(open('tts_objects/{team}/{Team} Cards.json'))
state = json.loads(obj['ObjectStates'][0]['LuaScriptState'])
print(f'lastCardUpdate: {state[\"lastCardUpdate\"]}')
"

# 5. Regenerate tts-metadata.json
poetry run python script/generate_tts_metadata.py

# 6. Stage, commit, push
git add output_v2/ tts_objects/ -A
git commit -m "Update {team} cards"
git push origin acc
```

### Verifying Hash Changes
```powershell
# Check hashes before/after making changes
python -c "
import hashlib
from pathlib import Path
cards = sorted(Path('output_v2/{faction}/{team}/datacards').glob('*.jpg'))
for c in cards:
    print(f'{c.name}: {hashlib.md5(c.read_bytes()).hexdigest()[:8]}')
"

# Check what changed in hash cache
git diff output_v2/.tts-image-hashes.json | Select-String "{card-name}" -Context 2
```

---

## Common TTS Issues

### "PDF changed but no timestamp update"
**Cause**: PDF extraction produced pixel-identical images despite source change.  
**Debug**: Compare file sizes and hashes before/after. Check if the visual change is in an extracted region (not cropped metadata areas).  
**Solution**: The change must be visible in the rendered card image, not just in PDF metadata.

### "TTS shows update on first click, then 'no changes'"
**Cause**: `tts-metadata.json` has old timestamps while box files have new ones.  
**Solution**:
```powershell
poetry run python script/generate_tts_metadata.py
git add output_v2/tts-metadata.json
git commit -m "Sync metadata timestamps"
git push origin acc
```

### "Hash cache not detecting changes after regeneration"
**Cause**: Old preload logic — was computing fresh hashes and pairing with old timestamps.  
**Status**: Fixed 2026-02-27. Preloading skips if hash cache already exists.

### "datacards-urls.json changes every time"
**Cause**: Old code rebuilt entire TTS entries list on each run.  
**Status**: Fixed 2026-02-27. Now updates in-place, preserving order.

---

## Best Practices

1. **Extract images before generating TTS objects** — don't regenerate TTS from stale JPGs
2. **Always regenerate `tts-metadata.json` after TTS objects** — keeps timestamps in sync
3. **Commit `.tts-image-hashes.json`** — it's the timestamp source of truth
4. **Use `--teams` filter** to only regenerate what changed, not all 46+ teams
5. **Test with actual visual changes** — PDF metadata changes don't affect extracted images
6. **Never push without verifying** `lastCardUpdate` changed in the box JSON
