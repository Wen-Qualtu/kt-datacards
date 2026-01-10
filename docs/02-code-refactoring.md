# Feature 02: Code Refactoring

## Status
🔴 Not Started

## Overview
Restructure the Python codebase to follow best practices with proper separation of concerns, classes, and modular design.

## Current Issues
- Scripts are monolithic with mixed concerns
- No clear separation between PDF processing, image extraction, text analysis
- Limited reusability of functions
- Configuration hardcoded in scripts
- No proper error handling/logging structure

## Proposed Structure

```
script/
├── config/
│   ├── team-mapping.yaml
│   └── settings.py              # Central configuration
├── src/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── team.py              # Team class
│   │   ├── datacard.py          # Datacard class
│   │   └── card_type.py         # CardType enum
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── pdf_processor.py     # PDF handling
│   │   ├── text_extractor.py   # OCR/text extraction
│   │   ├── image_extractor.py  # Image splitting
│   │   └── team_identifier.py  # Team name resolution
│   ├── generators/
│   │   ├── __init__.py
│   │   └── url_generator.py    # CSV generation
│   └── utils/
│       ├── __init__.py
│       ├── file_utils.py        # File operations
│       ├── path_utils.py        # Path handling
│       └── logger.py            # Logging setup
├── tests/
│   ├── __init__.py
│   ├── test_processors.py
│   ├── test_generators.py
│   └── fixtures/
├── main.py                       # Entry point
├── requirements.txt
└── README.md
```

## Key Classes to Implement

### 1. Team Class
```python
class Team:
    def __init__(self, name, aliases=None, metadata=None)
    - name: str (canonical name)
    - aliases: List[str]
    - metadata: dict
    - output_path: Path
    - processed_path: Path
    
    Methods:
    - resolve_name(text) -> str
    - get_output_folder(card_type) -> Path
```

### 2. Datacard Class
```python
class Datacard:
    def __init__(self, source_pdf, team, card_type)
    - source_pdf: Path
    - team: Team
    - card_type: CardType
    - pages: List[int]
    - front_image: Path
    - back_image: Path
    
    Methods:
    - extract_front() -> Image
    - extract_back() -> Image
    - save_images(output_dir)
```

### 3. CardType Enum
```python
class CardType(Enum):
    DATACARDS = "datacards"
    EQUIPMENT = "equipment"
    FACTION_RULES = "faction-rules"
    FIREFIGHT_PLOYS = "firefight-ploys"
    OPERATIVES = "operatives"
    STRATEGY_PLOYS = "strategy-ploys"
```

### 4. PDFProcessor Class
```python
class PDFProcessor:
    Methods:
    - identify_team(pdf_path) -> Team
    - identify_card_type(pdf_path) -> CardType
    - split_pages(pdf_path) -> List[Image]
    - extract_text(pdf_path) -> str
```

### 5. Pipeline Class
```python
class DatacardPipeline:
    def __init__(self, config)
    
    Methods:
    - process_raw_pdfs(team_filter=None)
    - extract_images(team_filter=None)
    - generate_urls()
    - run(teams=None, steps=None)
```

## Implementation Steps

### Phase 1: Setup Structure
- [ ] Create new folder structure
- [ ] Set up `__init__.py` files
- [ ] Create `settings.py` with configuration
- [ ] Set up logging infrastructure

### Phase 2: Create Model Classes
- [ ] Implement `Team` class
- [ ] Implement `Datacard` class
- [ ] Implement `CardType` enum
- [ ] Add unit tests for models

### Phase 3: Refactor Processors
- [ ] Extract PDF processing logic → `PDFProcessor`
- [ ] Extract text analysis → `TextExtractor`
- [ ] Extract image handling → `ImageExtractor`
- [ ] Extract team identification → `TeamIdentifier`
- [ ] Add unit tests for each processor

### Phase 4: Refactor Generators
- [ ] Move URL generation logic → `URLGenerator`
- [ ] Add templating for CSV output
- [ ] Add unit tests

### Phase 5: Create Pipeline
- [ ] Implement `DatacardPipeline` class
- [ ] Migrate existing script logic
- [ ] Add error handling
- [ ] Add progress reporting

### Phase 6: Create Main Entry Point
- [ ] Create `main.py` with CLI interface
- [ ] Add argument parsing
- [ ] Wire up pipeline
- [ ] Add help documentation

### Phase 7: Testing & Documentation
- [ ] Write comprehensive tests
- [ ] Update README.md
- [ ] Add docstrings to all classes/methods
- [ ] Create usage examples

## Configuration Management

### settings.py Example
```python
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).parent.parent.parent
INPUT_DIR = ROOT_DIR / "input"
PROCESSED_DIR = ROOT_DIR / "processed"
OUTPUT_DIR = ROOT_DIR / "output"
ARCHIVE_DIR = ROOT_DIR / "archive"

# Team mapping
TEAM_MAPPING_PATH = ROOT_DIR / "script" / "config" / "team-mapping.yaml"

# Processing options
DEFAULT_DPI = 300
IMAGE_FORMAT = "PNG"

# URL generation
GITHUB_BASE_URL = "https://raw.githubusercontent.com/..."
```

## Benefits
- **Maintainability**: Clear separation of concerns
- **Testability**: Each component can be tested independently
- **Reusability**: Functions/classes can be reused across scripts
- **Extensibility**: Easy to add new features
- **Debugging**: Better error handling and logging

## Migration Strategy
1. Create new structure alongside existing scripts
2. Migrate functionality piece by piece
3. Test each component thoroughly
4. Keep old scripts until new system is verified
5. Remove old scripts once confident

## Testing Requirements
- [ ] Unit tests for all classes (>80% coverage)
- [ ] Integration tests for full pipeline
- [ ] Test with sample PDFs from each team
- [ ] Test error conditions (missing files, corrupted PDFs)

## Estimated Effort
- **Complexity**: High
- **Time**: 8-12 hours
- **Risk**: Medium (requires thorough testing)

## Dependencies
- Should complete Feature 01 (Project Restructuring) first
- Will enable Feature 05 (Parameterized Execution)
