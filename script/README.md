# Datacard Processing Scripts

This directory contains the refactored Kill Team datacard processing pipeline.

## Quick Start

### Full Pipeline
Process everything from raw PDFs to TTS-ready URLs:
```bash
poetry run python script/run_pipeline.py
```

### Individual Steps
Run specific pipeline steps:
```bash
# Process raw PDFs
poetry run python script/run_pipeline.py --step process

# Extract images
poetry run python script/run_pipeline.py --step extract

# Add backsides
poetry run python script/run_pipeline.py --step backsides

# Generate URLs
poetry run python script/run_pipeline.py --step urls
```

### Options
```bash
# Filter by teams
poetry run python script/run_pipeline.py --teams kasrkin blooded

# Custom DPI
poetry run python script/run_pipeline.py --dpi 600

# Verbose logging
poetry run python script/run_pipeline.py -v

# Log to file
poetry run python script/run_pipeline.py --log-file pipeline.log
```

## Directory Structure

```
script/
├── run_pipeline.py         # Main entry point
├── README.md               # This file
│
├── src/                    # Source code
│   ├── models/             # Data models (Team, CardType, Datacard)
│   ├── processors/         # Processing logic (PDF, image, backside)
│   ├── generators/         # Output generation (URLs)
│   ├── utils/              # Utilities (logging, paths)
│   └── pipeline.py         # Pipeline orchestration
│
├── scripts/                # Individual step scripts
│   ├── process_pdfs.py     # Process raw PDFs
│   ├── extract_images.py   # Extract card images
│   ├── add_backsides.py    # Add backside images
│   └── generate_urls.py    # Generate URLs CSV
│
└── tests/                  # Test scripts
    ├── test_refactored.py  # Validation tests
    └── check_pdf.py        # PDF content checker
```

## Architecture

### Models
- **Team** - Kill Team faction with name normalization and path management
- **CardType** - Enum for card types (datacards, equipment, etc.)
- **Datacard** - Individual card linking PDF source to output images

### Processors
- **TeamIdentifier** - Team name resolution from YAML mapping
- **PDFProcessor** - PDF identification (filename + content analysis)
- **ImageExtractor** - Card image extraction with front/back detection
- **BacksideProcessor** - Backside image management (team-specific → default)

### Generators
- **URLGenerator** - GitHub raw URL CSV generation for TTS

### Pipeline
- **DatacardPipeline** - Main orchestrator coordinating all components

## Key Features

✅ **Clean Architecture** - Proper separation of concerns  
✅ **Type Safety** - Type hints throughout  
✅ **Error Handling** - Comprehensive logging and error recovery  
✅ **Extensibility** - Easy to add new card types or processors  
✅ **Maintainability** - Self-documenting code with clear module boundaries  

## Testing

Run validation tests:
```bash
poetry run python script/tests/test_refactored.py
```

## Documentation

For detailed development rules and guidelines, see:
- [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) - Development rules
- [FEATURE-02-COMPLETION-REPORT.md](../FEATURE-02-COMPLETION-REPORT.md) - Implementation details
