# Output V2 Format

## Overview

The V2 output format provides an enhanced, hierarchical organization of Kill Team datacards with better metadata support. This format **does not replace** the original `output/` folder structure - both coexist for backwards compatibility.

## Directory Structure

```
output/v2/
├── {faction}/
│   └── {army}/
│       └── {teamname}/
│           ├── datacards/
│           ├── equipment/
│           ├── faction-rules/
│           ├── firefight-ploys/
│           ├── operative-selection/     # Renamed from "operatives"
│           └── strategy-ploys/
└── datacards-urls.csv
```

### Example Structure

```
output/v2/
├── imperium/
│   ├── adeptus-mechanicus/
│   │   └── battleclade/
│   │       ├── datacards/
│   │       │   ├── battleclade-auto-proxy-servitor_front.jpg
│   │       │   ├── battleclade-auto-proxy-servitor_back.jpg
│   │       │   └── ...
│   │       ├── equipment/
│   │       ├── faction-rules/
│   │       ├── firefight-ploys/
│   │       ├── operative-selection/
│   │       └── strategy-ploys/
│   └── space-marines/
│       └── deathwatch/
│           └── ...
└── xenos/
    ├── leagues-of-votann/
    │   ├── farstalker/
    │   └── hearthkyn-salvagers/
    └── orks/
        └── wrecka-krew/
```

## Key Differences from V1

### 1. Hierarchical Organization
- **V1**: Flat structure `output/{teamname}/{cardtype}/`
- **V2**: Hierarchical `output/v2/{faction}/{army}/{teamname}/{cardtype}/`

### 2. Card Type Naming
- **V1**: Uses `operatives/` folder
- **V2**: Uses `operative-selection/` folder (more descriptive)

### 3. Card Filenames
- **V1**: Some cards have team prefix, some don't
- **V2**: ALL cards are prefixed with team name for clarity
  - Example: `trooper-gunner_front.jpg` → `kasrkin-trooper-gunner_front.jpg`

### 4. Metadata Location
- **V1**: `output-metadata.yaml` at project root
- **V2**: `output/metadata.yaml` within output directory

### 5. URL CSV Format
- **V1**: `team,type,name,url`
- **V2**: `faction,army,team,type,name,url` (includes hierarchy)

## Faction & Army Configuration

Teams are configured with faction and army metadata in `config/team-name-mapping.yaml`:

```yaml
team_metadata:
  hearthkyn-salvagers:
    canonical_name: "Hearthkyn Salvagers"
    faction: "xenos"                # imperium, chaos, or xenos
    army: "leagues-of-votann"       # Specific army
```

### Supported Factions
- **imperium** - Imperial forces (Space Marines, Astra Militarum, Adeptus Mechanicus, etc.)
- **chaos** - Chaos forces
- **xenos** - Alien forces (Orks, Leagues of Votann, Tau, etc.)

### Uncategorized Teams
Teams without faction/army metadata are placed in `output/v2/uncategorized/` until configured.

## URL CSV Format

The V2 URLs CSV includes full hierarchy information:

```csv
faction,army,team,type,name,url
imperium,adeptus-mechanicus,battleclade,datacards,battleclade-auto-proxy-servitor_front,https://raw.githubusercontent.com/.../v2/imperium/adeptus-mechanicus/battleclade/datacards/battleclade-auto-proxy-servitor_front.jpg
xenos,leagues-of-votann,hearthkyn-salvagers,operative-selection,hearthkyn-salvagers-operatives_front,https://raw.githubusercontent.com/.../v2/xenos/leagues-of-votann/hearthkyn-salvagers/operative-selection/hearthkyn-salvagers-operatives_front.jpg
```

## Benefits of V2 Format

1. **Better Organization**: Hierarchical structure makes it easier to find teams by faction/army
2. **Clear Naming**: All cards prefixed with team name prevents confusion
3. **Consistency**: `operative-selection` is more descriptive than `operatives`
4. **Enhanced Metadata**: Includes faction/army information in URLs and structure
5. **Future-Proof**: Easier to extend with additional organizational levels
6. **Backwards Compatible**: Original v1 format remains untouched for TTS compatibility

## Migration Notes

- **No Migration Required**: V2 is generated alongside V1
- **Both Formats Maintained**: Pipeline generates both automatically
- **TTS Users**: Continue using v1 format (unchanged URLs)
- **New Integrations**: Can use v2 format for better organization

## Adding New Teams

1. Add team metadata to `config/team-name-mapping.yaml`:
   ```yaml
   team_metadata:
     new-team:
       canonical_name: "New Team"
       faction: "imperium"
       army: "space-marines"
   ```

2. Process team through pipeline (both v1 and v2 are generated automatically)

3. Output appears in:
   - `output/new-team/` (v1 - flat structure)
   - `output/v2/imperium/space-marines/new-team/` (v2 - hierarchical)

## Technical Details

### Generation Process
1. V1 output is generated first (preserves existing workflow)
2. V2 processor reads from v1 output
3. Files are copied to v2 hierarchy with team-prefixed names
4. Separate URL CSV is generated for v2

### File Copying Strategy
- Files are copied (not moved) from v1 to v2
- Team prefix is added during copy if not present
- `operatives/` folder contents go to `operative-selection/`

### Performance
- V2 generation adds minimal overhead (~5-10% of total pipeline time)
- Files are only copied, not reprocessed
- Operates on existing v1 output

## Troubleshooting

### Team in `uncategorized/` folder
**Problem**: Team appears under `output/v2/uncategorized/{teamname}/`

**Solution**: Add faction/army metadata to `config/team-name-mapping.yaml`

### Card names missing team prefix
**Problem**: Some cards in v2 don't have team prefix

**Solution**: This can happen if the card name already starts with the team name. The prefix logic detects this and avoids duplication.

### V2 not generated
**Problem**: V1 output exists but v2 is empty

**Solution**: Run the full pipeline - v2 generation requires v1 output to exist first.

## Future Enhancements

Potential future improvements for v2 format:
- Additional hierarchy levels (subfaction, killteam type)
- Enhanced metadata per card (points, restrictions, etc.)
- Multilingual support
- Version tracking per team
