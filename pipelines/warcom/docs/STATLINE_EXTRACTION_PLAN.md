# Statline Extraction from Datacards - Project Plan

## Current Workflow (Complex)

1. User creates .rosz roster file in BattleScribe
2. Uploads to https://datateamapp.azurewebsites.net/Encode 
3. Gets encoded code (e.g., "YlduzBWvHG")
4. TTS mod fetches encoded data using this code
5. Stats applied to models on table

## Target Workflow (Simplified)

1. User selects team from list in TTS
2. TTS loads statline JSON directly from GitHub repo
3. Stats applied to models on table

## Technical Approach

### Phase 1: Extract Stats from Datacards

**Input:** Warcom pipeline output  
`output/{team}/cards/datacards/{team}-{operative}-front.jpg`

**Extract Stats:**
- **M** (Movement): "6□" format
- **APL** (Action Point Limit): number
- **GA** (Group Activation): number  
- **DF** (Defense): number
- **SV** (Save): "3+" format
- **W** (Wounds): number

**Weapons:**
- **A** (Attacks): number
- **WS/BS** (Hit): "2+", "3+" format
- **D** (Damage): "3/4" format
- **SR** (Special Rules): text

**Method:** 
- OCR with Tesseract or PyMuPDF text extraction
- Table detection (stat tables are in consistent format)
- Regex pattern matching for stats

### Phase 2: Convert to BattleScribe-Compatible Format

**Map terminology:**
```
Datacard → BattleScribe
M        → Move
APL      → APL (same)
GA       → (not in BattleScribe - ignore)
DF       → (not in BattleScribe - ignore)
SV       → Save
W        → Wounds

Weapons:
A        → ATK
WS/BS    → HIT
D        → DMG
SR       → WR (weapon rules)
```

**Output Format (XML → JSON):**
```json
{
  "roster": {
    "forces": {
      "force": {
        "selections": [{
          "name": "Operative Name",
          "profiles": [{
            "typeName": "Operative",
            "characteristics": {
              "APL": "3",
              "Move": "6\"",
              "Save": "3+",
              "Wounds": "12"
            }
          }],
          "weapons": [{
            "name": "Weapon Name",
            "ATK": "4",
            "HIT": "3+",
            "DMG": "3/4",
            "WR": "Relentless"
          }]
        }]
      }
    }
  }
}
```

### Phase 3: Generate Repository JSON Files

**Structure:**
```
statlines/
  {team-name}/
    roster.json        # Full BattleScribe-compatible JSON
    metadata.json      # Team info, last updated, etc.
```

**GitHub URL format:**
```
https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/statlines/{team-name}/roster.json
```

### Phase 4: TTS Integration (Future)

**Modify TTS mod to:**
1. Show team selector dropdown
2. Fetch from GitHub instead of encode site:
   ```lua
   local url = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/statlines/" .. teamSlug .. "/roster.json"
   WebRequest.get(url, parseRoster)
   ```
3. Parse JSON (same format as before)
4. Apply to models

## Implementation Steps

### Step 1: Analyze Datacard Layout ✓
- [x] Examine sample datacards
- [x] Identify stat table locations
- [x] Document stat formats

### Step 2: Create OCR/Extraction Module
- [ ] Create `pipelines/warcom/steps/7_extract_statlines.py`
- [ ] Use existing PDF text extraction from step 2
- [ ] Extract stat tables with regex patterns
- [ ] Handle edge cases (different layouts, missing data)

### Step 3: Data Model
- [ ] Create `StatlineData` class matching BattleScribe structure
- [ ] Validation rules for each stat
- [ ] Weapon profile parsing

### Step 4: Generate Output Files
- [ ] Create `statlines/{team}/` directories
- [ ] Generate `roster.json` compatible with current TTS mod
- [ ] Generate `metadata.json` with extraction details
- [ ] Add to `.tts-metadata.json` for change tracking

### Step 5: Testing
- [ ] Test with sample teams (Battleclade, Kommandos, etc.)
- [ ] Validate JSON against BattleScribe schema
- [ ] Test loading in TTS mod (if available)

### Step 6: Documentation
- [ ] Update DEVELOPMENT.md with statline extraction
- [ ] Create usage guide for TTS integration
- [ ] Document stat mapping and edge cases

## Key Files to Examine

**Example outputs (for format reference):**
- `dev/examples/3356996125.json` - Grey Knights roster
- `dev/examples/3451008956.json` - Another roster
- `dev/examples/rav.ros` - Raveners BattleScribe XML

**Datacard sources:**
- `output/{team}/cards/datacards/*.jpg` - Operative datacards
- Contains stat tables in consistent format

## Technical Challenges

1. **OCR Accuracy**: Stat tables may have complex formatting
   - Solution: Use template matching + OCR
   - Validate extracted values against expected ranges

2. **Weapon Rules**: Complex text that varies by weapon
   - Solution: Extract as-is, map to known rules later
   - Create weapon rule dictionary

3. **Datacard Variations**: Different teams may have different layouts  
   - Solution: Create multiple extraction patterns
   - Fallback to manual mapping for edge cases

4. **Data Validation**: Ensure extracted stats make sense
   - Solution: Validate ranges (APL: 2-3, Wounds: 7-20, etc.)
   - Flag suspicious extractions for review

## Next Actions

1. Examine sample datacards to understand layout
2. Create extraction patterns for stats
3. Build prototype extraction for one team
4. Validate output format matches BattleScribe
5. Scale to all teams

## Success Criteria

- ✅ Extract operative stats from datacards with >95% accuracy
- ✅ Generate BattleScribe-compatible JSON
- ✅ Files hosted on GitHub and accessible
- ✅ TTS mod can load and parse the data
- ✅ Eliminates need for external encode site
