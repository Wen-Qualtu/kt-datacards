# Feature 01: Project Restructuring

## Status
🔴 Not Started

## Overview
Reorganize the folder structure to better represent the processing pipeline and separate concerns.

## Current Structure Problems
- `input/` serves multiple purposes (raw files, processed files, archives)
- Intermediate processing steps live in `input/{teamname}/` which is confusing
- No clear separation between pipeline stages
- `team-mapping.yaml` in root is not ideal for configuration

## Proposed New Structure

```
kt-datacards/
├── input/                      # Raw input files only
│   └── {guid}.pdf              # Unprocessed PDF exports
├── archive/                    # Historical/processed files
│   └── {teamname}/
│       └── {original-files}
├── processed/                  # Intermediate processing stage
│   └── {teamname}/
│       └── {renamed-pdfs}
├── output/                     # Final PNG outputs (DO NOT CHANGE - TTS references)
│   └── {teamname}/
│       ├── datacards/
│       ├── equipment/
│       ├── faction-rules/
│       ├── firefight-ploys/
│       ├── operatives/
│       └── strategy-ploys/
├── script/                     # Python scripts
│   ├── config/                 # Configuration files
│   │   └── team-mapping.yaml
│   └── ...
├── docs/                       # Documentation
└── datacards-urls.csv
```

## Migration Steps

### Phase 1: Create New Structure
- [ ] Create `archive/` folder at root
- [ ] Create `processed/` folder at root
- [ ] Create `script/config/` folder
- [ ] Keep `output/` exactly as-is (TTS dependency)

### Phase 2: Move Existing Files
- [ ] Move `input/_archive/*` → `archive/*`
- [ ] Move `input/{teamname}/` folders → `processed/{teamname}/`
- [ ] Move `team-mapping.yaml` → `script/config/team-mapping.yaml`
- [ ] Keep only `_raw/` in `input/` initially

### Phase 3: Update Scripts
- [ ] Update `process_raw_pdfs.py` to output to `processed/` instead of `input/`
- [ ] Update `extract_pages.py` to read from `processed/` instead of `input/`
- [ ] Update all path references in scripts
- [ ] Update team-mapping path references
- [ ] Update archive logic to use new `archive/` folder

### Phase 4: Cleanup
- [ ] Remove `input/_archive/` (empty)
- [ ] Rename `input/_raw/` to just `input/` (or keep _raw if preferred)
- [ ] Test full pipeline with new structure
- [ ] Update README.md with new structure

## Impact Analysis

### Breaking Changes
- Script paths will change (internal only)
- Team mapping location changes (internal only)
- Archive location changes (internal only)

### Non-Breaking
- `output/` structure remains identical (TTS safe)
- CSV URLs remain valid
- GitHub repository structure compatible

## Testing Checklist
- [ ] Place test PDF in `input/`
- [ ] Run processing pipeline
- [ ] Verify files appear in `processed/{teamname}/`
- [ ] Verify PNGs appear in `output/{teamname}/{cardtype}/`
- [ ] Verify URLs in CSV are correct
- [ ] Test archive functionality

## Rollback Plan
If issues arise:
1. Keep backup of original structure
2. Revert git changes
3. Move files back manually if needed

## Estimated Effort
- **Complexity**: Medium
- **Time**: 2-3 hours
- **Risk**: Low (internal changes only)
