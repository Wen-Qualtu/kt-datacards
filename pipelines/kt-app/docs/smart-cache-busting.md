# Smart Cache Busting with Timestamps

## Overview
Implemented smart cache busting for both card boxes and token bags using timestamp checking. Instead of always force-updating with random cache-busting parameters, the system now checks if the remote version is newer before updating.

## Changes

### 1. Metadata Files with Timestamps

#### `output_v2/tts-card-boxes.json`
Contains metadata for all card boxes:
```json
[
  {
    "team": "legionaries",
    "name": "Legionaries",
    "url": "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/add-warcom-pdf-processor/tts_objects/Legionaries%20Cards.json",
    "last_modified": "2026-01-23T13:29:42"
  },
  ...
]
```

#### `output_v2/tts-token-bags.json` (NEW)
Contains metadata for all token bags:
```json
[
  {
    "team": "legionaries",
    "name": "Legionaries",
    "url": "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/add-warcom-pdf-processor/tts_objects/tokens/legionaries/legionaries-tokenbag.json",
    "last_modified": "2026-01-23T13:28:26"
  },
  ...
]
```

### 2. Card Box Update Flow

#### Before (Always Update):
1. User clicks "Update" button
2. System immediately updates all cards with cache-busting
3. Downloads and respawns everything regardless of changes

#### After (Smart Update):
1. User clicks "Update" button
2. **System fetches `tts-card-boxes.json`** to check remote timestamp
3. **Compares with stored `lastUpdate` timestamp**
4. **If timestamps match**: Shows "Already up to date!" message
5. **If timestamps differ**: Performs update and saves new timestamp

### 3. Token Bag Update Flow

#### Before (Always Update):
1. After card update completes
2. System immediately downloads token bag with cache-busting
3. Respawns token dispenser bag

#### After (Smart Update):
1. After card update completes (or separately)
2. **System fetches `tts-token-bags.json`** to check remote timestamp
3. **Compares with stored `lastTokenUpdate` timestamp**
4. **If timestamps match**: Shows "Token bags already up to date!" message
5. **If timestamps differ**: Performs update and saves new timestamp

### 4. State Tracking

Card boxes now track TWO separate timestamps in `LuaScriptState`:
```json
{
  "ml": {...},
  "rr": 270,
  "lastUpdate": "2026-01-23T13:29:42",
  "teamSlug": "legionaries",
  "lastTokenUpdate": "2026-01-23T13:28:26"
}
```

- `lastUpdate`: Timestamp of last card deck update
- `lastTokenUpdate`: Timestamp of last token bag update (NEW)

These are tracked separately because:
- Cards and tokens can be updated independently
- Token images might change without card changes (and vice versa)
- Users can see exactly which component needs updating

## Implementation Details

### Lua Script Changes

#### New Functions in Card Boxes:

**`updateTokenBag()`** - Smart token bag update with timestamp checking
- Fetches `tts-token-bags.json`
- Compares timestamps
- Only calls `performTokenUpdate()` if update needed

**`performTokenUpdate(tokenBagGUID, tokenBagURL, fetchTimestamp, newTimestamp)`** - Actual token bag update
- Downloads token bag JSON from GitHub
- Destroys old token dispenser bag
- Spawns new one
- Saves timestamp after success

#### Modified Functions:

**`onload()`** - Now loads `lastTokenUpdate` from saved state

**`updateSave()`** - Now saves `lastTokenUpdate` to saved state

### Python Scripts

#### `script/generate_tts_metadata.py` (NEW)
Generates both metadata files with timestamps:
- `output_v2/tts-card-boxes.json` (35 teams with tokens + 9 without)
- `output_v2/tts-token-bags.json` (35 teams with tokens)

Usage:
```bash
poetry run python script/generate_tts_metadata.py
```

**When to run**:
- After regenerating tokens for any team
- After updating card boxes
- Before committing changes to GitHub

#### `script/update_token_timestamps.py` (NEW)
Updates all card box Lua scripts to use smart timestamp checking:
- Removes old `updateTokenBag()` function
- Adds new version with timestamp checking
- Updates `onload()` and `updateSave()` functions
- Initializes `lastTokenUpdate` in `LuaScriptState`

## Benefits

### 1. Reduced Network Traffic
- Only downloads when actually needed
- Saves bandwidth for both GitHub and users

### 2. Faster Updates
- Timestamp check is much faster than downloading full JSON
- Users see "Already up to date!" immediately

### 3. Better User Experience
- Clear feedback about what's updating and why
- Separate messages for cards vs tokens
- Shows local vs remote timestamps when update available

### 4. Debugging
- Users can see exactly when their local copy was last updated
- Easy to compare with GitHub timestamps
- Separate tracking for cards and tokens helps identify issues

## User Experience (In TTS)

### Scenario 1: Everything Up to Date
```
User clicks "Update"
> "Checking for updates..."
> "Already up to date! (Last: 2026-01-23T13:29:42)"
> "Checking for token bag updates..."
> "Token bags already up to date! (Last: 2026-01-23T13:28:26)"
```

### Scenario 2: Cards Need Update, Tokens Don't
```
User clicks "Update"
> "Checking for updates..."
> "Update available! Local: 2026-01-23T13:29:42 | Remote: 2026-01-24T10:15:30"
> "Updating rules and box texture... Please wait and do NOT click other buttons."
> "Updated 1 of 8 cards..."
> ...
> "Update complete! All 8 cards, box texture, and mesh refreshed. Now updating tokens..."
> "Checking for token bag updates..."
> "Token bags already up to date! (Last: 2026-01-23T13:28:26)"
```

### Scenario 3: Both Need Updates
```
User clicks "Update"
> "Checking for updates..."
> "Update available! Local: 2026-01-23T13:29:42 | Remote: 2026-01-24T10:15:30"
> "Updating rules and box texture... Please wait..."
> ... (card update messages) ...
> "Update complete! All 8 cards refreshed. Now updating tokens..."
> "Checking for token bag updates..."
> "Token bag update available! Local: 2026-01-23T13:28:26 | Remote: 2026-01-24T10:20:15"
> "Updating token bags from GitHub... Please wait."
> "Token bags updated successfully!"
```

### Scenario 4: First Time (No Timestamps)
```
User clicks "Update" (first time ever)
> "No timestamp info. Forcing refresh..."
> "Updating rules and box texture... Please wait..."
> ... (update proceeds) ...
> "No token timestamp info. Forcing refresh..."
> ... (token update proceeds) ...
```
After this, timestamps are saved and future updates will be smart.

## Workflow Integration

### Complete Regeneration Workflow

```bash
# 1. Make changes to token images or card extraction
poetry run python script/main.py extract-tokens --team legionaries

# 2. Generate TTS tokens
poetry run python script/src/token_tools/generate_tts_tokens.py --team legionaries

# 3. Extract token bags
poetry run python script/extract_token_bags.py

# 4. Generate metadata with timestamps
poetry run python script/generate_tts_metadata.py

# 5. Commit to GitHub
git add output_v2/tts-token-bags.json output_v2/tts-card-boxes.json
git add tts_objects/tokens/legionaries/
git commit -m "Update legionaries tokens"
git push

# Users can now click "Update" in TTS and will only download if their local copy is older
```

### Automated Script Idea

Consider creating a helper script:
```bash
# script/update_team.sh
#!/bin/bash
TEAM=$1

# Regenerate everything
poetry run python script/main.py extract-tokens --team $TEAM
poetry run python script/src/token_tools/generate_tts_tokens.py --team $TEAM
poetry run python script/extract_token_bags.py
poetry run python script/generate_tts_metadata.py

# Show what changed
git status

echo "Ready to commit! Review changes above, then:"
echo "  git add ."
echo "  git commit -m 'Update $TEAM'"
echo "  git push"
```

## Technical Notes

### Timestamp Format
Using ISO 8601 format without timezone (local time):
```
2026-01-23T13:29:42
```

This is:
- Human readable
- Sortable as strings
- Easy to generate in Python: `datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M:%S")`

### Cache Busting Still Used
Even with timestamp checking, we still use `?v=random` when actually downloading:
- Ensures intermediate caches (CDN, browser) are bypassed
- Guarantees fresh content when update is needed
- Small overhead only when update is actually required

### Separate Cards and Tokens
They have separate timestamps because:
- Different files updated at different times
- Different generation processes
- Allows partial updates (e.g., just cards)
- Better granularity for debugging

## Files Modified

### New Files:
1. `output_v2/tts-token-bags.json` - Token bag metadata with timestamps
2. `script/generate_tts_metadata.py` - Generate both metadata files
3. `script/update_token_timestamps.py` - Update card boxes with smart checking
4. `docs/smart-cache-busting.md` - This documentation

### Modified Files:
1. `output_v2/tts-card-boxes.json` - Added `last_modified` timestamps
2. `tts_objects/*Cards.json` (35 files) - Updated Lua scripts with timestamp checking

### Scripts No Longer Needed:
- `script/add_token_update_to_cardboxes.py` (superseded by `update_token_timestamps.py`)
- `script/add_timestamp_checking.py` (superseded by `update_token_timestamps.py`)

## Future Enhancements

### Possible Improvements:
1. **Single metadata file**: Combine cards and tokens into one file
2. **Version numbers**: Use semantic versioning instead of timestamps
3. **Change log**: Include what changed in each version
4. **Automatic update**: Button to update all outdated teams at once
5. **Update notification**: Show badge on Update button when updates available
