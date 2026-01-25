# Refactoring Action Plan - Kill Team Datacards Pipeline

**Created:** January 25, 2026  
**Based on:** [REFACTORING-REVIEW.md](REFACTORING-REVIEW.md)  
**Status:** Ready for Implementation

---

## Overview

This document provides a step-by-step action plan to address the issues identified in the refactoring review. Each phase is designed to be completed independently with minimal risk to existing functionality.

---

## Phase 1: Foundation & Critical Fixes
**Estimated Time:** 1 day  
**Risk Level:** Low  
**Can Break TTS:** No

### Task 1.1: Create Central Configuration
**Priority:** 🔴 Critical  
**Files to Create:**
- `script/config.py`

**Implementation:**
```python
"""Central configuration for paths and settings."""
from pathlib import Path

# Project root - calculated once from this file's location
# config.py is in script/, so parent is project root
PROJECT_ROOT = Path(__file__).parent.parent

# Directory paths (derived from root)
CONFIG_DIR = PROJECT_ROOT / 'config'
INPUT_DIR = PROJECT_ROOT / 'input'
PROCESSED_DIR = PROJECT_ROOT / 'processed'
ARCHIVE_DIR = PROJECT_ROOT / 'archive'
OUTPUT_V2_DIR = PROJECT_ROOT / 'output_v2'
TTS_OBJECTS_DIR = PROJECT_ROOT / 'tts_objects'
METADATA_DIR = PROJECT_ROOT / 'metadata'

# Processing settings
DEFAULT_DPI = 300
DEFAULT_TOKEN_CANVAS_PX = 512

# URLs
GITHUB_BASE_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"
GITHUB_OUTPUT_V2_URL = f"{GITHUB_BASE_URL}/output_v2"
GITHUB_TTS_URL = f"{GITHUB_BASE_URL}/tts_objects"

# Team config
TEAM_CONFIG_PATH = CONFIG_DIR / 'team-config.yaml'
TEAM_GUIDS_PATH = CONFIG_DIR / 'team-guids.json'
```

**Files to Update:**
1. `run_pipeline.py` - Replace project_root calculation
2. `pipeline/pipeline.py` - Replace all Path('output_v2') with config
3. `managers.py` - Use OUTPUT_V2_DIR
4. All generator files - Use config paths

**Testing:**
- Run `python script/run_pipeline.py --step all --teams kasrkin`
- Verify all paths resolve correctly
- Check output files are in correct locations

---

### Task 1.2: Fix Logging - Remove Print Statements
**Priority:** 🔴 Critical  
**Files to Update:**
- `pipeline/image_extractor.py` (10+ print statements)
- `generators/objects/urls.py` (5+ print statements)

**Search & Replace Pattern:**
```python
# BEFORE
print(f"[DEBUG extract_from_pdf] Called for {team.name}...")
print(f"DEBUG: Collected {len(entries)} entries")

# AFTER
self.logger.debug(f"extract_from_pdf called for {team.name}...")
self.logger.debug(f"Collected {len(entries)} entries")
```

**Implementation Steps:**
1. Find all `print(` statements in script/ (exclude generated JSON/Lua)
2. Replace with appropriate logging level:
   - `[DEBUG ...]` → `self.logger.debug(...)`
   - Error messages → `self.logger.error(...)`
   - Status updates → `self.logger.info(...)`
3. Remove `[DEBUG]` prefix from messages

**Testing:**
- Run with `--verbose` flag - should see debug messages
- Run without flag - should NOT see debug messages
- Check log output is clean and structured

---

### Task 1.3: Consolidate URL Generation
**Priority:** 🔴 Critical  
**Goal:** Single source of truth for URL generation

**Current State (3 implementations):**
1. `generators/objects/urls.py` - URLGenerator class ⭐ KEEP THIS
2. `generators/metadata/urls.py` - Standalone script
3. `pipeline/v2_output_processor.py` - Duplicate logic

**Action Plan:**

**Step 1:** Keep and improve `generators/objects/urls.py`
- Move to `generators/urls.py` (remove objects/ nesting)
- Update to use `from config import OUTPUT_V2_DIR, GITHUB_OUTPUT_V2_URL`

**Step 2:** Update `pipeline/pipeline.py`
```python
# BEFORE
from .generators.url_generator import URLGenerator  # Wrong path

# AFTER  
from generators.urls import URLGenerator
```

**Step 3:** Simplify `generators/metadata/urls.py`
```python
"""CLI wrapper for URL generation"""
import sys
from pathlib import Path
from utils import setup_logger

# Import the main URLGenerator
sys.path.insert(0, str(Path(__file__).parent.parent))
from generators.urls import URLGenerator
from config import OUTPUT_V2_DIR, GITHUB_OUTPUT_V2_URL, TTS_OBJECTS_DIR

def main():
    logger = setup_logger(name='generate_urls', level='INFO')
    logger.info("Generating URLs JSON")
    
    generator = URLGenerator(
        output_dir=OUTPUT_V2_DIR,
        github_base=GITHUB_OUTPUT_V2_URL,
        tts_objects_dir=TTS_OBJECTS_DIR
    )
    count = generator.generate_json(OUTPUT_V2_DIR / "datacards-urls.json")
    
    logger.info(f"Generated {count} URL(s)")

if __name__ == '__main__':
    main()
```

**Step 4:** Delete or refactor `pipeline/v2_output_processor.py`
- Either delete entirely
- OR make it a thin wrapper around URLGenerator
- Update pipeline.py to use URLGenerator directly

**Testing:**
- Run URL generation via pipeline
- Run via CLI: `python script/generators/metadata/urls.py`
- Compare output files - should be identical
- Verify all URLs are correct and accessible

---

### Task 1.4: Rename cardboxes.py
**Priority:** 🟡 High  
**Files Affected:**
- `script/generators/objects/cardboxes.py` → `tts_objects.py`

**Steps:**
1. Rename file: `cardboxes.py` → `tts_objects.py`
2. Update imports in:
   - `pipeline/pipeline.py`
   - `generators/generate.py`
   - `generators/objects/generate.py`
3. Search codebase for any other references

**Find & Replace:**
```python
# BEFORE
from generators.objects.cardboxes import TTSGenerator

# AFTER
from generators.objects.tts_objects import TTSGenerator
```

**Testing:**
- Run pipeline with TTS generation step
- Verify TTS objects are created correctly
- Check no import errors

---

## Phase 2: Structure Reorganization
**Estimated Time:** 1 day  
**Risk Level:** Medium  
**Can Break TTS:** No

### Task 2.1: Consolidate CLI Scripts
**Priority:** 🟡 High  
**Goal:** Reduce confusion, keep only essential entry points

**Current State:**
```
script/
├── run_pipeline.py               # Main CLI ✅ KEEP
├── pipeline/
│   ├── process_pdfs_cli.py      # ❌ DELETE (redundant)
│   └── extract_images_cli.py    # ❌ DELETE (redundant)
└── generators/
    ├── generate.py              # ⚠️ REFACTOR
    └── objects/
        └── generate.py          # ⚠️ MERGE or DELETE
```

**Actions:**

**Step 1:** Delete redundant pipeline CLIs
```bash
# These duplicate --step process and --step extract
rm script/pipeline/process_pdfs_cli.py
rm script/pipeline/extract_images_cli.py
```

**Step 2:** Consolidate generator CLIs

**Option A (Recommended):** Keep only `generators/generate.py`, delete `generators/objects/generate.py`

Update `generators/generate.py` to include all commands:
```python
#!/usr/bin/env python3
"""
Unified generation CLI for TTS objects and metadata.

Usage:
    python script/generators/generate.py objects display-table
    python script/generators/generate.py metadata urls
"""
```

**Option B:** Keep both but document clearly which to use when

**Step 3:** Update documentation
- Update README with correct CLI commands
- Remove references to deleted scripts
- Document when to use `run_pipeline.py` vs `generators/generate.py`

**Testing:**
- Test main pipeline: `python script/run_pipeline.py --step all`
- Test generator CLI: `python script/generators/generate.py objects display-table`
- Verify all functionality still works

---

### Task 2.2: Organize Generators Directory
**Priority:** 🟡 High  
**Current Structure:**
```
generators/
├── generate.py
├── objects/
│   ├── generate.py
│   ├── urls.py
│   ├── cardboxes.py
│   ├── display_table.py
│   ├── tokens.py
│   ├── cardbox_helpers.py
│   └── ...
└── metadata/
    ├── urls.py
    ├── tts_metadata.py
    ├── datacards.py
    └── ...
```

**Issues:**
- URLs in both objects/ and metadata/
- Unclear when something is "object" vs "metadata"
- Helper files mixed with generators

**Proposed Structure:**
```
generators/
├── cli.py                    # Main CLI (renamed from generate.py)
├── urls.py                   # Single URL generator
├── tts_objects.py           # TTS object generation
├── display_table.py         # Display table
├── tokens.py                # Token generation
├── metadata_files.py        # Metadata JSON generation
└── helpers/
    ├── guid.py              # GUID generation (from cardbox_helpers)
    └── tts_templates.py     # TTS template loading
```

**Implementation:**
1. Flatten structure - move key files up
2. Create helpers/ subdirectory for utilities
3. Update all imports
4. Keep legacy structure temporarily with deprecation warnings

**Testing:**
- Run all generation tasks
- Verify imports work
- Check backward compatibility

---

## Phase 3: Code Quality Improvements
**Estimated Time:** 1 day  
**Risk Level:** Low  
**Can Break TTS:** No

### Task 3.1: Break Up Long Functions
**Priority:** 🟢 Medium  
**Target:** `ImageExtractor._analyze_pages()` (200+ lines)

**Refactoring Strategy:**
```python
class ImageExtractor:
    def _analyze_pages(self, pdf_document, team, card_type):
        """Main orchestrator - now much shorter."""
        context = AnalysisContext(card_type)
        card_pages = []
        
        for page_num in range(len(pdf_document)):
            if context.should_skip_page(page_num):
                continue
            
            page = pdf_document[page_num]
            page_info = self._analyze_single_page(page, page_num, context, team, card_type)
            card_pages.append(page_info)
            context.advance_page()
        
        return card_pages
    
    def _analyze_single_page(self, page, page_num, context, team, card_type):
        """Analyze one page and determine its properties."""
        text = page.get_text().upper()
        
        card_name = self._extract_card_name(page, card_type, team)
        has_continuation = self._detect_continuation_marker(text)
        has_back = self._determine_has_back(
            card_name, has_continuation, page_num, 
            pdf_document, context, card_type
        )
        
        return {
            'page_num': page_num,
            'card_name': card_name,
            'has_back': has_back
        }
    
    def _detect_continuation_marker(self, text: str) -> bool:
        """Check if page has continuation marker."""
        markers = [
            'CONTINUES ON OTHER SIDE',
            'CONTINUES ON THE OTHER SIDE',
            'RULES CONTINUE ON OTHER SIDE'
        ]
        return any(marker in text for marker in markers)
    
    def _determine_has_back(self, card_name, has_continuation, 
                           page_num, pdf_document, context, card_type):
        """Determine if this card has a back side."""
        # Complex logic extracted here
        pass

class AnalysisContext:
    """Tracks state during page analysis."""
    def __init__(self, card_type):
        self.card_type = card_type
        self.skip_next = False
        self.last_faction_rule = None
        self.faction_rule_counters = {}
        self.options_mode = False
```

**Benefits:**
- Each function < 50 lines
- Single responsibility
- Easier to test
- Easier to understand

**Testing:**
- Unit tests for each small function
- Integration test for full _analyze_pages
- Test on various PDF types

---

### Task 3.2: Improve Error Handling
**Priority:** 🟢 Medium  
**Current Pattern:**
```python
try:
    # Complex logic
except Exception as e:
    self.logger.error(f"Failed: {e}")
    return []  # Silent failure
```

**Better Pattern:**
```python
class CardExtractionError(Exception):
    """Raised when card extraction fails."""
    pass

try:
    # Complex logic
except FileNotFoundError as e:
    self.logger.error(f"PDF file not found: {pdf_path}")
    raise CardExtractionError(f"Cannot extract from missing file: {pdf_path}") from e
except fitz.FileDataError as e:
    self.logger.error(f"Corrupt PDF: {pdf_path}")
    raise CardExtractionError(f"PDF file is corrupt or invalid: {pdf_path}") from e
except Exception as e:
    self.logger.error(f"Unexpected error extracting {pdf_path}: {e}", exc_info=True)
    raise
```

**Implementation:**
1. Define custom exceptions in `models.py`:
   ```python
   class DatacardError(Exception):
       """Base exception for datacard processing."""
       pass
   
   class CardExtractionError(DatacardError):
       """Card extraction failed."""
       pass
   
   class TeamIdentificationError(DatacardError):
       """Could not identify team."""
       pass
   ```

2. Update error handling across pipeline
3. Let errors bubble up - catch at top level (run_pipeline.py)
4. Add --strict flag for fail-fast vs. continue-on-error

**Testing:**
- Test with corrupt PDFs
- Test with missing files
- Verify error messages are helpful

---

### Task 3.3: Add Comprehensive Docstrings
**Priority:** 🟢 Medium  
**Coverage Target:** 90%+ of public functions

**Template:**
```python
def process_team_cards(team_name: str, card_types: List[CardType]) -> ProcessingResult:
    """
    Process all cards for a specific team.
    
    Args:
        team_name: Canonical team name (e.g., 'kasrkin', 'hearthkyn-salvagers')
        card_types: List of card types to process
    
    Returns:
        ProcessingResult with counts and any errors
    
    Raises:
        TeamIdentificationError: If team not found in config
        CardExtractionError: If extraction fails
    
    Example:
        >>> result = process_team_cards('kasrkin', [CardType.DATACARDS])
        >>> print(f"Processed {result.cards_count} cards")
    """
    pass
```

**Files Priority:**
1. `models.py` - All classes and methods
2. `pipeline/pipeline.py` - Public methods
3. `generators/*.py` - Public functions
4. `utils.py` - All functions

**Tools:**
- Use `pydocstyle` to check coverage
- Use `sphinx` to generate HTML docs (future)

---

## Phase 4: Documentation & Testing
**Estimated Time:** 1 day  
**Risk Level:** Low  
**Can Break TTS:** No

### Task 4.1: Update DEVELOPMENT.md
**Priority:** 🟢 Medium  
**Changes Needed:**

1. **Remove confusing rule (line 205):**
```markdown
# REMOVE THIS:
- **Exception**: Python convention parameters (`self` for instance methods, 
  `card_type_class` for @classmethod instead of `cls`)

# REPLACE WITH:
- Use standard Python conventions: `self` for instance methods, `cls` for class methods
```

2. **Add import guidelines:**
```markdown
## Import Organization

### Standard Order
1. Standard library imports
2. Third-party imports  
3. Local application imports

### Use Absolute Imports
```python
# ✅ GOOD
from models import Team, CardType
from generators.urls import URLGenerator
from config import OUTPUT_V2_DIR

# ❌ BAD
from .models import Team
from ..generators.urls import URLGenerator
```

### Configuration
Always import from central config:
```python
from config import PROJECT_ROOT, OUTPUT_V2_DIR, TTS_OBJECTS_DIR
```
```

3. **Document actual structure:**
```markdown
## Project Structure

```
kt-datacards/
├── script/
│   ├── config.py              # ⭐ Central configuration
│   ├── models.py              # Data models
│   ├── managers.py            # Data managers
│   ├── utils.py               # Utilities
│   ├── run_pipeline.py        # 🚀 Main entry point
│   ├── pipeline/              # Processing steps
│   │   ├── pipeline.py        # Main orchestrator
│   │   ├── pdf_processor.py
│   │   ├── image_extractor.py
│   │   └── ...
│   └── generators/            # Output generation
│       ├── cli.py             # 🚀 Generation CLI
│       ├── urls.py
│       ├── tts_objects.py
│       └── ...
├── config/                    # Configuration files
├── input/                     # Source PDFs
├── processed/                 # Intermediate files
├── output_v2/                 # ⚠️ IMMUTABLE - Final outputs
└── tts_objects/               # ⚠️ IMMUTABLE - TTS files
```
```

---

### Task 4.2: Create ARCHITECTURE.md
**Priority:** 🟢 Medium  
**Content:**

```markdown
# Architecture Overview

## Data Flow

```
┌─────────┐
│ Raw PDFs│
│ (input/)│
└────┬────┘
     │
     ▼
┌─────────────────┐
│ TeamIdentifier  │ Identify team from PDF content
│ PDFProcessor    │ Organize by team/type
└────┬────────────┘
     │
     ▼ processed/
┌─────────────────┐
│ ImageExtractor  │ Extract card images
└────┬────────────┘
     │
     ▼ output_v2/
┌─────────────────┐
│ BacksideProc    │ Add card backsides
│ BoxTextureProc  │ Process box textures
└────┬────────────┘
     │
     ▼
┌─────────────────┐
│ URLGenerator    │ Generate datacards-urls.json
│ TTSGenerator    │ Generate TTS objects
│ TokenGenerator  │ Generate token bags
└────┬────────────┘
     │
     ▼ tts_objects/
┌─────────────────┐
│ MetadataGen     │ Generate metadata files
│ DisplayTable    │ Generate display table
└─────────────────┘
```

## Core Components

### Models (`models.py`)
- `Team`: Team representation with name, faction, aliases
- `CardType`: Enum of card types
- `Datacard`: Individual card with front/back images

### Managers (`managers.py`)
- `TeamDataManager`: Manages team_data.json (card content)
- `ExtractionMetadataManager`: Manages extraction_metadata.json (ETL info)

### Pipeline (`pipeline/`)
- `DatacardPipeline`: Orchestrates all steps
- `TeamIdentifier`: Resolves team names
- `PDFProcessor`: Identifies and organizes PDFs
- `ImageExtractor`: Extracts card images from PDFs
- `BacksideProcessor`: Adds backside images
- `BoxTextureProcessor`: Processes 3D box textures

### Generators (`generators/`)
- `URLGenerator`: Creates datacards-urls.json
- `TTSGenerator`: Creates TTS Custom_Model_Bag objects
- `DisplayTableGenerator`: Creates team grid
- `TokenGenerator`: Creates token bags

## Configuration (`config.py`)

Central source of truth for:
- All directory paths
- Default settings (DPI, canvas sizes)
- GitHub URLs
- File paths (team config, GUIDs)

## Key Design Decisions

### Why V2 Structure?
- V1 (`output/`) is flat: `output/{team}/{type}/`
- V2 (`output_v2/`) is hierarchical: `output_v2/{faction}/{team}/{type}/`
- V1 maintained for backward compatibility (TTS references)
- All new work uses V2

### Why Separate Managers?
- `TeamDataManager`: Card content for users/apps
- `ExtractionMetadataManager`: ETL metadata for pipeline debugging
- Different audiences, different update frequencies

### Why Tokens Separate?
- Tokens optional (not all teams have them)
- Different source (extracted vs. generated)
- Different TTS object type (infinite bag vs. card deck)
```

---

### Task 4.3: Add Test Suite
**Priority:** 🟢 Medium  
**Initial Structure:**

```
script/
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_team_identifier.py
    ├── test_image_extractor.py
    ├── test_url_generator.py
    ├── fixtures/
    │   ├── sample_team_config.yaml
    │   └── pdfs/
    │       └── sample_datacard.pdf
    └── README.md
```

**Priority Tests:**

**1. test_models.py**
```python
import pytest
from models import Team, CardType

def test_team_normalize_name():
    assert Team.normalize_name("Kasrkin") == "kasrkin"
    assert Team.normalize_name("Hearthkyn Salvagers") == "hearthkyn-salvagers"

def test_team_matches():
    team = Team("kasrkin", aliases=["kasrkin troopers"])
    assert team.matches("Kasrkin")
    assert team.matches("KASRKIN TROOPERS")
    assert not team.matches("blooded")

def test_cardtype_from_string():
    assert CardType.from_string("datacards") == CardType.DATACARDS
    assert CardType.from_string("Firefight Ploys") == CardType.FIREFIGHT_PLOYS
```

**2. test_team_identifier.py**
```python
def test_identify_team_from_text():
    # Test with fixture config
    pass

def test_get_all_teams():
    # Should return all teams from config
    pass
```

**Run Tests:**
```bash
# Install pytest
poetry add --dev pytest pytest-cov

# Run tests
poetry run pytest script/tests/ -v

# With coverage
poetry run pytest script/tests/ --cov=script --cov-report=html
```

---

## Phase 5: Optional Enhancements
**Estimated Time:** 2-3 days  
**Risk Level:** Low  
**Priority:** 🔵 Low (Nice to Have)

### Task 5.1: Convert to Proper Python Package

**Current:** Messy sys.path manipulation  
**Goal:** Proper package structure

```
kt-datacards/
├── pyproject.toml
├── src/
│   └── kt_datacards/
│       ├── __init__.py
│       ├── config.py
│       ├── models.py
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── pipeline.py
│       │   └── generate.py
│       ├── pipeline/
│       │   ├── __init__.py
│       │   └── ...
│       └── generators/
│           ├── __init__.py
│           └── ...
└── tests/
    └── ...
```

**Install as package:**
```bash
pip install -e .
```

**Run as module:**
```bash
python -m kt_datacards.cli.pipeline --step all
kt-datacards pipeline --step all  # If entry point configured
```

---

### Task 5.2: Add Pre-commit Hooks

**Install:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.11
  
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=100']
  
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ['--profile', 'black']
```

---

### Task 5.3: Add CI/CD Pipeline

**GitHub Actions:**
```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install poetry
      - run: poetry install
      - run: poetry run pytest script/tests/ --cov
```

---

## Rollback Plan

If any phase causes issues:

### Rollback Steps
1. **Git is your friend** - commit after each task
   ```bash
   git commit -m "Phase 1.1: Add config.py"
   git commit -m "Phase 1.2: Fix logging"
   ```

2. **Tag before major changes**
   ```bash
   git tag pre-refactor-phase-2
   ```

3. **Rollback if needed**
   ```bash
   git revert HEAD
   # or
   git reset --hard pre-refactor-phase-2
   ```

### Risk Mitigation
- **Test after each task** - don't batch changes
- **Keep backups** - copy entire directory before starting
- **Test on sample teams first** - don't run on all 40+ teams immediately
- **Monitor output/** - must remain unchanged (TTS compatibility)

---

## Success Criteria

### Phase 1 Success
- [ ] All paths come from config.py
- [ ] No print() statements in production code
- [ ] Single URL generation implementation
- [ ] cardboxes.py renamed to tts_objects.py
- [ ] All tests pass
- [ ] Pipeline runs successfully on test team

### Phase 2 Success
- [ ] CLI scripts consolidated
- [ ] Generators organized logically
- [ ] Documentation updated
- [ ] No broken imports
- [ ] All generation tasks work

### Phase 3 Success
- [ ] No function > 100 lines
- [ ] Specific exception handling
- [ ] 90%+ docstring coverage
- [ ] Code passes linting

### Phase 4 Success
- [ ] DEVELOPMENT.md reflects reality
- [ ] ARCHITECTURE.md created
- [ ] Test suite with >50% coverage
- [ ] All docs up to date

---

## Timeline

### Aggressive (Focus Mode)
- **Day 1:** Phase 1 (Critical Fixes)
- **Day 2:** Phase 2 (Structure)
- **Day 3:** Phase 3 (Code Quality)
- **Total:** 3 days

### Moderate (Balanced)
- **Week 1:** Phases 1-2
- **Week 2:** Phases 3-4
- **Total:** 2 weeks

### Conservative (Safe)
- **Week 1:** Phase 1 (one task per day)
- **Week 2:** Phase 2
- **Week 3:** Phase 3
- **Week 4:** Phase 4
- **Total:** 4 weeks

---

## Contact & Questions

For questions about this refactoring plan:
1. Review [REFACTORING-REVIEW.md](REFACTORING-REVIEW.md) for detailed analysis
2. Check [DEVELOPMENT.md](DEVELOPMENT.md) for coding standards
3. Test changes on small dataset first
4. Commit frequently, test thoroughly

**Remember:** The goal is maintainability, not perfection. Incremental improvement is success.
