# TTS Command Node Integration Analysis

## Overview

This document analyzes how the existing TTS Command Node works and proposes how to integrate it with the kt-datacards metadata pipeline to eliminate the need for New Recruit and .rosz file generation.

## Current Workflow (Manual)

### Step-by-Step Process:
1. **Create roster** in New Recruit (external app): https://www.newrecruit.eu/app/MySystems
2. **Export as .rosz** file (BattleScribe format)
3. **Convert to team code** at https://datateamapp.azurewebsites.net/Encode
4. **Load in TTS** via Command Node by pasting team code
5. **Assign 3D models** to each operative in TTS
6. **Extend UI** to add scripts to models
7. Models now have interactive UIs, statlines, and rules in their descriptions

## What the .rosz File Contains

From analyzing the example Grey Knight roster in [dev/examples/3356996125.json](dev/examples/3356996125.json), the .rosz file (BattleScribe format) contains:

### Operative Data:
- **Name**: `@name` and optional `@customName`
- **Stats**:
  - M (Movement) - e.g., "33&&" (3" with circle symbol)
  - APL (Action Point Limit) - e.g., "3"
  - GA (Group Activation) - e.g., "1"
  - DF (Defense) - e.g., "3"
  - SV (Save) - e.g., "3+"
  - W (Wounds) - e.g., "11" or "12"

### Weapon Profiles:
For each weapon:
- **Name**: e.g., "(R) Storm bolter" or "(M) Nemesis falchions"
- **Characteristics**:
  - A (Attacks) - e.g., "4"
  - WS/BS (Weapon Skill/Ballistic Skill) - e.g., "2+" or "3+"
  - D (Damage) - e.g., "4/5" (normal/critical)
  - SR (Special Rules) - e.g., "Relentless"

### Additional Data:
- **Unique Actions**: e.g., "Manifest Psychic Power (1AP)"
- **Abilities**: Special rules text
- **Psychic Powers**: For psyker operatives
- **Categories/Keywords**: e.g., ["Leader", "Psyker", "Grey Knight"]

## What Happens in TTS

The Command Node Lua script ([dev/examples/3356996125.json](dev/examples/3356996125.json) lines 555+) performs these operations:

### 1. Parse Roster Data
```lua
function modelToInfo(m)
  -- Extracts from BattleScribe JSON:
  -- - Operative stats (M, APL, GA, DF, SV, W)
  -- - Weapon profiles with stats
  -- - Unique actions
  -- - Abilities
  -- - Categories/keywords
end
```

### 2. Create Model Descriptions
Generates formatted description text for TTS models:
```
Justicar
[APL 3] [MOVE 6"] [SAVE 3+] [WOUNDS 12]
Grey Knight, Imperium, Sanctic Astartes, Psyker, Leader

Weapons
(R) Storm bolter (Justicar)
ATK 4 HIT 2+ DMG 4/5
WR: Relentless

Actions
- Manifest Psychic Power (1AP)

Abilities
- Inspirational Example
```

### 3. Create Interactive UI
- Wound tracker with current/max wounds
- Damage/heal context menu actions
- Range measurement circles (1", 2", 3", 6")
- Status icons (engage/conceal, injured, etc.)

## Our Metadata Structure

Currently in `metadata/{team}/extraction_metadata.json`:

### What We Have:
```json
{
  "datacards": {
    "novitiate-superior": {
      "card_name": "novitiate-superior",
      "extraction": {
        "full_text": "... 3 APL WOUNDS SAVE MOVE 6\" 3+ 9 32 ..."
      },
      "output": {
        "front_image": "output_v2/imperium/novitiates/datacards/..."
      }
    }
  }
}
```

### What We Need to Add:
```json
{
  "datacards": {
    "novitiate-superior": {
      "card_name": "novitiate-superior",
      "operative_data": {
        "display_name": "Novitiate Superior",
        "stats": {
          "M": "6\"",
          "APL": 3,
          "GA": 1,
          "DF": 3,
          "SV": "3+",
          "W": 9
        },
        "weapons": [
          {
            "name": "(R) Plasma pistol (standard)",
            "stats": {
              "A": 4,
              "BS": "3+",
              "D": "3/5",
              "SR": "Range 8\", Piercing 1"
            }
          },
          {
            "name": "(M) Power weapon",
            "stats": {
              "A": 4,
              "WS": "3+",
              "D": "4/6",
              "SR": "Lethal 5+"
            }
          }
        ],
        "abilities": [
          {
            "name": "Inspirational Example",
            "text": "Whenever this operative incapacitates an enemy operative..."
          }
        ],
        "actions": [],
        "keywords": ["NOVITIATE", "IMPERIUM", "ADEPTA SORORITAS", "LEADER", "SUPERIOR"]
      },
      "extraction": {
        "full_text": "..."
      }
    }
  }
}
```

## Proposed Solution

### Phase 1: Enhanced Metadata Extraction

Create a new parser that processes datacard OCR text and extracts structured data:

**New File**: `script/parse_operative_stats.py`

```python
class OperativeStatsParser:
    """Parse operative stats from datacard OCR text."""
    
    def parse_datacard(self, full_text: str) -> OperativeData:
        """
        Extract structured data from datacard text.
        
        Returns:
            OperativeData with:
            - stats (M, APL, GA, DF, SV, W)
            - weapons with profiles
            - abilities
            - actions
            - keywords
        """
        pass
```

### Phase 2: TTS Metadata Export

Create an exporter that generates TTS-compatible JSON:

**New File**: `script/generate_tts_team_data.py`

```python
def export_team_for_tts(team_name: str) -> dict:
    """
    Generate TTS-compatible team data from metadata.
    
    Output format matches what the Command Node expects:
    {
      "roster": {
        "@name": "Novitiates",
        "forces": {
          "force": {
            "selections": {
              "selection": [
                {
                  "@id": "unique-guid",
                  "@name": "Novitiate Superior",
                  "profiles": {
                    "profile": [
                      {
                        "@typeName": "Operative",
                        "characteristics": {...}
                      },
                      {
                        "@typeName": "Weapons",
                        "characteristics": {...}
                      }
                    ]
                  },
                  "categories": {...}
                }
              ]
            }
          }
        }
      }
    }
    """
    pass
```

### Phase 3: Simplified TTS Command Node

Create a new version of the Command Node that:

1. **Loads team directly from GitHub**: 
   - URL: `https://raw.githubusercontent.com/{user}/{repo}/main/metadata/{team}/tts_team_data.json`
   
2. **Team selection UI**:
   - Dropdown of all available teams
   - No need for external apps or encoding
   
3. **Model assignment**:
   - Same as current: click operative, select 3D model
   
4. **Script generation**:
   - Identical to current implementation
   - Same interactive UI and features

**Benefits**:
- ✅ No external dependencies (New Recruit, Datateam encoder)
- ✅ Always up-to-date with latest card data
- ✅ Single source of truth (your metadata)
- ✅ Easier for users (just select team name)
- ✅ Version controlled (via git)

## Data Extraction Challenges

### From Datacard OCR Text

Looking at the extracted text, we need to parse:

**Example**: `"3 APL WOUNDS SAVE MOVE 6\" 3+ 9 32"`

Pattern recognition needed:
- Stats appear at bottom of card
- Stat order: APL, SAVE, WOUNDS, MOVE (varies by layout)
- Movement has `"` symbol
- Some stats have symbols (3&&, 6&&)

**Weapon Profiles**:
```
WR  Plasma pistol (standard) 4 3+ 3/5  Range 8", Piercing 1
```
Pattern:
- Optional WR (weapon rules indicator)
- Weapon name
- Attacks (number)
- Hit roll (with +)
- Damage (number/number)
- Special rules (comma-separated)

### Parsing Strategy:

1. **Use regex patterns** for common stat layouts
2. **Keyword matching** for abilities (look for ":")
3. **Weapon identification** (look for ranged (R) or melee (M) prefixes)
4. **Fallback to current text** if structured parsing fails

## Implementation Roadmap

### Immediate (Can Do Now):
1. ✅ **Analyze existing metadata** - DONE (this document)
2. ⚠️ **Create stat parser** - Parse operative stats from OCR text
3. ⚠️ **Enhance metadata structure** - Add `operative_data` field to extraction_metadata.json

### Near Term:
4. ⚠️ **Create TTS exporter** - Generate BattleScribe-compatible JSON
5. ⚠️ **Test with existing teams** - Validate parsed data matches game rules
6. ⚠️ **Host team data** - Make available via GitHub raw URLs

### Future:
7. ⚠️ **Create simplified Command Node** - New Lua script for TTS
8. ⚠️ **User testing** - Get feedback from TTS community
9. ⚠️ **Documentation** - User guide for new workflow

## Questions for Discussion

### Data Extraction:
1. **How accurate is the OCR?** Can we reliably parse stats or do we need manual verification?
2. **What about card variants?** Some operatives have different loadouts - how to represent?
3. **Two-sided cards?** Some datacards have additional rules on back

### TTS Integration:
1. **Model library?** Should we also generate a database of recommended 3D models?
2. **Backwards compatibility?** Should new Command Node support old .rosz format too?
3. **Update mechanism?** How often to refresh team data from GitHub?

### Scope:
1. **All teams or just some?** Start with a few well-tested teams?
2. **Compendium support?** How to handle team updates when GW releases balance patches?
3. **Custom teams?** Should users be able to add their own parsed data?

## Example: What Users Would See

### Current Workflow (7 Steps):
1. Open New Recruit website
2. Build roster
3. Export .rosz
4. Go to Datateam encoder website
5. Upload file, copy code
6. Paste in TTS Command Node
7. Assign models

### Proposed Workflow (4 Steps):
1. Open TTS Command Node
2. Select team from dropdown (e.g., "Novitiates")
3. Click "Load Team"
4. Assign models

**Time saved**: ~5-10 minutes per team setup
**Complexity**: From "moderate" to "simple"
**Dependencies**: From 3 external tools → 0 external tools

## Conclusion

**Feasibility**: HIGH  
This is absolutely doable. The hardest part is parsing the OCR text reliably, but we can:
- Start with manual verification
- Build confidence over time with more teams
- Have fallbacks for unparseable cards

**Value**: HIGH  
- Dramatically simplifies user workflow
- Leverages existing kt-datacards data
- No external service dependencies
- Always up-to-date with your repository

**Recommendation**: Start with Phase 1 (stat parsing) on 2-3 teams as a proof-of-concept. Once that's working well, move to Phase 2 (TTS export) and finally Phase 3 (new Command Node).

---

Would you like me to:
1. Start implementing the stat parser for a specific team (e.g., Novitiates)?
2. Create the enhanced metadata structure specification?
3. Build a prototype TTS team data exporter?
