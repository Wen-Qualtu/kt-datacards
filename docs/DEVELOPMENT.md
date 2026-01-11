# Development Rules & Guidelines

## 🎯 Project Overview

### What Is This Project?

This is an automated pipeline for processing **Warhammer 40,000: Kill Team datacards** exported from the mobile app into a format usable in **Tabletop Simulator (TTS)**.

**The Challenge:**
- Kill Team mobile app exports PDFs with UUID filenames
- PDFs contain multiple card types (datacards, equipment, ploys, faction rules, operatives, strategy)
- TTS needs individual card images with specific URLs
- Users want to quickly get new teams into TTS without manual image extraction

**The Solution:**
This pipeline automates the entire workflow:
1. **Identify** - Analyze PDF content to determine team name and card type
2. **Extract** - Split PDFs into individual card images (front/back detection)
3. **Organize** - Store in TTS-compatible folder structure
4. **Backsides** - Add default or team-specific card backsides
5. **Generate URLs** - Create CSV mapping for TTS deck builder

**Key Constraints:**
- ⚠️ **IMMUTABLE output/ structure** - TTS cards reference exact paths via GitHub raw URLs
- 🎯 **Accuracy over speed** - Wrong card data breaks gameplay
- 🔄 **Reproducible** - Anyone should be able to run the pipeline and get same results

**Current Status:**
- ✅ Feature 00: Poetry + Task setup (complete)
- ✅ Feature 01: Project restructuring (complete)
- ✅ Feature 02: Code refactoring with clean architecture (complete)
- 🔴 Feature 03: Enhanced metadata (not started)
- 🔴 Feature 04: Stats extraction with OCR (not started)
- 🔴 Feature 05: Parameterized execution (partially complete - CLI exists)

**Tech Stack:**
- Python 3.11+ with Poetry dependency management
- PyMuPDF (fitz) for PDF processing
- Pillow for image manipulation
- pytesseract for OCR (future)
- Task for workflow automation
- Git for version control
- GitHub for hosting output images (via raw URLs)

**Users:**
- Kill Team players who want their cards in TTS
- Primary user: Wen (project owner, manages team datacards)

---

## 📋 Core Principles

### 1. **Feature-First Development Workflow**
**CRITICAL**: All new features must follow this workflow to maintain control and organization:

1. **Create Feature Document First**
   - Use naming convention: `docs/{XX}-{shortname}.md`
   - Number sequentially (00, 01, 02, etc.)
   - Document idea, steps, requirements, and acceptance criteria
   
2. **Ask Before Implementation**
   - After creating the feature document, **STOP**
   - Ask: "Should we implement this now or later?"
   - Respect the user's prioritization and workflow preferences
   
3. **User Controls the Queue**
   - User decides which features to tackle and when
   - Features can be deferred, reordered, or modified
   - Implementation happens only with explicit approval

4. **Confirm Before Closing**
   - After completing implementation, **STOP**
   - Explain what was accomplished and show results
   - Ask: "Is this sufficient to close the feature?"
   - Don't immediately suggest moving to the next feature
   - Wait for user confirmation before marking feature complete

**Example:**
```
❌ BAD: "I'll add team-specific backsides" → [implements immediately]
✅ GOOD: [Creates docs/06-team-backsides.md] → "Feature documented. Implement now or later?"

❌ BAD: [Completes feature] → "Done! Ready for Feature 02?"
✅ GOOD: [Completes feature] → "Here's what I implemented: [summary]. Is this sufficient to close Feature 00?"
```

### 2. **Never Break TTS References**
**CRITICAL**: The `output/` folder structure is IMMUTABLE. TTS cards reference these exact paths.
- ✅ DO: Keep `output/{teamname}/{cardtype}/` structure exactly as-is
- ❌ DON'T: Rename, restructure, or move anything in `output/`
- 💡 Future: Use `output/v2/` for new structures while keeping `output/` for backwards compatibility

### 3. **Git as Source of Truth**
- All changes are tracked in git
- No manual version numbers in files
- Use git history for version tracking
- Commit frequently with clear messages

### 4. **Feature Branch Workflow**
**CRITICAL**: No direct commits to main branch
- ✅ DO: Create a feature branch for each feature
- ✅ DO: Name branch after the feature (e.g., `feature-03-enhanced-metadata`)
- ✅ DO: Work on the branch until feature is complete
- ✅ DO: Merge to main when feature is tested and approved
- ❌ DON'T: Commit directly to main
- 💡 Benefits: Multiple features in parallel, easy rollback, cleaner history

**Example workflow:**
```bash
git checkout -b feature-03-enhanced-metadata
# ... work on feature ...
git add -A
git commit -m "feat: add faction metadata to teams"
# ... more commits ...
git checkout main
git merge feature-03-enhanced-metadata
git branch -d feature-03-enhanced-metadata
```

### 4. **Reproducibility Across Machines**
- Use Poetry for dependency management
- Lock dependencies with `poetry.lock`
- Use Task for consistent script execution
- Virtual environments for isolation

### 5. **Quality Over Speed**
- Accuracy is paramount (especially for stats extraction)
- Better to show warnings/errors than wrong data
- Manual review is acceptable when accuracy is uncertain
- Don't rush processing - it's fine if it takes hours

---

## 📁 Folder Structure Rules

### Current Structure (After Restructuring)
```
kt-datacards/
├── input/                      # Raw unprocessed files (any structure allowed)
│   └── *.pdf                   # Process all PDFs recursively
├── config/                     # Configuration files
│   ├── team-name-mapping.yaml
│   └── card-backside/
│       ├── default/            # Default backside images
│       └── team/               # Team-specific custom backsides
├── processed/                  # Intermediate processing stage
│   └── {teamname}/             # Flat structure by team
├── output/                     # ⚠️ IMMUTABLE - TTS references these paths
│   ├── {teamname}/
│   │   ├── datacards/
│   │   ├── equipment/
│   │   ├── faction-rules/
│   │   ├── firefight-ploys/
│   │   ├── operatives/
│   │   └── strategy-ploys/
│   └── datacards-urls.csv      # Generated URL mapping
├── archive/                    # Archived processed files (optional)
│   └── {teamname}/
├── script/
│   ├── src/                    # Source code
│   ├── scripts/                # Individual step scripts
│   ├── tests/                  # Test scripts
│   ├── run_pipeline.py         # Main entry point
│   └── README.md               # Script documentation
└── docs/                       # Feature documentation
```

### Folder Rules

#### `input/`
- Process all PDFs recursively (including subfolders)
- No specific structure required
- Files are moved after processing
- Keep it flexible for user convenience

#### `archive/`
- Keep files forever (safe to accumulate)
- Organized by team name
- GUIDs linked to source PDFs (overwrite on reprocessing)
- Storage growth is acceptable

#### `processed/`
- Flat structure by team: `{teamname}/`
- Example: `kasrkin/`, `hearthkyn-salvager/`
- Contains identified and renamed PDFs
- Note: Future hierarchical structure (faction/army) deferred to Feature 03

#### `output/` ⚠️
- **NEVER change structure**
- Flat team structure: `{teamname}/{cardtype}/`
- TTS cards reference these exact paths
- Future: Create `output/v2/` for new structures

#### `config/`
- All configuration files here
- `team-name-mapping.yaml` for team name normalization
- `settings.py` for application config (future)
- `card-backside/default/` for default backside images
- `card-backside/team/{teamname}/` for custom team backsides
- Keep configs in git (except secrets)

---

## 🏷️ Naming Conventions

### File Names

#### Raw Input Files
- **Accept any filename** - Pipeline identifies content, not based on filename
- Mobile app exports use GUIDs (e.g., `05ba2863-8395-4b11-8df9-e67b70feebde.pdf`)
- Manual exports may use descriptive names (e.g., `kasrkin-datacards.pdf`)
- No specific naming required - pipeline handles all cases

#### Processed Files
- Pattern: `{team-name}_{card-type}.pdf`
- Example: `kasrkin_datacards.pdf`
- Use kebab-case for team names
- Use kebab-case for card types

#### Output Images
- Pattern: `{card-name}_{side}.png`
- Example: `assault-intercessor-grenadier_front.png`
- Example: `assault-intercessor-grenadier_back.png`
- Use kebab-case for card names
- Sides: `_front` and `_back`

### Code Naming

#### Python Files
- Use snake_case: `pdf_processor.py`
- Descriptive names: `extract_pages.py`, `generate_urls.py`

#### Classes
- Use PascalCase: `TeamMetadata`, `PDFProcessor`
- Noun-based names
- Clear single responsibility

#### Functions/Methods
- Use snake_case: `process_raw_pdfs()`, `extract_text()`
- Verb-based names
- Clear action description

#### Variables
- Use snake_case: `team_name`, `output_dir`
- Descriptive, not abbreviated
- Boolean variables: `is_`, `has_`, `should_` prefix
- **Exception**: Python convention parameters (`self` for instance methods, `card_type_class` for @classmethod instead of `cls`)
- **Rule**: Prefer full words over abbreviations - you type once but read many times
  - ✅ GOOD: `team_identifier`, `card_type_class`, `configuration`
  - ❌ BAD: `team_id`, `cls`, `cfg`
  - Clarity trumps brevity

#### Constants
- Use UPPER_SNAKE_CASE: `DEFAULT_DPI`, `MAX_WORKERS`
- Defined at module level
- Grouped logically

### YAML/Config Naming

#### Team Names (Canonical)
- Use kebab-case: `angels-of-death`
- Lowercase only
- Hyphens for spaces

#### Card Types
- Use kebab-case: `datacards`, `firefight-ploys`
- Lowercase only
- Match output folder names exactly

#### Metadata Keys
- Use snake_case: `last_updated`, `file_count`
- Descriptive keys
- Consistent across all YAML files

---

## 🏗️ Architecture Principles

### Separation of Concerns
- **Models**: Data structures (`Team`, `Datacard`)
- **Processors**: Business logic (`PDFProcessor`, `TextExtractor`)
- **Generators**: Output creation (`URLGenerator`)
- **Utils**: Shared utilities (`file_utils`, `logger`)

### Single Responsibility
- Each class/function does ONE thing well
- Easy to test, easy to understand
- Easy to modify without breaking others

### Dependency Injection
- Pass dependencies explicitly
- Don't hardcode paths in classes
- Use config for settings

### Error Handling
- Validate early, fail fast
- Clear error messages
- Log errors with context
- Don't silently ignore errors

---

## 🔍 Data Quality Rules

### Stats Extraction
- **100% accuracy required** - no guessing
- Better to show warning than wrong data
- Flag uncertain extractions for manual review
- Validate against expected patterns

### Text Extraction
- OCR can be imperfect - validate results
- Cross-reference with known patterns
- Allow manual correction workflow
- Document OCR challenges per card type

### Metadata Tracking
- Use content hashes to detect real changes
- Don't update timestamps on reprocessing unchanged files
- Track processing dates separately from update dates
- Validate metadata against schema

---

## 🎯 Processing Workflow Rules

### Default Behavior
1. Check CLI arguments
2. If no CLI args, check config file
3. If no config, process all teams
4. Always process recursively in `input/`

### Team Filtering
- Validate team names against team-mapping
- Show clear error for unknown teams
- Support comma-separated lists
- Support "all" keyword

### Change Detection
- Use content hash comparison
- Only process if content changed
- Support `--force` flag to override
- Log whether processing or skipping

### Pipeline Steps
- Steps: `process`, `extract`, `backside`, `urls`
- Each step can run independently
- Support selective execution
- Clear logging for each step

---

## 🗺️ Team Mapping Structure

### Hierarchical Organization
```yaml
teams:
  hearthkyn-salvagers:
    canonical_name: "Hearthkyn Salvagers"
    faction: "xenos"                    # Top level
    army: "leagues-of-votann"           # Mid level
    aliases:
      - "hearthkyn salvagers"
      - "salvagers"
    card_types:
      datacards:
        present: true
        last_updated: "2025-12-15"
        file_count: 8
        source_hash: "abc123..."
    paths:
      processed: "processed/xenos/leagues-of-votann/hearthkyn-salvagers"
      output: "output/hearthkyn-salvagers"  # Keep flat for TTS
      archive: "archive/hearthkyn-salvagers"
```

### Factions
- `imperium` - Imperial forces
- `chaos` - Chaos forces
- `xenos` - Alien forces

### Card Types (Always Lowercase)
- `datacards` - Unit datacards
- `equipment` - Equipment cards
- `faction-rules` - Faction-specific rules
- `firefight-ploys` - Firefight tactical ploys
- `operatives` - Operative cards
- `strategy-ploys` - Strategic ploys

---

## 📊 Output Formats

### URL CSV Format
```csv
team,card_type,card_name,side,url
kasrkin,datacards,trooper-gunner,front,https://raw.githubusercontent.com/.../kasrkin/datacards/trooper-gunner_front.png
kasrkin,datacards,trooper-gunner,back,https://raw.githubusercontent.com/.../kasrkin/datacards/trooper-gunner_back.png
```

### Stats YAML Format (Datacards)
```yaml
teams:
  kasrkin:
    operatives:
      - id: "trooper-gunner"
        name: "Trooper Gunner"
        stats:
          movement: "6"
          apl: "2"
          save: "4+"
          wounds: "7"
        weapons:
          - name: "Hot-shot Lasgun"
            type: "ranged"
            attacks: "4"
            hit: "4+"
            damage:
              normal: "3"
              critical: "4"
              combined: "3/4"
            weapon_rules:
              - "Ceaseless"
              - "Hot"
        abilities:
          - name: "Marksman"
            description: "In the Roll Attack Dice step..."
```

### Stats CSV Format (Flat)
```csv
team,operative_id,operative_name,movement,apl,save,wounds,weapon_name,weapon_type,attacks,hit,dmg_normal,dmg_crit
kasrkin,trooper-gunner,Trooper Gunner,6,2,4+,7,Hot-shot Lasgun,ranged,4,4+,3,4
```

---

## 🔧 Development Workflow

### Setting Up New Machine
```bash
git clone <repo>
cd kt-datacards
task install          # Install all dependencies
task info            # Verify setup
```

### Daily Development
```bash
task format          # Format code before commit
task lint            # Check code quality
task test            # Run tests
git commit           # Commit changes
```

### Processing Cards
```bash
# Process everything
task all

# Process specific team
task process-team -- --teams kasrkin

# Dry run to preview
task process-team -- --teams kasrkin --dry-run

# Force reprocess
task process-team -- --teams kasrkin --force
```

### Adding New Team
1. Export PDFs from Kill Team app
2. Save to `input/` folder (any name/structure)
3. Run `task all`
4. Verify output in `output/{teamname}/`
5. Check URLs in `output/datacards-urls.csv`
6. Commit changes

---

## ⚠️ Common Pitfalls to Avoid

### 1. Don't Modify Output Structure
- ❌ Renaming teams in `output/`
- ❌ Changing folder structure in `output/`
- ❌ Moving files in `output/`
- ✅ Only add new files or update existing images

### 2. Don't Hardcode Paths
- ❌ `output_dir = "c:/project/output"`
- ✅ `output_dir = config.OUTPUT_DIR`
- ✅ Use pathlib.Path for all paths

### 3. Don't Ignore Errors
- ❌ Silent failures
- ❌ Continuing with partial data
- ✅ Log errors with context
- ✅ Fail fast with clear messages

### 4. Don't Guess at Stats
- ❌ Filling in missing values with defaults
- ❌ "Probably 3, that's common"
- ✅ Flag as uncertain
- ✅ Prompt for manual review

### 5. Don't Break Virtual Environment
- ❌ Installing packages with pip directly
- ✅ Use `poetry add {package}`
- ✅ Use `task install`

---

## 📝 Code Review Checklist

Before committing code, verify:

- [ ] Code follows naming conventions
- [ ] No hardcoded paths (use config)
- [ ] Errors are handled properly
- [ ] Logging is informative
- [ ] Tests are updated
- [ ] Documentation is updated
- [ ] `output/` structure is unchanged
- [ ] Works in virtual environment
- [ ] Formatted with Black
- [ ] Passes linting
- [ ] No sensitive data committed

---

## 🔮 Future Considerations

### Output v2 Structure
When ready to implement hierarchical output:
```
output/
├── {teamname}/          # Legacy structure (keep!)
└── v2/                  # New structure
    └── {faction}/
        └── {army}/
            └── {teamname}/
```

### TTS Scripting
Future feature to investigate:
- Automate TTS object creation
- Auto-update card URLs in TTS
- Would enable easier migrations

### Stats Validation
Future enhancements:
- Machine learning for OCR improvement
- Automated error correction
- Stats comparison between versions
- Web interface for browsing stats

---

## 📚 References

- [Poetry Documentation](https://python-poetry.org/docs/)
- [Task Documentation](https://taskfile.dev/)
- [Kill Team Official Rules](https://www.warhammer-community.com/kill-team/)
- Project Feature Docs: `docs/00-*.md` through `docs/05-*.md`

---

## ❓ Questions?

If you're unsure about something:
1. Check this document first
2. Check feature documents in `docs/`
3. Check existing code for patterns
4. Ask before making structural changes
5. When in doubt, don't break `output/`!

---

**Last Updated**: January 10, 2026
**Maintainer**: Project Team
**Review Schedule**: Update after each major feature implementation
