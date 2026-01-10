# Questions for Clarification

This document tracks questions that need answers before implementing features.

## ✅ Answered Questions

All questions have been answered! See the **Decisions Summary** section below for quick reference.

---

## 📋 Decisions Summary

### Feature Organization
- **Faction Hierarchy**: Add `{faction}/{army}/{teamname}` structure to `processed/` and metadata
  - Example: `xenos/leagues-of-votann/hearthkyn-salvagers`
  - Keep `output/` flat for backwards compatibility
  - Future: Create `output/v2/` with new structure

### Processing Workflow
- **Input Structure**: Process all PDFs in `input/` recursively (any subfolder structure allowed)
- **Archive Policy**: Keep archived files forever (acceptable to accumulate)
- **Change Detection**: Use content hash (D) to detect actual changes
- **Default Behavior**: CLI args → config file → process all teams

### Stats Extraction
- **Accuracy**: 100% accuracy required (A) - show warnings/errors rather than wrong data
- **Scope**: All card types need stats extracted (datacards most complex, others simpler)
- **Manual Review**: Yes, manual review when uncertain
- **Output Format**: YAML/JSON for structure, then generate CSV
- **OCR Service**: Use free/local tools (speed not critical)
- **Version History**: Only keep current stats (no historical tracking)

### Metadata
- **Status Tracking**: Use boolean `present: true/false` instead of complex status values
- **Additional Fields**: Add manually as needed, automate later
- **Team Properties**: Track faction, army, type (elite/horde/normal) based on operative count

### Implementation
- **Feature Priority**: 00 → 01 → 02 → 05 → 03 → 04
- **Rollout**: One feature at a time
- **Testing**: Use existing archived and processed files as test data

---

## 🔍 Open Questions (New)

### Feature 06: Output v2 Structure
- **Q**: When should we implement the hierarchical `output/v2/` structure?
- **Priority**: Future
- **Impact**: Better organization but requires TTS URL migration
- **Considerations**: Need migration strategy, documentation for users

### Stats Extraction Details
- **Q**: For weapon rules that reference abilities lower on the card, should we:
  - A: Just list the keyword name (simple)
  - B: Try to extract and link the full description
  - C: Flag for manual linking
- **Priority**: Medium
- **Recommendation**: Start with A, enhance later

### TTS Scripting Investigation
- **Q**: Should we investigate automating TTS object creation/updates?
- **Priority**: Low (nice to have)
- **Impact**: Would make URL migrations easier
- **Next Steps**: Research TTS scripting capabilities

---

## 📝 Answered - General Questions

### 1. Processing Workflow ✅
- **Decision**: Manual export from mobile app using phone link
- **Workflow**: Kill Team app → Share → Phone Link → Save to repo
- **Impact**: No automation possible, manual process acceptable

### 2. GitHub Repository ✅
- **Decision**: Repository is public at `Wen-Qualtu/kt-datacards`
- **Base URL**: `https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/`
- **Example**: `.../output/angels-of-death/datacards/assault-intercessor-grenadier_back.jpg`

---

## Feature 01: Project Restructuring
📝 Answered - Feature 01: Project Restructuring

### 1. Input Folder Naming ✅
- **Decision**: Use `input/` and process recursively including all subfolders
- **Benefit**: Flexible structure for user convenience
- **Note**: Files moved after processing anyway

### 2. Archive Policy ✅
- **Decision**: Keep archived files forever
- **Rationale**: GUIDs linked to source PDFs, overwrite on reprocessing
- **Storage**: Acceptable growth, not a concern


## Feature 03: Enhanced Metadata

### 1. Update Tracking Method
- **Q**: For tracking updates, which approach do you prefer?
- *📝 Answered - Feature 03: Enhanced Metadata

### 1. Update Tracking Method ✅
- **Decision**: Content hash comparison (D)
- **Note**: Test to ensure it detects actual changes correctly
- **Implementation**: Focus on image content hashing

### 2. Faction & Army Hierarchy ✅
- **Decision**: Implement 3-level structure: `{faction}/{army}/{teamname}`
- **Example**: `xenos/leagues-of-votann/hearthkyn-salvagers`
- **Factions**: imperium, chaos, xenos
- **Rollout**: 
  - ✅ Add to `processed/` folder structure immediately
  - ✅ Add to metadata YAML immediately
  - ✅ Add to CSV output immediately
  - ⏳ Keep `output/` flat (backwards compatibility)
  - 🔮 Future: Create `output/v2/` with hierarchy

### 3. Team Versions ✅
- **Decision**: No version tracking in metadata
- **Rationale**: Git tracks changes; TTS URL changes are cumbersome
- **Future**: Use `output/v2/` path for structural changes
- **Note**: TTS scripting investigation is a potential feature

### 4. Status Values ✅
- **Decision**: Use boolean `present: true/false` for card types
- **Rationale**: Hard to track completeness without manual input
- **Keep Simple**: Either present or missing

### 5. Additional Metadata ✅
- **Decision**: Add fields manually as needed, automate later
- **Track**: 
  - `type`: elite/horde/normal (derivable from operative count)
  - Other fields: add as discovered
- **Note**: Kill Team doesn't use points system

### 1. Priority Stats
- **Q**: Which stats are most important to extract?
- **All possible stats**:
  - Unit stats: Movement, APL, GA, DF, SV, Wounds
  - Weapons: Range, Attacks, BS/WS, Damage, Special Rules
  - Abilities: Name, Type, Text, Timing
  - Keywords
  - Equipment
- **Priority**: High
- **Impact**: Determines scope and effort
- *📝 Answered - Feature 04: Stats Extraction

### 1. Priority Stats ✅
**Decision**: Extract ALL stats from datacards

**Header Stats**:
- Name
- APL (Action Point Limit)
- MOVE (Movement)
- SAVE
- WOUNDS

**Weapon Table** (with icon for ranged/melee):
- Name (weapon name)
- ATK (attacks) - number of attack dice
- HIT - roll needed (e.g., "4+")
- DMG (damage) - format "X/Y" where X=normal, Y=critical
  - Store as: `normal`, `critical`, and combined `"X/Y"`
- WR (weapon rules) - comma-separated keywords

**Abilities**:
- Name
- Description (can be multi-column or span to back of card)
- Store as array of objects

### 2. Accuracy Requirements ✅
- **Decision**: 100% accuracy required (A)
- **Rationale**: Wrong data on cards is unacceptable
- **Strategy**: Show errors/warnings when uncertain rather than guessing
- **Process**: Trigger manual review when confidence is low

### 3. Card Type Scope ✅
- **Decision**: Extract from ALL card types
- **Complexity**:
  - Datacards: Very complex (full structure above)
  - Equipment/Faction Rules/Ploys: Simple (name + description)
- **Approach**: Start with datacards, others are simpler

### 4. Version History ✅
- **Decision**: Only keep current stats (no historical tracking)
- **Rationale**: Git provides version history if needed

### 5. Manual Review Process ✅
- **Decision**: Yes, prompt for manual review when uncertain
- **Workflow**: Process → Flag uncertain → Prompt user → Correct → Continue

### 6. Output Format Priority ✅
- **Decision**: YAML or JSON primary (structured), generate CSV after
- **Rationale**: Complex nested structure needs hierarchical format
- **Process**: YAML/JSON → CSV extraction for sharing

### 7. Cloud OCR Services ✅
- **Decision**: Use free/local tools (no paid services for now)
- **Rationale**: Speed not critical (monthly updates, hours acceptable)
- **Tools**: Start with Tesseract OCR
- **Recommendation**: Both (C)
- **A**: Both, but probably only use cli

### 2. Default Behavior
- **Q**: When running with no arguments, should it process all teams or have a default subset?
- **Options**:
  - A: Process all teams (current behavior)
  - B: Process teams in config file
  - C: Require explicit team selection
- **Priority**: Low
- **Recommendation**: A (process all)
- **A**: A, combined with point 1. it should do cli, if not then check config, if not do all

###📝 Answered - Feature 05: Parameterized Execution

### 1. CLI vs. Config File ✅
- **Decision**: Support both (C)
- **Usage**: Likely mostly CLI in practice
- **Priority**: CLI arguments → Config file → Default behavior

### 2. Default Behavior ✅
- **Decision**: Cascading priority system
  1. Use CLI arguments if provided
  2. Else check config file
  3. Else process all teams
- **Keeps**: Flexibility with sensible defaults

### 3. Progress Indicators ✅
- **Decision**: Nice to have, low priority
- **Implementation**: Add after core functionality stable

### 3. Testing Requirements
- **Q**: Do you have sample PDFs we can use for testing?
- **Needed**: Examples from different teams, different card types
- **Priority**: High
- **Impact**: Development and testing
- **A**: those are already in the archive and proccessed files. That's all the files we imported up to now. there are lots of other teams that I will add later, but that is manual work and this should be a good represitation.

---

## How to Answer These Questions

You can answer directly in conversation, or update this file with answers:
📝 Answered - Implementation Priority

### 1. Feature Order ✅
**Decision**: Implement in this order:
1. **Feature 00**: Poetry + Task Setup (foundation for multi-machine)
2. **Feature 01**: Project Restructuring (harder if we grow)
3. **Feature 02**: Code Refactoring (harder if we grow)
4. **Feature 05**: Parameterized Execution (quick wins)
5. **Feature 03**: Enhanced Metadata (organization)
6. **Feature 04**: Stats Extraction (complex, can defer)

### 2. Phased Rollout ✅
- **Decision**: One feature at a time
- **Approach**: Complete and test each feature before starting next

### 3. Testing Requirements ✅
- **Decision**: Use existing archived and processed files
- **Data**: Current files represent good variety of teams and card types
- **Future**: More teams will be added manually over time

---

## ✅ All Questions Answered!

Ready to begin implementation. Start with Feature 00 (Poetry + Task Setup).

See **[DEVELOPMENT.md](DEVELOPMENT.md)** for coding guidelines and rules.