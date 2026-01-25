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

### TTS Objects
Generate Tabletop Simulator objects:
```bash
# Generate TTS JSON objects with preview images
poetry run python script/generate_tts_objects.py

# Extract preview images from box textures (run once when adding new teams)
poetry run python script/extract_tts_preview_images.py
```

## Directory Structure

```
script/
├── run_pipeline.py              # Main entry point (ONLY script in root)
├── README.md                    # This file
│
├── src/                         # Source code
│   ├── models/                  # Data models (Team, CardType, Datacard)
│   ├── processors/              # Processing logic (PDF, image, backside)
│   ├── generators/              # Output generation (URLs)
│   ├── utils/                   # Utilities (logging, paths)
│   └── pipeline.py              # Pipeline orchestration
│
├── processing/                  # PDF and image processing
│   ├── README.md
│   ├── process_pdfs.py              # Process raw PDFs (step 1)
│   └── extract_images.py            # Extract card images (step 2)
│
├── metadata_generation/         # Metadata and URL generation
│   ├── README.md
│   ├── generate_metadata.py         # Generate output metadata YAML
│   ├── generate_tts_metadata.py     # Generate TTS metadata files
│   ├── generate_tts_objects.py      # Generate TTS JSON objects
│   ├── generate_urls.py             # Generate datacards-urls.json
│   └── create_manager_metadata.py   # Create Manager bag metadata
│
├── spawner/                     # Team spawner token
│   ├── README.md
│   ├── generate_spawner_image.py    # Generate team list image
│   └── generate_team_spawner.py     # Generate spawner token
│
├── display_table/               # Display table management
│   ├── README.md
│   ├── extract_manager_bag.py       # Extract Manager from table
│   └── generate_display_table.py    # Regenerate display table
│
├── tokens/                      # Token management
│   ├── README.md
│   └── extract_token_bags.py        # Extract token bags
│
├── tools/                       # Utility tools for TTS object updates
│   ├── README.md
│   ├── update_manager.py            # Update Manager bag Lua
│   ├── update_cardbox_features.py   # Update card box features
│   ├── update_token_timestamps.py   # Add token timestamp checking
│   ├── verify_timestamps.py         # Verify timestamps
│   └── add_backsides.py             # Add backside images
│
├── archive/                     # Historical scripts (reference only)
│   ├── README.md
│   └── fix_onload.py                # One-time corruption fix
│
├── tests/                       # Test scripts
│   ├── test_refactored.py           # Validation tests
│   └── check_pdf.py                 # PDF content checker
│
└── tools/                       # Additional utilities
```

## Architecture

### Directory Structure
The pipeline uses clear separation between input and configuration:
- `input/` - Recursively processes all PDFs (root and any subdirectories)
- `config/` - Static configuration files (team mappings, custom backsides)

This allows flexible organization of source PDFs in `input/_raw/`, `input/team-name/`, etc.

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
