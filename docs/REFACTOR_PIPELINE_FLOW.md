# KT-App Refactor Pipeline — Complete Flow Diagram

**Branch**: `refactor-kt-app-pipeline`  
**Location**: `pipelines/kt-app/steps/`  
**Date**: May 11, 2026

---

## Pipeline Overview

**7-Step Modular Pipeline**

```
INPUT: input/*.pdf (raw PDFs with UUID filenames)
OUTPUT: output_v3/{team}/ (complete team assets)
INTERMEDIATE: layers/kt-app/ (processing state)
```

---

## Step-by-Step Flow

### **STEP 1: Process PDFs**
**Script**: `1_process_pdfs.py`

**Actions**:
1. Scan `input/` for PDF files
2. Identify team and card type from PDF content analysis
   - Read first page text
   - Match against team aliases in `config/team-config.yaml`
   - Detect card type (datacards, equipment, ploys, faction-rules, etc.)
3. Copy and rename PDF to `layers/kt-app/processed/{team}/`
   - Format: `{team}-{card-type}.pdf`
4. Split PDF into single-page PDFs
   - Extract each page individually
   - Save to `layers/kt-app/extracted/{team}/cards/{card-type}/`
   - Format: `{team}-{card-type}-page_{N}.pdf`

**Input**:
```
input/
  ├── 4e539e3e-b2d3-4b65-9d77-343446f41e5f.pdf  # Unknown team/type
  ├── b1d88360-c0bd-4516-9766-08d665c94338.pdf
  └── d59ee429-093c-41f7-bcef-31d2ca0c6e3e.pdf
```

**Output**:
```
layers/kt-app/
  ├── processed/{team}/
  │   ├── {team}-datacards.pdf
  │   ├── {team}-equipment.pdf
  │   ├── {team}-faction-rules.pdf
  │   ├── {team}-firefight-ploys.pdf
  │   ├── {team}-strategy-ploys.pdf
  │   └── {team}-operatives-selection.pdf
  │
  └── extracted/{team}/cards/
      ├── datacards/
      │   ├── {team}-datacards-page_0.pdf
      │   ├── {team}-datacards-page_1.pdf
      │   └── ...
      ├── equipment/
      │   ├── {team}-equipment-page_0.pdf
      │   └── ...
      ├── faction-rules/
      ├── firefight-ploys/
      ├── strategy-ploys/
      └── operatives-selection/
```

**Potential Issues**:
- ⚠️ Team identification fails if content doesn't match aliases
- ⚠️ Card type detection relies on keywords (e.g., "FACTION EQUIPMENT")
- ⚠️ Multiple teams in same PDF not supported
- ⚠️ Very large PDFs may cause memory issues

---

### **STEP 2: Classify Structure**
**Script**: `2_classify_structure.py`

**Actions**:
1. Load single-page PDFs from `layers/kt-app/extracted/{team}/`
2. Classify each page as front or back
   - Front: Contains weapon header ("NAME", "HIT", "WR")
   - Back: No weapon header
3. Extract names from pages
   - Datacards: Extract operative name (top-left corner)
   - Other cards: Extract card name (after card type label)
   - **SPECIAL**: Multi-card faction rules → append card number to name
4. Pair fronts with backs
   - Check "CONTINUE ON BACK" indicator
   - **SPECIAL**: Don't pair if both have "(CARD X/Y)" pattern
5. Group cards by entity
   - Same operative → multiple cards
   - Token guide detection (separate from faction rules)
6. Extract token metadata (if token guide exists)
   - Use TokenExtractor for text labels
   - Store token names with positions
7. Build structure.json mapping

**Input**:
```
layers/kt-app/extracted/{team}/cards/
  ├── datacards/
  │   ├── page_0.pdf, page_1.pdf, page_2.pdf, ...
  ├── equipment/
  ├── faction-rules/
  │   ├── page_0.pdf  # ELITE FIELDCRAFT (CARD 1/3) front
  │   ├── page_1.pdf  # ELITE FIELDCRAFT (CARD 1/3) back
  │   ├── page_2.pdf  # ELITE FIELDCRAFT (CARD 2/3) front
  │   ├── page_3.pdf  # ELITE FIELDCRAFT (CARD 3/3) front
  │   ├── page_4.pdf  # CAMO CLOAKS front
  │   └── page_5.pdf  # MARKER/TOKEN GUIDE
  └── ...
```

**Output**:
```
layers/kt-app/classified/{team}/
  └── structure.json

{
  "team": "spectre-squad",
  "datacards": [
    {
      "datacard_number": 1,
      "name": "SPECTRE VETERAN SERGEANT",
      "cards": [
        {
          "card_number": 1,
          "type": "front",
          "front": "layers/kt-app/extracted/.../page_0.pdf"
        }
      ]
    },
    {
      "datacard_number": 2,
      "name": "SPECTRE FIELD MEDICAE",
      "cards": [
        {
          "card_number": 1,
          "type": "both",
          "front": "layers/kt-app/extracted/.../page_1.pdf",
          "back": "layers/kt-app/extracted/.../page_2.pdf"
        }
      ]
    }
  ],
  "equipment": [...],
  "faction_rules": [
    {
      "faction_rule_number": 1,
      "name": "elite-fieldcraft-card-1",  # ← Card number appended
      "cards": [
        {
          "card_number": 1,
          "type": "both",
          "front": ".../page_0.pdf",
          "back": ".../page_1.pdf"
        }
      ]
    },
    {
      "faction_rule_number": 2,
      "name": "elite-fieldcraft-card-2",  # ← Separate card
      "cards": [
        {
          "card_number": 1,
          "type": "front",
          "front": ".../page_2.pdf"
        }
      ]
    },
    {
      "faction_rule_number": 3,
      "name": "elite-fieldcraft-card-3",  # ← Separate card
      "cards": [...]
    },
    {
      "faction_rule_number": 4,
      "name": "CAMO CLOAKS",
      "cards": [...]
    }
  ],
  "token_guide": [
    {
      "token_guide_number": 1,
      "name": "TOKEN GUIDE SPECTRE SQUAD",
      "cards": [...],
      "tokens": {
        "names": [
          {"card_number": 1, "name": "Advanced Camouflage", "type": "token"},
          {"card_number": 1, "name": "Medic", "type": "token"},
          ...
        ]
      }
    }
  ]
}
```

**Potential Issues**:
- ⚠️ Front page detection relies on header keywords
- ⚠️ Name extraction may fail with unusual text layout
- ⚠️ Multi-card pattern `\(CARD \d+/\d+\)` must match exactly
- ⚠️ Token guide must be detected before token extraction
- ⚠️ Pairing logic assumes sequential pages (front then back)

---

### **STEP 3: Extract Team Data**
**Script**: `3_extract_team_data.py`

**Actions**:
1. Load structure.json for team
2. Extract text data from each card
   - Use PyMuPDF to get full text content
   - Extract from single-page PDFs (already split)
3. Structure text data by card type
4. Save to team-data.json

**Input**:
```
layers/kt-app/classified/{team}/structure.json
layers/kt-app/extracted/{team}/cards/  # For text extraction
```

**Output**:
```
output_v3/{team}/data/
  └── {team}-team-data.json

{
  "team": "spectre-squad",
  "datacards": [
    {
      "name": "SPECTRE VETERAN SERGEANT",
      "text": "Full extracted text from card..."
    }
  ],
  "equipment": [...],
  "faction_rules": [...],
  ...
}
```

**Potential Issues**:
- ⚠️ Text extraction order may not be logical (PDF text blocks)
- ⚠️ No statline parsing at this step (done in step 7 during TTS generation)
- ⚠️ Large text blocks may hit memory limits

---

### **STEP 4: Extract Card Images**
**Script**: `4_extract_card_images.py`

**Actions**:
1. Load structure.json for team
2. For each card entity:
   - For each card (front/back):
     - Render single-page PDF to PNG at 300 DPI
     - Save with normalized filename
3. Add default backside for front-only cards
   - Use `config/defaults/card-backside/default-backside-portrait.jpg`
4. Normalize filenames
   - Pattern: `{team}-{name}-front.png`, `{team}-{name}-back.png`
   - Multi-card: `{team}-{name}-card-{N}-front.png`

**Input**:
```
layers/kt-app/classified/{team}/structure.json
layers/kt-app/extracted/{team}/cards/  # Single-page PDFs
config/defaults/card-backside/
  ├── default-backside-portrait.jpg
  └── default-backside-landscape.jpg
```

**Output**:
```
output_v3/{team}/cards/
  ├── datacards/
  │   ├── {team}-spectre-veteran-sergeant-front.png
  │   ├── {team}-spectre-veteran-sergeant-back.png  # Default
  │   ├── {team}-spectre-field-medicae-front.png
  │   ├── {team}-spectre-field-medicae-back.png     # From PDF
  │   └── ...
  │
  ├── equipment/
  │   ├── {team}-sniper-overwatch-front.png
  │   ├── {team}-sniper-overwatch-back.png
  │   └── ...
  │
  ├── faction_rules/
  │   ├── {team}-elite-fieldcraft-card-1-front.png
  │   ├── {team}-elite-fieldcraft-card-1-back.png   # From PDF
  │   ├── {team}-elite-fieldcraft-card-2-front.png
  │   ├── {team}-elite-fieldcraft-card-2-back.png   # Default
  │   ├── {team}-elite-fieldcraft-card-3-front.png
  │   ├── {team}-elite-fieldcraft-card-3-back.png   # Default
  │   ├── {team}-camo-cloaks-front.png
  │   └── {team}-camo-cloaks-back.png               # Default
  │
  ├── firefight_ploys/
  ├── strategy_ploys/
  ├── operatives_selection/
  └── token_guide/
```

**Potential Issues**:
- ⚠️ 300 DPI renders are memory intensive
- ⚠️ Default backside may not match card orientation
- ⚠️ Filename collisions if names aren't unique
- ⚠️ PNG compression may be slow for many cards

---

### **STEP 5: Extract Tokens**
**Script**: `5_extract_tokens.py`

**Actions**:
1. **Phase 1: Extract rough tokens**
   - Read faction-rules PDF (contains token guide page)
   - Render at 150 DPI for contour detection
   - Use OpenCV for contour detection:
     - Convert to grayscale
     - Threshold (Otsu's method)
     - Morphological operations (close, open)
     - Find external contours
     - Filter by area (min 3000 pixels at 150 DPI)
   - Skip header region (top 15% of card)
   - Extract text labels from PDF (word-level)
   - Match contours with text labels
   - Save rough tokens to intermediate directory

2. **Phase 2: Apply transparency and shape cutting**
   - Load rough token images
   - Remove background:
     - HSV color detection: `v > 235` and `s < 25`
     - Remove small noise (< 100 pixels)
     - Fill holes in contours
   - Crop to content bounds
   - Load shape template (operative/round/diamond)
   - Fit template to content (5% incut)
   - Apply template as alpha mask
   - **SAFETY**: Force pixels outside template to white
   - Fill transparent areas inside template with white
   - Resize to standard size:
     - Operative: 439×414
     - Round/Diamond: 235×235

**Input**:
```
layers/kt-app/extracted/{team}/cards/faction-rules/
  └── {team}-faction-rules-page_5.pdf  # Token guide

config/team-config.yaml  # Token definitions
layers/  # Shape templates (operative, round, diamond)
```

**Output**:
```
layers/kt-app/extracted/_tuning/{team}/
  ├── advanced-camouflage.png        # Rough extraction
  ├── medic.png
  ├── patience.png
  └── extraction-metadata.json       # Metadata

output_v3/{team}/tokens/
  ├── {team}-advanced-camouflage.png  # Final with transparency
  ├── {team}-medic.png
  ├── {team}-patience.png             # No stray pixels!
  └── ...
```

**Potential Issues**:
- ⚠️ Contour detection sensitive to PDF rendering quality
- ⚠️ Text label matching may fail with OCR errors
- ⚠️ Background removal threshold may remove white content
  - **FIXED**: Lowered to 235, increased saturation to 25
  - **FIXED**: Hard template boundary enforcement
- ⚠️ Shape detection (operative vs round) may be incorrect
- ⚠️ Token guide must be page 5+ (skip header assumption)
- ⚠️ Multiple token guides in same PDF may cause issues

---

### **STEP 6: Generate TTS Assets**
**Script**: `6_generate_tts_assets.py`

**Actions**:
1. Copy cardbox assets from `output_v2/{faction}/{team}/tts/`
   - card-box.obj
   - card-box-texture.jpg
   - icon.png
2. Copy token bag mesh
3. Copy token meshes (.obj) and textures (.png)
   - Match token names from structure.json
   - Copy from `output_v2/{faction}/{team}/tts/token/`

**Input**:
```
output_v2/{faction}/{team}/tts/
  ├── card-box.obj
  ├── card-box-texture.jpg
  ├── icon.png
  ├── token-bag.obj
  └── token/
      ├── {token-name}.obj
      └── {token-name}.png

output_v3/{team}/tokens/  # New token textures
```

**Output**:
```
output_v3/{team}/cardbox/
  ├── card-box.obj
  ├── card-box-texture.jpg
  └── icon.png

output_v3/{team}/tokens/
  ├── {team}-advanced-camouflage.png  # Already exists from step 5
  ├── {team}-advanced-camouflage.obj  # Copied
  ├── {team}-medic.png
  ├── {team}-medic.obj
  ├── token-bag.obj
  └── ...
```

**Potential Issues**:
- ⚠️ Relies on output_v2 having correct assets
- ⚠️ Token name matching between v2 and v3 may fail
- ⚠️ Missing tokens in v2 will not be copied
- ⚠️ No validation that .obj matches .png texture

---

### **STEP 7: Generate TTS Objects (with embedded stats)**
**Script**: `7_generate_tts_objects.py`

**Actions**:
1. Load team configuration from `config/team-config.yaml`
2. Load team GUIDs from `config/team-guids.json`
3. Scan card images from `output_v3/{team}/cards/`
4. Build card deck objects:
   - Group by type (datacards, equipment, ploys, faction rules)
   - Generate CustomDeck entries with GitHub raw URLs
   - Create Deck or Card objects
   - Set positions relative to cardbox
5. Build token bag object:
   - Load tokens from `output_v3/{team}/tokens/`
   - Create CustomModelBag with ContainedObjects
   - Position relative to cardbox
6. Generate memoryList (for TTS asset loading)
7. **Embed operative stats** (from step 3's team-data.json):
   - Match datacards to operatives
   - Build GMNotes JSON with stats, weapons, abilities, actions
   - Add LuaScript for "Load stats to model" functionality
   - Add faction rule UI (if applicable)
   - Update lastCardUpdate timestamp
8. Save TTS JSON to `output_v3/{team}/tts_objects/`
   - Individual card JSONs: `output_v3/{team}/tts_objects/cards/{card_type}/card-*.json`
   - Individual token JSONs: `output_v3/{team}/tts_objects/tokens/token-*.json`
   - Assembled box: `output_v3/{team}/tts_objects/{Team Name} Box.json`
9. Update `output_v3/team-urls.json` for all teams

**Input**:
```
config/team-config.yaml
config/team-guids.json
config/weapon_rules.json
config/defaults/tts-script/datacard-load-stats.lua
output_v3/{team}/cards/  # All PNG images
output_v3/{team}/tokens/ # Token PNGs and OBJs
output_v3/{team}/cardbox/ # Cardbox assets
output_v3/{team}/data/{team}-team-data.json  # Optional, for stat embedding
```

**Output**:
```
output_v3/{team}/tts_objects/
  ├── {Team Name} Box.json            # Assembled card box (final TTS save file)
  ├── {Team Name} Box.png             # Preview image
  ├── cards/                          # Individual card JSONs by type
  │   ├── datacards/
  │   │   ├── card-001.json
  │   │   ├── card-002.json
  │   │   └── ...
  │   ├── equipment/
  │   │   └── card-001.json
  │   ├── faction-rules/
  │   ├── firefight-ploys/
  │   ├── operative-selection/
  │   ├── strategy-ploys/
  │   └── token-guide/
  └── tokens/                         # Individual token JSONs
      ├── token-001.json
      ├── token-002.json
      └── ...

output_v3/team-urls.json               # Update manifest for all teams
```

**Structure Details**:
- **Individual card/token JSONs**: Enable granular TTS updates (update single card without re-downloading entire box)
- **Assembled box JSON**: Contains all decks/tokens assembled into final TTS Custom_Model_Bag
- **No intermediate deck JSONs**: Individual cards assemble directly into final box (no datacards.json, equipment.json, etc.)

**Example Assembled Box JSON** (`{Team Name} Box.json`):
```json
{
  "ObjectStates": [
    {
      "Name": "Custom_Model_Bag",
      "Nickname": "Spectre Squad",
      "GUID": "abc123",
      "Transform": {...},
      "CustomMesh": {
        "MeshURL": ".../card-box.obj",
        "DiffuseURL": ".../card-box-texture.jpg"
      },
      "ContainedObjects": [
        {
          "Name": "Deck",
          "Nickname": "Datacards (11)",
          "DeckIDs": [100, 200, 300, ...],
          "CustomDeck": {
            "1": {
              "FaceURL": ".../spectre-veteran-sergeant-front.png",
              "BackURL": ".../spectre-veteran-sergeant-back.png",
              "NumWidth": 1,
              "NumHeight": 1
            },
            ...
          },
          "ContainedObjects": [
            {
              "Name": "Card",
              "Nickname": "SPECTRE VETERAN SERGEANT",
              "CardID": 100,
              "Transform": {...},
              "GMNotes": "{\"stats\":{\"APL\":2,\"Move\":6,\"Save\":4,\"Wounds\":8},...}",
              "LuaScript": "-- Load stats to model..."
            },
            ...
          ]
        },
        {
          "Name": "Deck",
          "Nickname": "Faction Rules (4)",
          "CustomDeck": {
            "10": {
              "FaceURL": ".../elite-fieldcraft-card-1-front.png",
              "BackURL": ".../elite-fieldcraft-card-1-back.png"
            },
            "11": {
              "FaceURL": ".../elite-fieldcraft-card-2-front.png",
              "BackURL": ".../default-backside-portrait.jpg"
            },
            ...
          },
          "ContainedObjects": [...]
        },
        {
          "Name": "Custom_Model_Bag",
          "Nickname": "Token Bag",
          "GUID": "6300e8",
          "Transform": {"posX": 4.0, "posY": -2.5, "posZ": -8.0},
          "ContainedObjects": [
            {
              "Name": "Custom_Model",
              "Nickname": "Advanced Camouflage",
              "CustomMesh": {
                "MeshURL": ".../advanced-camouflage.obj",
                "DiffuseURL": ".../advanced-camouflage.png"
              }
            },
            ...
          ]
        }
      ],
      "LuaScript": "function click_update_rules()...",
      "LuaScriptState": "{\"lastCardUpdate\":\"2026-05-11T12:30:45\"}"
    }
  ]
}

output_v3/team-urls.json    # Updated with all 47 teams
{
  "teams": [
    {
      "team": "spectre-squad",
      "name": "Spectre Squad",
      "object_url": "https://raw.githubusercontent.com/.../Spectre Squad Box.json"
    },
    ...
  ]
}
```

**Potential Issues**:
- ⚠️ GitHub URLs must use correct branch name
- ⚠️ URL encoding for spaces in filenames
- ⚠️ GUID conflicts if not properly managed
- ⚠️ Token bag position may not align with cardbox
- ⚠️ Card numbering (DeckIDs) must be unique
- ⚠️ Elite Fieldcraft cards 2/3 use default backside URL
- ⚠️ memoryList must include all contained objects
- ⚠️ Stat embedding skipped if team-data.json missing (with warning)

---

### **STEP 8: Embed Datacard Stats (DEPRECATED)**
**Script**: `8_embed_datacard_stats.py`

**Status**: ⚠️ **No longer needed in normal pipeline workflow**

Step 7 now embeds stats automatically. This utility is kept for:
- Re-embedding stats without regenerating entire TTS objects
- Debugging stat extraction issues
- Batch updates to existing TTS files

**Actions** (if run manually):
1. For each team:
   - Load `output_v3/{team}/data/{team}-team-data.json` (from step 3)
   - Load TTS object from `output_v3/{team}/tts_objects/`
2. Find datacard deck in TTS object
3. For each datacard in deck:
   - Match card nickname to operative in team-data.json
   - Extract stats: APL, Movement, Save, Wounds
   - Extract weapons with profiles
   - Extract abilities, actions, unique actions
   - Build GMNotes JSON structure
4. Patch each card:
   - Set GMNotes with JSON stats
   - Add LuaScript from `config/defaults/tts-script/datacard-load-stats.lua`
5. Update cardbox:
   - Set LuaScript with click_update_rules() function
   - Update LuaScriptState with lastCardUpdate timestamp
6. Save patched TTS object

**Input**:
```
output_v3/{team}/data/{team}-team-data.json  # From step 3 extraction
output_v3/{team}/tts_objects/{Team Name} Box.json
config/defaults/tts-script/
  ├── datacard-load-stats.lua
  └── cardbox-update-rules.lua
```

**Output**:
```
output_v3/{team}/tts_objects/{Team Name} Box.json  # PATCHED

ContainedObjects[0] = Datacards Deck
  ContainedObjects[0] = SPECTRE VETERAN SERGEANT Card
    {
      "Nickname": "SPECTRE VETERAN SERGEANT",
      "GMNotes": "{
        \"stats\": {\"apl\": \"2\", \"move\": \"6\\\"\", \"save\": \"3+\", \"wounds\": \"8\"},
        \"weapons\": [...],
        \"abilities\": [...],
        \"actions\": [...],
        \"unique_actions\": [...]
      }",
      "LuaScript": "-- Load stats to model...",
      "LuaScriptState": ""
    }
  ...

ObjectStates[0] = Cardbox
  {
    "LuaScript": "function click_update_rules()...",
    "LuaScriptState": "{
      \"lastCardUpdate\": \"2026-05-11T12:30:45\"
    }"
  }
```

**Potential Issues**:
- ⚠️ Depends on step 3's team-data.json existing
- ⚠️ Name matching between TTS nickname and team-data must be exact
- ⚠️ Some operatives may not have complete stat extraction
- ⚠️ GMNotes JSON must be valid (escaped quotes)
- ⚠️ LuaScript may have syntax errors
- ⚠️ Timestamp format must match expected format

---

## Complete File System State After Pipeline

```
input/
  └── (empty or archived)

layers/kt-app/
  ├── processed/{team}/
  │   ├── {team}-datacards.pdf
  │   ├── {team}-equipment.pdf
  │   └── ...
  ├── extracted/{team}/cards/
  │   ├── datacards/{team}-datacards-page_N.pdf
  │   ├── equipment/{team}-equipment-page_N.pdf
  │   └── ...
  ├── extracted/_tuning/{team}/
  │   ├── rough-token-01.png
  │   └── extraction-metadata.json
  ├── classified/{team}/
  │   └── structure.json
  └── metadata.json

output_v3/{team}/
  ├── cards/
  │   ├── datacards/*.png (front+back)
  │   ├── equipment/*.png
  │   ├── faction_rules/*.png (including multi-card)
  │   ├── firefight_ploys/*.png
  │   ├── strategy_ploys/*.png
  │   ├── operatives_selection/*.png
  │   └── token_guide/*.png
  ├── tokens/
  │   ├── {team}-{token-name}.png (with transparency)
  │   ├── {team}-{token-name}.obj
  │   └── token-bag.obj
  ├── cardbox/
  │   ├── card-box.obj
  │   ├── card-box-texture.jpg
  │   └── icon.png
  ├── data/
  │   └── {team}-team-data.json
  └── tts_objects/
      └── {Team Name} Box.json (with embedded stats)

output_v3/
  └── team-urls.json (all 47 teams)

config/
  ├── team-config.yaml
  ├── team-guids.json7 TTS generation (embeds stats automatically)
- **Edge Case**: Step 3 must complete before step 7 runs
- **Impact**: Stats skipped if team-data.json missing (with warning)  └── teams/{team}.yaml

output_v2/  # Still used for reference
  └── {faction}/{team}/tts/  # Source for step 6 assets
```

---

## Data Dependencies Between Steps

```
Step 1 (Process PDFs)
  ↓ Creates: layers/kt-app/processed/, layers/kt-app/extracted/
  
Step 2 (Classify Structure)
  ↓ Reads: layers/kt-app/extracted/
  ↓ Creates: layers/kt-app/classified/{team}/structure.json
  
Step 3 (Extract Team Data)
  ↓ Reads: structure.json, extracted PDFs
  ↓ Creates: output_v3/{team}/data/team-data.json
  ↓           (includes statlines for all operatives)
  
Step 4 (Extract Card Images)
  ↓ Reads: structure.json, extracted PDFs
  ↓ Creates: output_v3/{team}/cards/*/*.png
  
Step 5 (Extract Tokens)
  ↓ Reads: structure.json, faction-rules PDF
  ↓ Creates: output_v3/{team}/tokens/*.png
  
Step 6 (Generate TTS Assets)
  ↓ Reads: output_v2/{faction}/{team}/tts/ (cardbox, token meshes)
  ↓ Creates: output_v3/{team}/cardbox/, output_v3/{team}/tokens/*.obj
  
Step 7 (Generate TTS Objects + Embed Stats)
  ↓ Reads: output_v3/{team}/cards/, tokens/, cardbox/
  ↓         output_v3/{team}/data/team-data.json (from step 3)
  ↓ Creates: output_v3/{team}/tts_objects/*.json (with embedded GMNotes)
  ↓          output_v3/team-urls.json
```

---

## Critical Decision Points & Edge Cases

### 1. **Multi-Card Faction Rules (Elite Fieldcraft Pattern)**
- **Decision**: Regex match `\(CARD \d+/\d+\)` → append card number to name
- **Location**: Step 2 classification
- **Edge Case**: Pattern must match exactly (case-sensitive, spacing)
- **Impact**: If missed, cards 2/3 pair incorrectly as front/back

### 2. **Token Guide Detection**
- **Decision**: Check for "MARKER/TOKEN GUIDE" in first line of page
- **Location**: Step 2 classification
- **Edge Case**: Token guide must be separate from faction rules
- **Impact**: If not detected, tokens won't extract in step 5

### 3. **Background Removal Threshold**
- **Decision**: HSV value > 235, saturation < 25
- **Location**: Step 5 token extraction
- **Edge Case**: White content (skulls, wings) may be removed if threshold too high
- **Impact**: Stray pixels if too low, missing content if too high

### 4. **Default Backside Assignment**
- **Decision**: Front-only cards get default backside from config
- **Location**: Step 4 card image extraction
- **Edge Case**: Portrait vs landscape orientation
- **Impact**: Wrong backside orientation breaks TTS display

### 5. **Statline Embedding Dependency**
- **Decision**: Use team-data.json from step 3 (output_v3/)
- **Location**: Step 8 embed stats
- **Edge Case**: Step 3 must complete before step 8 runs
- **Impact**: Step 8 fails if team-data.json missing or incomplete

### 6. **GUID Management**
- **Decision**: Use team-guids.json for consistent object IDs
- **Location**: Step 7 TTS object generation
- **Edge Case**: New teams need new GUIDs assigned
- **Impact**: GUID conflicts break TTS object spawning

### 7. **GitHub URL Branch Name**
- **Decision**: Hardcoded branch name in URLs (refactor-kt-app-pipeline)
- **Location**: Step 7 TTS object generation
- **Edge Case**: Must update when branch merges to main
- **Impact**: 404 errors for all card images in TTS

---

## Potential Issues Summary

### **High Priority**
1. ⚠️ **Asset dependency**: Step 6 requires `output_v2/{faction}/{team}/tts/` assets from main pipeline
   - **Solution**: Ensure main pipeline has generated these first, or extract assets independently
   
2. ⚠️ **Branch-specific URLs**: GitHub URLs hardcoded to refactor branch
   - **Solution**: Make branch configurable or auto-detect

### **Medium Priority**
3. ⚠️ **Memory usage**: Multiple 300 DPI renders in step 4
   - **Solution**: Process teams in batches, cleanup between teams

4. ⚠️ **Name matching**: Multiple places rely on exact name matching
   - **Solution**: Add normalization function (lowercase, strip non-ASCII)

5. ⚠️ **Error propagation**: Early step failures block later steps
   - **Solution**: Add skip/continue logic for failed teams

### **Low Priority**
6. ⚠️ **Token guide assumption**: Assumes page 5+ for header skip
   - **Solution**: Dynamic header detection per page

7. ⚠️ **Multi-PDF token guides**: Accumulation pattern required
   - **Solution**: Already implemented, but document clearly

8. ⚠️ **Default backside orientation**: May not match card type
   - **Solution**: Detect orientation from PDF dimensions

---

## Running the Complete Pipeline

### Full Pipeline (All Teams)
```powershell
cd pipelines/kt-app/steps

# Run all steps in sequence
python 1_process_pdfs.py
python 2_classify_structure.py
python 3_extract_team_data.py
python 4_extract_card_images.py
python 5_extract_tokens.py
python 6_generate_tts_assets.py
python 7_generate_tts_objects.py  # Generates TTS objects with embedded stats
```

### Single Team (Faster Development)
```powershell
# Process single team through all steps
$team = "spectre-squad"

python 1_process_pdfs.py --team $team --force
python 2_classify_structure.py --team $team --force
python 3_extract_team_data.py --team $team --force
python 4_extract_card_images.py --team $team --force
python 5_extract_tokens.py --teams $team
python 6_generate_tts_assets.py --teams $team
python 7_generate_tts_objects.py --teams $team  # Embeds stats automatically
```

### Prerequisites
Before running refactor pipeline:
```powershell
# 1. Ensure TTS assets exist (main pipeline for cardbox/token meshes)
python script/run_pipeline.py --step 3.5 --teams spectre-squad  # Generate cardbox

# Note: Statlines are extracted by refactor pipeline step 3
# No dependency on main pipeline's roster.json
```

---

## Validation Checklist

After running pipeline for a team, verify:

- [ ] `layers/kt-app/classified/{team}/structure.json` exists and valid
- [ ] All card types have PNG files in `output_v3/{team}/cards/`
- [ ] Multi-card faction rules have separate cards with card numbers
- [ ] Tokens exist in `output_v3/{team}/tokens/` with transparency
- [ ] No stray pixels outside token boundaries
- [ ] TTS object exists in `output_v3/{team}/tts_objects/`
- [ ] TTS object has all decks (datacards, equipment, ploys, faction rules)
- [ ] Faction rules deck has 4 cards (for Spectre Squad)
- [ ] Token bag exists with all tokens
- [ ] Datacards have GMNotes with stats JSON
- [ ] Cardbox has LuaScript with lastCardUpdate timestamp
- [ ] `output_v3/team-urls.json` includes team entry

---

## Comparison: Main vs Refactor Pipeline

| Aspect | Main Pipeline (script/) | Refactor Pipeline (pipelines/kt-app/) |
|--------|------------------------|--------------------------------------|
| **Architecture** | Monolithic orchestrator | Modular 8 steps |
| **Output** | output_v2/ (faction-organized) | output_v3/ (team-organized) |
| **Intermediate** | None (direct processing) | layers/kt-app/ (full state) |
| **Classification** | Implicit in extraction | Explicit structure.json |
| **Token Cleanup** | Original thresholds | Improved (v>235, s<25) + hard boundary |
| **Multi-Card Fix** | Implemented | Implemented |
| **Statline Source** | Extracts directly | Self-contained (step 3) |
| **Reusability** | Tightly coupled | Loosely coupled steps |
| **Debugging** | Difficult (no intermediate state) | Easy (inspect layers/) |

---

## Recommendations

1. ~~**Merge steps 7 & 8**: Generate TTS objects with stats embedded from the start (single pass)~~ ✅ **COMPLETED**
2. **Make step 6 self-contained**: Extract cardbox assets from PDFs instead of copying from output_v2
3. **Add validation step**: Verify output after each step
4. **Parallel processing**: Run step 4 (card images) in parallel per team
5. **Consolidate token extraction**: Merge main and refactor token pipelines
6. **Auto-detect branch**: Don't hardcode "refactor-kt-app-pipeline" in URLs
7. **Add cleanup step**: Remove intermediate files after success
8. **Document GUID assignment**: Process for adding new teams
9. **Test multi-card patterns**: Verify with other teams (Angels of Death, Warpcoven)
