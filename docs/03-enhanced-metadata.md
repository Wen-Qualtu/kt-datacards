# Feature 03: Enhanced Metadata

## Status
🔴 Not Started

## Overview
Expand the `team-mapping.yaml` to include richer metadata about teams, card types, update tracking, and file locations.

## Current State
`team-mapping.yaml` contains only name mappings:
```yaml
angels-of-death:
  - space-marine-captain
  - angels of death
  
blooded:
  - blooded
```

## Proposed Enhanced Structure

```yaml
teams:
  angels-of-death:
    # Identity
    canonical_name: "Angels of Death"
    aliases:
      - "space-marine-captain"
      - "angels of death"
      - "Space Marines"
    
    # Card Types Available
    card_types:
      datacards:
        status: "complete"
        last_updated: "2025-12-15"
        file_count: 8
        source_hash: "abc123..."  # Hash of source PDF
      equipment:
        status: "complete"
        last_updated: "2025-12-15"
        file_count: 12
      faction-rules:
        status: "complete"
        last_updated: "2025-12-10"
        file_count: 2
      firefight-ploys:
        status: "complete"
        last_updated: "2025-12-15"
        file_count: 6
      operatives:
        status: "complete"
        last_updated: "2025-12-15"
        file_count: 10
      strategy-ploys:
        status: "complete"
        last_updated: "2025-12-15"
        file_count: 8
    
    # Paths
    paths:
      processed: "processed/angels-of-death"
      output: "output/angels-of-death"
      archive: "archive/angels-of-death"
    
    # Metadata
    faction: "Imperium"
    game_version: "2024"
    notes: ""
    
  blooded:
    canonical_name: "Blooded"
    aliases:
      - "blooded"
      - "Chaos Cultists"
    card_types:
      datacards:
        status: "complete"
        last_updated: "2025-11-20"
        file_count: 6
    # ... similar structure
    faction: "Chaos"
    
  # ... more teams
```

## Features to Track

### 1. Team Identity
- **canonical_name**: Official display name
- **aliases**: List of name variations found in PDFs
- **faction**: Game faction (Imperium, Chaos, Xenos, etc.)

### 2. Card Type Status
For each card type:
- **status**: `complete`, `partial`, `missing`, `needs_update`
- **last_updated**: Date of last meaningful change
- **file_count**: Number of cards for this type
- **source_hash**: MD5/SHA hash of source PDF to detect actual changes

### 3. Path Information
- **processed**: Path to processed PDFs
- **output**: Path to output images
- **archive**: Path to archived files

### 4. Additional Metadata
- **game_version**: Track which game edition
- **notes**: Free-form notes about special cases
- **deprecated**: Flag if team is no longer used

## Implementation Steps

### Phase 1: Schema Definition
- [ ] Define YAML schema
- [ ] Create validation function
- [ ] Create default template

### Phase 2: Migration Script
- [ ] Create script to convert old format to new format
- [ ] Auto-populate data from existing files
- [ ] Calculate initial file counts
- [ ] Set initial last_updated dates from file system

### Phase 3: Update Detection
- [ ] Implement PDF hash calculation
- [ ] Store hashes in metadata
- [ ] Compare hashes on re-processing to detect actual changes
- [ ] Only update `last_updated` when content changes

### Phase 4: Metadata Writer
- [ ] Create function to update metadata after processing
- [ ] Update file counts automatically
- [ ] Update timestamps
- [ ] Update hashes

### Phase 5: Metadata Reader
- [ ] Create helper class to read metadata
- [ ] Provide convenient access methods
- [ ] Integrate with Team class (from Feature 02)

### Phase 6: Reporting
- [ ] Create script to generate status report
- [ ] Show which teams need updates
- [ ] Show missing card types
- [ ] Show last update dates

## Usage Examples

### Reading Metadata
```python
from src.utils.metadata import TeamMetadata

metadata = TeamMetadata.load()
team = metadata.get_team("angels-of-death")

print(team.canonical_name)  # "Angels of Death"
print(team.has_card_type("datacards"))  # True
print(team.get_last_updated("datacards"))  # "2025-12-15"
print(team.needs_update("datacards", current_hash))  # False
```

### Updating Metadata
```python
from src.utils.metadata import TeamMetadata

metadata = TeamMetadata.load()
metadata.update_card_type(
    team="angels-of-death",
    card_type="datacards",
    file_count=8,
    source_hash="abc123..."
)
metadata.save()
```

### Status Report
```bash
python script/generate_status_report.py

# Output:
=== Team Status Report ===
Angels of Death:
  ✓ datacards (8 cards, updated 2025-12-15)
  ✓ equipment (12 cards, updated 2025-12-15)
  ✓ faction-rules (2 cards, updated 2025-12-10)
  ...

Blooded:
  ✓ datacards (6 cards, updated 2025-11-20)
  ⚠ equipment (missing)
  ...
```

## Change Detection Logic

```python
def needs_update(pdf_path: Path, team: str, card_type: str) -> bool:
    """
    Determine if a PDF represents new content.
    """
    current_hash = calculate_hash(pdf_path)
    stored_hash = metadata.get_hash(team, card_type)
    
    if stored_hash is None:
        return True  # New card type
    
    return current_hash != stored_hash
```

## Questions to Answer

1. **Update Tracking**: Should we track:
   - File modification dates?
   - Git commit dates?
   - Processing dates?
   - All of the above?

2. **Version Tracking**: Do teams have version numbers we should track?

3. **Faction List**: What are all the possible factions?
   - Imperium
   - Chaos
   - Xenos
   - Others?

4. **Card Status**: Are these statuses sufficient?
   - complete
   - partial
   - missing
   - needs_update

5. **Hash Algorithm**: MD5, SHA-1, or SHA-256?

## Benefits
- Track which teams are up-to-date
- Detect actual content changes (not just reprocessing)
- Better organization and documentation
- Foundation for automated updates
- Easy status reporting

## Estimated Effort
- **Complexity**: Medium
- **Time**: 4-6 hours
- **Risk**: Low

## Dependencies
- Works best after Feature 02 (Code Refactoring)
- Independent of other features
