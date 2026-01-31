# Token Bag Update Implementation

## Overview
Added functionality to update token bags dynamically when the card box's "Update" button is clicked. This solves the TTS image caching issue where token images wouldn't update even after regeneration.

## Implementation Details

### 1. Token Bag Extraction
Created `script/extract_token_bags.py` which:
- Scans all card box JSON files in `tts_objects/`
- Extracts the token dispenser bag (the bag containing all token bags for a team)
- Saves each as a separate JSON file: `tts_objects/tokens/{team}/{team}-tokenbag.json`

**Results:**
- Extracted token bags for 35 teams (9 teams don't have tokens)
- Each token bag JSON contains the token dispenser bag with all individual token bags inside

### 2. Card Box Update Enhancement
Created `script/add_token_update_to_cardboxes.py` which:
- Adds a new Lua function `updateTokenBag()` to each card box
- Modifies the existing `performUpdate()` function to call `updateTokenBag()` after card updates complete
- The token bag update process:
  1. Finds the token dispenser bag in the card box (by nickname ending in " tokens")
  2. Fetches the token bag JSON from GitHub with cache-busting: `?v=random_number`
  3. Takes out the old token bag
  4. Destroys it and spawns the new one from the fetched JSON
  5. Puts the new token bag back in the card box

**Results:**
- Updated 35 card boxes to include token bag update functionality
- The existing "Update" button now updates both cards and tokens

## Files Modified

### New Files Created:
1. `tts_objects/tokens/{team}/{team}-tokenbag.json` (35 teams)
   - Legionaries, Blooded, Kommandos, etc.
   - Contains the complete token dispenser bag with all token bags inside

2. `script/extract_token_bags.py`
   - Utility to extract token bags from card boxes

3. `script/add_token_update_to_cardboxes.py`
   - Utility to add token update functionality to card boxes

### Modified Files:
- `tts_objects/*Cards.json` (35 files)
  - Added `updateTokenBag()` Lua function
  - Modified `performUpdate()` to call `updateTokenBag()` after card updates

## Usage

### For Users (In TTS):
1. Right-click on a card box and click "Recall" to bring all cards/tokens back into the box
2. Click the "Update" button on the side of the card box
3. The system will:
   - Update all card images with cache-busting
   - Update the box texture and mesh
   - Fetch and respawn the token dispenser bag from GitHub
   - Display progress messages in the chat

### For Developers:
1. Make changes to token images in `output_v2/{faction}/{team}/tts/token/`
2. Run token generation: `poetry run python script/src/token_tools/generate_tts_tokens.py --team {team}`
3. Extract token bags: `poetry run python script/extract_token_bags.py`
4. Commit and push to GitHub
5. Users can click "Update" in TTS to get the new tokens

## Technical Details

### Token Bag Structure:
```json
{
  "ObjectStates": [{
    "Name": "Custom_Model_Bag",
    "Nickname": "Legionaries tokens",
    "ContainedObjects": [
      {
        "Name": "Custom_Model_Infinite_Bag",
        "Nickname": "Mark of Chaos Khorne",
        "ContainedObjects": [
          {
            "Name": "Custom_Token",
            "CustomImage": {
              "ImageURL": "https://...legionaries-mark-of-chaos-khorne.png"
            }
          }
        ]
      },
      // ... more token bags
    ]
  }]
}
```

### GitHub URL Pattern:
```
https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/fix/correct-celestians/tts_objects/tokens/{team}/{team}-tokenbag.json?v={random}
```

The `?v={random}` parameter forces TTS to bypass its cache and fetch the latest version.

## Benefits

1. **Dynamic Updates**: Token bags can be updated without manually editing card box JSON files
2. **Cache Busting**: Random parameter ensures TTS always fetches the latest version
3. **User Friendly**: Single button click updates everything
4. **Maintainable**: Token bags are separate files, easier to regenerate
5. **Consistent**: Same update mechanism as cards (WebRequest + spawnObjectData)

## Workflow Integration

### Current Token Generation Workflow:
1. Extract tokens from PDFs: `poetry run python script/main.py extract-tokens --team {team}`
2. Generate TTS tokens: `poetry run python script/src/token_tools/generate_tts_tokens.py --team {team}`
3. Extract token bags: `poetry run python script/extract_token_bags.py` (NEW)
4. Commit and push to GitHub

### To Update All Teams:
```bash
# Extract and generate all teams
for team in $(ls processed); do
  poetry run python script/src/token_tools/generate_tts_tokens.py --team $team
done

# Extract all token bags
poetry run python script/extract_token_bags.py

# Update card boxes (only needed once)
poetry run python script/add_token_update_to_cardboxes.py
```

## Teams Without Token Bags

The following 9 teams don't have token bags (no tokens in their rules):
- Angels Of Death
- Chaos Cult
- Elucidian Starstriders
- Gellerpox Infected
- Hunter Clade
- Plague Marines
- Void Dancer Troupe
- Warpcoven
- Wyrmblade

These teams were skipped during processing as they don't need token update functionality.
