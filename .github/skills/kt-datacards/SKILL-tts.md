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

### Core Files (per team)

| File | Location | Purpose |
|------|----------|---------|
| Bag / box JSON | `output/{team}/tts_objects/{Team Name}.json` | Contains `lastCardUpdate` in `LuaScriptState` |
| Object URLs | `output/{team}/{team}-object-urls.json` | Per-entry `{url, hash, modified}` for the box + each object |
| Pipeline state | `layers/integration/{team}/{team}-pipeline-state.json` | Step completion + output hashes (change detection) |

All asset URLs point at the `main` branch:
`https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/{team}/...`

### Object URLs Format
```json
{
  "box": {
    "url": "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/angels-of-death/tts_objects/Angels Of Death.json",
    "hash": "86b9c446",
    "modified": "202602271335"
  },
  "objects": [
    {
      "type": "card",
      "name": "stalker-alpha",
      "url": "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/angels-of-death/cards/datacards/stalker-alpha-front.jpg",
      "hash": "1a2b3c4d",
      "modified": "202602271335"
    }
  ]
}
```
- Hash: MD5 of file bytes, first 8 hex chars
- Commit this file — the `hash`/`modified` pair is the source of truth for change detection
- Every entry MUST carry a `hash` field (validated by the pre-merge check suite)

### How Change Detection Works
```
For each asset:
1. Compute current MD5 hash of local file
2. Compare against the committed `hash` in {team}-object-urls.json
   a. If hash matches → keep the existing `modified` timestamp (no change)
   b. If hash differs (or missing) → bump `modified` to now, update `hash`
```

### Box Timestamp Alignment
The bag's `LuaScriptState.lastCardUpdate` MUST be `>=` the max `modified` across that
team's `{team}-object-urls.json` entries. If ANY asset changes, `lastCardUpdate` bumps so
TTS clients see the update. The pre-merge check `check_timestamp_alignment.py` enforces
this (see **SKILL-pre-merge.md**). A surgical realignment recipe lives in
`/memories/repo/kt-app-step7-timestamp-alignment.md`.

---

## Key Code

| Location | Purpose |
|--------|---------|
| `generate_tts` step (`pipeline/steps/`) | Generates the box JSON + `{team}-object-urls.json`, embeds GMNotes/LuaScript, aligns timestamps |
| `pipeline/steps/` (tts implementation + templates) | Box/deck/card assembly and TTS templates |
| `pipeline/utils/paths.py` | Resolves `output/{team}/tts_objects/...` and object-urls paths |

Run it with `python -m pipeline.main --step generate_tts --teams {team}` (or `--source
warcom`). URL base/branch override via `KT_DATACARDS_URL_BASE` / `KT_DATACARDS_URL_BRANCH`
(default branch `main`).

---

## Standard Deployment Workflow

```powershell
# Run from the repo root with PYTHONPATH = repo root

# 1. Import the updated source PDF (kt-app: into input/; warcom: into layers/warcom/staging/)
Copy-Item "dev\{team}-datacards.pdf" -Destination "input\{team}-datacards.pdf" -Force

# 2. Regenerate the team end-to-end (regenerates cards under output/{team}/cards/)
python -m pipeline.main --source kt-app --teams {team} --force

# 3. (Or just regenerate the TTS objects if only stats/box changed)
python -m pipeline.main --step generate_tts --teams {team}

# 4. Verify the box timestamp changed
python -c "
import json
obj = json.load(open('output/{team}/tts_objects/{Team}.json'))
state = json.loads(obj['ObjectStates'][0]['LuaScriptState'])
print(f'lastCardUpdate: {state[\"lastCardUpdate\"]}')
"

# 5. Run the pre-merge check suite before committing
python .github/skills/kt-datacards/tools/check_all.py

# 6. Stage, commit, push
git add output/ layers/integration/ -A
git commit -m "Update {team} cards"
git push
```

### Verifying Hash Changes
```powershell
# Check hashes before/after making changes
python -c "
import hashlib
from pathlib import Path
cards = sorted(Path('output/{team}/cards/datacards').glob('*.jpg'))
for c in cards:
    print(f'{c.name}: {hashlib.md5(c.read_bytes()).hexdigest()[:8]}')
"

# Check what changed in the object-urls hashes
git diff output/{team}/{team}-object-urls.json | Select-String "{card-name}" -Context 2
```

---

## Common TTS Issues

### "PDF changed but no timestamp update"
**Cause**: PDF extraction produced pixel-identical images despite source change.  
**Debug**: Compare file sizes and hashes before/after. Check if the visual change is in an extracted region (not cropped metadata areas).  
**Solution**: The change must be visible in the rendered card image, not just in PDF metadata.

### "TTS shows update on first click, then 'no changes'"
**Cause**: The box's `lastCardUpdate` is out of sync with the max `modified` in
`{team}-object-urls.json`.  
**Solution**: Re-run the `generate_tts` step for the team, or apply the surgical
realignment in `/memories/repo/kt-app-step7-timestamp-alignment.md`, then re-run the
pre-merge checks:
```powershell
python -m pipeline.main --step generate_tts --teams {team}
python .github/skills/kt-datacards/tools/check_all.py
git add output/{team} -A
git commit -m "Sync {team} timestamps"
git push
```

### "Change detection not firing after regeneration"
**Cause**: An entry in `{team}-object-urls.json` is missing its `hash` field, so change
detection can't compare against a baseline.  
**Solution**: Re-run the `generate_tts` step for the team to repopulate `hash` on every
entry (validated by `check_hash_baseline.py`).

### "Object URLs churn every run"
**Cause**: Content is genuinely unchanged but timestamps/URLs are being rewritten.  
**Debug**: Confirm the per-entry `hash` matches the on-disk file; unchanged hashes should
preserve the existing `modified` timestamp and URL.

---

## Best Practices

1. **Regenerate assets before the TTS objects** — don't build TTS from stale card images
2. **Run the pre-merge check suite before committing** — `check_all.py` gates timestamp
   alignment, hash baselines, and `main`-branch URLs
3. **Commit `{team}-object-urls.json`** — the `hash`/`modified` pairs are the change-detection source of truth
4. **Use `--teams` filter** to only regenerate what changed, not all 46+ teams
5. **Test with actual visual changes** — PDF metadata changes don't affect extracted images
6. **Never push without verifying** `lastCardUpdate` changed in the box JSON

