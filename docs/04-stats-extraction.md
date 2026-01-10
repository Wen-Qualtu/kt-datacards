# Feature 04: Stats Extraction

## Status
🔴 Not Started

## Overview
Extract structured data from datacards (stats, weapon profiles, abilities) and store in YAML/CSV format for use by other applications.

## Goal
Parse datacards to extract:
- Unit stats (Wounds, APL, Movement, Save)
- Weapon profiles (Range, Attacks, Damage, etc.)
- Special abilities
- Keywords
- Equipment

## Data Structure

### Example Datacard Data (YAML)

```yaml
teams:
  angels-of-death:
    operatives:
      - id: "space-marine-warrior"
        name: "Space Marine Warrior"
        type: "operative"
        stats:
          movement: "6"
          apl: "2"
          ga: "3+"  # Group Activation
          df: "3"   # Defense
          sv: "3+"  # Save
          wounds: "18"
        
        weapons:
          - name: "Bolt Gun"
            type: "ranged"
            range: "12"
            attacks: "4"
            skill: "3+"
            damage:
              normal: "3/4"
              critical: "4/5"
            special_rules:
              - "Ceaseless"
          
          - name: "Fists"
            type: "melee"
            range: "-"
            attacks: "3"
            skill: "3+"
            damage:
              normal: "3/4"
              critical: "4/5"
        
        abilities:
          - name: "Angels of Death"
            type: "passive"
            description: "Each time this operative fights in combat, in the Roll Attack Dice step..."
            timing: "combat"
        
        keywords:
          - "IMPERIUM"
          - "ADEPTUS ASTARTES"
          - "WARRIOR"
        
        equipment:
          - "Krak Grenade"
          - "Frag Grenade"
      
      - id: "space-marine-sergeant"
        name: "Space Marine Sergeant"
        # ... similar structure

  blooded:
    operatives:
      # ...
```

## Extraction Challenges

### OCR Accuracy
- Cards are images, text extraction can be imperfect
- Tables may not parse correctly
- Special symbols (†, *, etc.) may be misread

### Layout Variations
- Different card types have different layouts
- Weapon tables can vary in format
- Ability text can be lengthy

### Data Validation
- Need to verify extracted data makes sense
- Cross-reference with known patterns
- Flag anomalies for manual review

## Implementation Approach

### Phase 1: Template Identification
- [ ] Identify common card templates/layouts
- [ ] Create template matchers
- [ ] Map regions of interest (ROI) for each template

### Phase 2: Text Extraction
- [ ] Use OCR on specific regions
- [ ] Extract stat blocks
- [ ] Extract weapon tables
- [ ] Extract ability text
- [ ] Extract keywords

### Phase 3: Parsing & Structuring
- [ ] Parse stat values into structured format
- [ ] Parse weapon tables into arrays
- [ ] Structure abilities with metadata
- [ ] Normalize text (fix OCR errors)

### Phase 4: Validation
- [ ] Validate against expected patterns
- [ ] Check for missing required fields
- [ ] Flag suspicious values
- [ ] Create validation report

### Phase 5: Output Generation
- [ ] Export to YAML (primary format)
- [ ] Export to CSV (for spreadsheet use)
- [ ] Export to JSON (for web apps)
- [ ] Generate human-readable reports

### Phase 6: Manual Review Interface
- [ ] Create review tool for flagged entries
- [ ] Allow manual corrections
- [ ] Store corrections for future reference

## Technical Stack

### OCR Options
1. **Tesseract OCR** (open source)
   - Pros: Free, good accuracy
   - Cons: May need training for special symbols
   
2. **Azure Computer Vision** (cloud)
   - Pros: Excellent accuracy, handles tables
   - Cons: Costs money, requires API key
   
3. **AWS Textract** (cloud)
   - Pros: Designed for document extraction
   - Cons: Costs money

**Recommendation**: Start with Tesseract, consider cloud services if needed

### Data Validation
- **jsonschema**: Validate YAML against schema
- **pandas**: CSV manipulation and validation
- **regex**: Pattern matching for values

## Output Formats

### 1. YAML (Primary)
```yaml
# stats/angels-of-death.yaml
```
- Human readable
- Comments supported
- Hierarchical
- Easy to edit

### 2. CSV (Spreadsheets)
```csv
team,operative_id,operative_name,movement,apl,wounds,weapon_name,weapon_range,weapon_attacks
angels-of-death,space-marine-warrior,Space Marine Warrior,6,2,18,Bolt Gun,12,4
```
- Excel compatible
- Easy sorting/filtering
- Flat structure

### 3. JSON (Web Apps)
```json
{
  "teams": {
    "angels-of-death": { ... }
  }
}
```
- API friendly
- JavaScript compatible
- Widely supported

## Stats to Extract

### Unit Stats
- [ ] Movement (e.g., "6", "8", "3□")
- [ ] APL (Action Point Limit)
- [ ] GA (Group Activation)
- [ ] DF (Defense)
- [ ] SV (Save)
- [ ] W (Wounds)

### Weapon Stats
- [ ] Name
- [ ] Type (Ranged/Melee)
- [ ] Range (e.g., "12", "□")
- [ ] Attacks (e.g., "4", "3+D3")
- [ ] BS/WS (Ballistic/Weapon Skill)
- [ ] Damage (Normal/Critical)
- [ ] Special Rules

### Abilities
- [ ] Name
- [ ] Type (Passive, Action, etc.)
- [ ] Timing
- [ ] Full text description

### Keywords
- [ ] List of keywords

### Equipment
- [ ] List of equipment options

## Example Usage

```python
from src.extractors.stats_extractor import StatsExtractor

extractor = StatsExtractor()

# Extract stats from a team
stats = extractor.extract_team_stats("angels-of-death")

# Save to various formats
stats.to_yaml("stats/angels-of-death.yaml")
stats.to_csv("stats/angels-of-death.csv")
stats.to_json("stats/angels-of-death.json")

# Query stats
warrior = stats.get_operative("space-marine-warrior")
print(f"Wounds: {warrior.stats.wounds}")
print(f"Weapons: {len(warrior.weapons)}")
```

## Questions to Answer

1. **Scope**: Which card types should we extract stats from?
   - Datacards: Yes (all unit stats)
   - Equipment: Yes (for equipment stats)
   - Faction Rules: Maybe (general rules)
   - Ploys: Probably not (mostly text)

2. **Accuracy vs. Speed**: How important is 100% accuracy?
   - Manual review required?
   - Acceptable error rate?

3. **Update Frequency**: How often do stats change?
   - Should we track stat history?
   - Version control for stats?

4. **Output Location**: Where should stats files go?
   ```
   stats/
   ├── yaml/
   │   └── {teamname}.yaml
   ├── csv/
   │   └── {teamname}.csv
   └── json/
       └── {teamname}.json
   ```

5. **Validation Rules**: What makes data "valid"?
   - Movement typically 3-8
   - Wounds typically 1-30
   - Required fields
   - Type checking

## Challenges & Risks

### High Risk Areas
- **OCR Accuracy**: May require significant tuning
- **Template Variety**: Different card layouts require different parsers
- **Special Characters**: Symbols may not extract correctly
- **Table Parsing**: Complex tables can be hard to parse

### Mitigation
- Start with one team as proof of concept
- Build extensive validation
- Plan for manual review process
- Create feedback loop for improvements

## Success Criteria
- [ ] Can extract stats from 90%+ of datacards
- [ ] Validation catches obvious errors
- [ ] Output is usable by other applications
- [ ] Process is documented and repeatable

## Estimated Effort
- **Complexity**: Very High
- **Time**: 16-24 hours
- **Risk**: High (OCR accuracy unknown)

## Dependencies
- Should complete Feature 02 (Code Refactoring)
- Can work in parallel with other features
- Independent processing pipeline

## Future Enhancements
- Machine learning for improved accuracy
- Automated error correction
- Stats comparison between versions
- Web interface for browsing stats
