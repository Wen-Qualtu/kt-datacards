# Feature 01: Project Restructuring

## Status
✅ Complete (January 10, 2026)

**Note**: Configuration was later moved from `script/config/` to root `config/` (see Feature 02) for cleaner separation of input data and configuration.

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
│       ├── strategy-ploys/
│       └── datacards-urls.csv  # Generated URL mapping
├── script/                     # Python scripts
├── config/                     # Configuration files
│   └── team-mapping.yaml
└── docs/                       # Documentation
```

## Migration Steps

### Phase 1: Create New Structure
- [x] Create `archive/` folder at root
- [x] Create `processed/` folder at root
- [x] Create `config/` folder at root (moved from script/config in Feature 02)
- [x] Keep `output/` exactly as-is (TTS dependency)

### Phase 2: Move Existing Files
- [x] Move `input/_archive/*` → `archive/*` (8 teams)
- [x] Move `input/{teamname}/` folders → `processed/{teamname}/` (13 teams)
- [x] Move `team-mapping.yaml` → `config/team-name-mapping.yaml` (later moved from script/config)
- [x] Flattened `input/_raw/` to just `input/`
- [x] Moved `input/config/` → `config/` (Feature 02)

### Phase 3: Update Scripts
- [x] Update `process_raw_pdfs.py` to output to `processed/` instead of `input/`
- [x] Update `extract_pages.py` to read from `processed/` instead of `input/`
- [x] Update all path references in scripts
- [x] Update team-mapping path references
- [x] Update archive logic to use new `archive/` folder

### Phase 4: Cleanup
- [x] Remove `input/_archive/` (empty)
- [x] Rename `input/_raw/` to just `input/`
- [x] Test full pipeline with new structure
- [x] Update README.md with new structure

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
- [x] Place test PDF in `input/`
- [x] Run processing pipeline
- [x] Verify files appear in `processed/{teamname}/`
- [x] Verify PNGs appear in `output/{teamname}/{cardtype}/`
- [x] Verify URLs in CSV are correct
- [x] Test archive functionality

## Rollback Plan
If issues arise:
1. Keep backup of original structure
2. Revert git changes
3. Move files back manually if needed

## Estimated Effort
- **Complexity**: Medium
- **Time**: 2-3 hours
- **Risk**: Low (internal changes only)

---

## Implementation Summary

### Completed Changes

**Folders Created:**
- ✅ `archive/` - Contains archived PDFs (optional)
- ✅ `processed/` - Contains team folders with organized PDFs (flat structure)
- ✅ `config/` - Configuration files at root (moved from script/config in Feature 02)
- ✅ `config/card-backside/default/` - Default backside images
- ✅ `config/card-backside/team/` - Team-specific custom backsides

**File Migrations:**
- ✅ `input/_archive/*` → `archive/*`
- ✅ `input/{teamname}/` → `processed/{teamname}/`
- ✅ `input/_raw/*` → `input/*` (flattened, now processes recursively)
- ✅ `team-mapping.yaml` → `config/team-name-mapping.yaml` (initially script/config)
- ✅ Default backside images → `config/card-backside/default/`
- ✅ URL CSV → `output/datacards-urls.csv` (Feature 02)

**Script Updates:**
- ✅ Complete refactor to modular architecture (Feature 02)
- ✅ New `script/run_pipeline.py` - Main CLI entry point
- ✅ `script/src/` - Modular source code (models, processors, generators)
- ✅ Updated all path references to use config at root
- ✅ Recursive input/ processing with no exclusions needed

**New Features Added:**
- ✅ Team-specific custom backsides support
- ✅ Recursive subdirectory processing in input/
- ✅ Clean separation of config from input data
- ✅ Priority logic: team-specific → default fallback
- ✅ Organized backside configuration: `config/card-backside/default` and `config/card-backside/team`

### Verification

**Structure Verified:**
```
✅ archive/ exists with 8 team folders
✅ processed/ exists with 13 team folders  
✅ script/config/ exists with team-mapping.yaml
✅ script/config/card-backside/default/ with default images
✅ script/config/card-backside/team/ ready for custom backsides
✅ input/ is clean and flat
✅ output/ unchanged (TTS safe!)
```

**No Breaking Changes:**
- ✅ TTS card URLs still work (output/ unchanged)
- ✅ GitHub structure compatible
- ✅ All scripts updated and tested
- ✅ CSV generation works with existing structure

### Workflow After Restructuring

1. **Add New Cards**: Place PDF in `input/` → Run `process_raw_pdfs.py` → Organized in `processed/`, archived in `archive/`
2. **Extract Images**: Run `extract_pages.py` → Reads from `processed/` → Outputs to `output/`
3. **Add Backsides**: Run `add_default_backsides.py` → Uses `config/card-backside/default/` or `config/card-backside/team/{team}/`
4. **Generate URLs**: Run `generate_urls.py` → Creates CSV for TTS import

### Custom Backsides Feature

**Implementation:**
- Custom backsides stored in `script/config/card-backside/team/{teamname}/`
- Files: `backside-portrait.jpg` (for equipment/ploys) and `backside-landscape.jpg` (for datacards)
- Priority: Check team folder first, fall back to defaults if not found
- Example added: `angels-of-death-backside-landscape.jpg`

**Benefits:**
- Each team can have themed backsides matching faction colors
- Optional: teams without custom backsides use defaults
- Easy to add/remove without script changes
- Professional look for tournament play

**Documentation:**
- Added to `script/config/card-backside/team/README.md`
- Updated DEVELOPMENT.md with folder structure
- Complete usage examples and image requirements
