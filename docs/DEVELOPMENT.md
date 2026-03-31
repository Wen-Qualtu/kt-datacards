# Development Rules & Guidelines

> **Purpose**: This document provides essential context and rules for AI agents working on the Kill Team Datacards project. It focuses on current architecture, coding standards, and critical constraints.

## 🎯 Project Overview

### What Is This Project?

Automated pipelines for processing **Warhammer 40,000: Kill Team** datacards into **Tabletop Simulator (TTS)** compatible formats from two sources:

1. **kt-app Pipeline**: Processes PDFs exported from the Kill Team mobile app
2. **warcom Pipeline**: Processes official PDFs from Warhammer Community website

**Tech Stack:**
- Python 3.11+ with Poetry dependency management
- PyMuPDF (fitz) for PDF processing
- Pillow & OpenCV for image manipulation
- YAML for configuration
- Git for version control
- GitHub raw URLs for hosting card images

---

## 🚨 Critical Constraints

### 1. Never Break TTS References
**The `output/` folder structure is IMMUTABLE.**
- TTS cards reference exact GitHub raw URLs
- ✅ DO: Add new files or update existing images
- ❌ DON'T: Rename folders, restructure paths, or move files in `output/`

### 2. Logging Standard
**All pipeline scripts MUST use Python's logging module exclusively.**
- ✅ DO: `logging.info()`, `logging.warning()`, `logging.error()`, `logging.debug()`
- ❌ DON'T: `print()` statements
- Configuration: Use `--log-level` flag (DEBUG, INFO, WARNING, ERROR)
- Format: `'%(levelname)s: %(message)s'`

### 3. Data Quality Over Speed
- Accuracy is paramount (especially for stats extraction)
- Better to warn/error than produce wrong data
- Manual review is acceptable when uncertain
- Processing can take hours - that's fine

---

## 📁 Repository Structure

```
kt-datacards/
├── config/
│   ├── team-config.yaml           # Team metadata, faction assignments
│   ├── team-guids.json            # TTS GUID assignments per team
│   ├── defaults/                   # Default assets for all teams
│   │   ├── box/                   # Default cardbox mesh/textures
│   │   ├── card-backside/         # Default card back images
│   │   ├── tts-image/             # Default TTS object images
│   │   ├── tts-script/            # Default Lua scripts
│   │   └── tts-token/             # Default token meshes/scripts
│   ├── pipelines/                  # Pipeline-specific config
│   │   └── warcom/                # Warcom scraping patterns
│   └── teams/{teamname}/          # Team-specific overrides
├── dev/                            # Development/debugging scripts
│   └── examples/                   # Example scripts
├── docs/
│   └── DEVELOPMENT.md             # This file - AI agent onboarding
├── input/                          # Raw unprocessed files (kt-app pipeline)
├── layers/
│   ├── archive/                    # Source PDFs archived by team
│   ├── kt-app/                     # kt-app pipeline intermediate data
│   └── warcom/                     # warcom pipeline intermediate data
│       ├── staging/                # Downloaded PDFs awaiting processing
│       └── extracted/{teamname}/  # Extracted cards and tokens
├── output/                         # ⚠️ IMMUTABLE - TTS references these
│   ├── .tts-metadata.json         # Change detection metadata
│   └── {teamname}/
│       ├── cards/{cardtype}/      # Card images organized by type
│       ├── textures/               # Team box textures
│       ├── tokens/                 # Processed token images
│       └── tts/                    # TTS object JSON files
├── output_v2/                      # Faction-organized output structure
│   ├── datacards-urls.json        # All card URLs by team
│   ├── metadata.yaml              # Team metadata
│   ├── tts-card-boxes.json        # Cardbox objects by team
│   ├── tts-manager.json           # TTS manager object
│   ├── tts-metadata.json          # TTS generation metadata
│   ├── chaos/{teamname}/          # Chaos faction teams
│   ├── imperium/{teamname}/       # Imperium faction teams
│   └── xenos/{teamname}/          # Xenos faction teams
├── pipelines/
│   ├── kt-app/                     # Mobile app PDF processing
│   │   ├── docs/                   # kt-app specific documentation
│   │   └── *.py                    # Pipeline scripts
│   └── warcom/                     # Warhammer Community PDF processing
│       ├── docs/                   # warcom specific documentation
│       ├── steps/                  # Pipeline step implementations
│       ├── pdf_process_pipeline.py # Main orchestrator
│       └── README.md              # warcom pipeline overview
├── tools/                          # Utility scripts and tools
├── pyproject.toml                 # Poetry dependencies
└── README.md                      # Project overview
```

---

## 🏗️ Architecture Principles

### Separation of Concerns
- **Models**: Data structures (Team, Card, Token)
- **Processors**: Business logic (extraction, classification)
- **Generators**: Output creation (TTS objects, URLs)
- **Utils**: Shared utilities (file operations, logging)

### Dependency Injection
- Pass dependencies explicitly via parameters
- Don't hardcode paths - use config or Path() relative to workspace root
- Example: `workspace_root = Path(__file__).parent.parent.parent`

### Error Handling
- Validate early, fail fast
- Log errors with full context
- Don't silently ignore errors
- Provide actionable error messages

---

## 📝 Naming Conventions

### Python Code

#### Files & Modules
- Use `snake_case`: `pdf_processor.py`, `extract_tokens.py`

#### Classes
- Use `PascalCase`: `TeamMetadata`, `PDFProcessor`, `TTSCard`

#### Functions & Methods
- Use `snake_case`: `process_raw_pdfs()`, `extract_text()`, `build_tts_object()`
- Verb-based names describing the action

#### Variables
- Use `snake_case`: `team_name`, `output_dir`, `card_type`
- **Rule**: Prefer full words over abbreviations
  - ✅ GOOD: `team_identifier`, `configuration`, `card_type_class`
  - ❌ BAD: `team_id`, `cfg`, `cls`
- Boolean variables: `is_*`, `has_*`, `should_*` prefix

#### Constants
- Use `UPPER_SNAKE_CASE`: `DEFAULT_DPI`, `MAX_WORKERS`, `TARGET_SIZE`

### Configuration (YAML)

#### Team Names (Canonical)
- Use `kebab-case`: `angels-of-death`, `corsair-voidscarred`
- Always lowercase

#### Card Types
- Use `kebab-case`: `datacards`, `firefight-ploys`, `faction-rules`
- Match output folder names exactly

#### Metadata Keys
- Use `snake_case`: `last_updated`, `file_count`, `content_hash`

---

## ⚙️ Configuration System

### Team Configuration (`config/team-config.yaml`)

Central configuration for all teams with metadata and paths:

```yaml
teams:
  hearthkyn-salvagers:
    canonical_name: "Hearthkyn Salvagers"
    faction: "xenos"              # imperium, chaos, or xenos
    army: "leagues-of-votann"     # Specific army within faction
    aliases:
      - "hearthkyn salvagers"
      - "salvagers"
    tokens:                        # Optional: token shape configuration
      - name: "Void Armor"
        shape: "round"
        type: "token"
      - name: "Breach"
        shape: "octagon"
        type: "marker"
```
---

## 🔄 Pipeline Architectures

### kt-app Pipeline
**Purpose**: Process PDFs exported from Kill Team mobile app

**Characteristics:**
- PDFs have UUID filenames
- Contains all team datacards in one or more PDFs
- Requires content analysis to identify team and card types
- Full documentation in `pipelines/kt-app/docs/`

### warcom Pipeline
**Purpose**: Process official PDFs from Warhammer Community

**Characteristics:**
- Standardized PDF structure (4 cards per page in grid)
- Includes token guide cards along with datacards
- Uses template matching for extraction
- Cards extracted with team prefixes
- Full documentation in `pipelines/warcom/docs/` and `pipelines/warcom/README.md`

**Key Steps:**
1. Scrape and download PDFs from warcom website
2. Extract individual cards using template matching
3. Classify cards by type based on text content
4. Process tokens (step 4 - token name matching and transparency)
5. Generate TTS objects (step 5)

---

## 🛠️ Common Development Tasks

### Running Pipelines

**kt-app Pipeline:**
```bash
poetry run python pipelines/kt-app/run_pipeline.py --step all
poetry run python pipelines/kt-app/run_pipeline.py --step extract --teams kasrkin
```

**warcom Pipeline:**
```bash
# Full pipeline (steps 1-3)
poetry run python pipelines/warcom/pdf_process_pipeline.py --all

# Individual steps
poetry run python pipelines/warcom/pdf_process_pipeline.py --step 2
poetry run python pipelines/warcom/pdf_process_pipeline.py --step 3 --teams kommandos

# TTS object generation
poetry run python pipelines/warcom/steps/5_generate_tts_objects.py --teams battleclade --force
```

### Installing Dependencies
```bash
poetry install                    # Install all dependencies
poetry add {package}              # Add new package
```

### Code Quality
```bash
poetry run black .                # Format code
poetry run flake8                 # Lint code (if configured)
```

---

## ⚠️ Common Pitfalls

### Don't Modify Output Structure
- ❌ Renaming teams in `output/`
- ❌ Changing folder hierarchy in `output/`
- ❌ Moving files between folders in `output/`

### Don't Hardcode Paths
- ❌ `output_dir = "c:/project/output"`  
- ✅ `output_dir = workspace_root / "output"`
- ✅ Use `pathlib.Path` for all path operations

### Don't Use Print Statements
- ❌ `print("Processing team...")`
- ✅ `logger.info("Processing team...")`

### Don't Ignore Errors
- ❌ Silent failures, empty except blocks
- ✅ Log errors with context, fail fast

---

## 📚 Documentation Structure

- **`docs/DEVELOPMENT.md`** (this file): AI agent onboarding, coding standards, critical rules
- **`pipelines/kt-app/docs/`**: kt-app pipeline specific documentation
- **`pipelines/warcom/docs/`**: warcom pipeline specific documentation
- **`pipelines/warcom/README.md`**: warcom pipeline overview and usage

---

## 🎯 Quick Reference

**Before making changes:**
- Read the relevant pipeline docs (kt-app or warcom)
- Never modify `output/` structure (TTS URLs are hardcoded)
- Use logging module exclusively (no print statements)
- Use `pathlib.Path` for all file operations
- Prefer explicit variable names over abbreviations

**When stuck:**
- Check pipeline-specific documentation
- Look at existing code patterns in the same pipeline
- Ask about design decisions rather than assuming

---

**Last Updated**: February 16, 2026  
**Review**: Update when architectural changes are made
