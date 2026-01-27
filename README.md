# Kill Team Datacards for Tabletop Simulator

An automated pipeline for processing Warhammer 40,000: Kill Team datacards into Tabletop Simulator (TTS) format. This tool extracts individual cards from PDF exports, organizes them by team and type, and generates all necessary assets for seamless TTS integration.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Poetry](https://img.shields.io/badge/poetry-dependency%20management-blue)](https://python-poetry.org/)

## 📋 Table of Contents

- [What Problem Does This Solve?](#what-problem-does-this-solve)
- [Features](#features)
- [How It Works](#how-it-works)
- [Setup](#setup)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Contributing](#contributing)

## 🎯 What Problem Does This Solve?

The Kill Team mobile app exports datacards as PDFs with random UUID filenames, containing mixed card types all in one document. Getting these into Tabletop Simulator requires:
- Manually splitting PDFs into individual card images
- Organizing hundreds of images by team and card type
- Creating proper front/back card pairs
- Generating URL mappings for TTS deck builders
- Adding team-specific card backsides and 3D box models

**This pipeline automates 100% of that workflow.**

## ✨ Features

- **Automatic Team Detection**: Identifies team names from PDF content using OCR and pattern matching
- **Smart Card Extraction**: Splits multi-page PDFs into individual card images with front/back detection
- **Organized Output**: Structures cards by team and type (datacards, equipment, ploys, faction rules, etc.)
- **TTS Asset Generation**: Creates complete TTS objects with:
  - Individual card JSON files
  - Custom card backsides
  - 3D box models
  - Team-specific preview images
  - Display table grid layout with all teams
- **Metadata Tracking**: Maintains comprehensive card metadata (card IDs, types, dimensions, extraction quality)
- **Reproducible**: Locked dependencies and clear workflows ensure consistent results across machines

## 🔧 How It Works

The pipeline processes your Kill Team PDFs in 7 automated steps:

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Extract from PDFs                                      │
│  • Analyze PDF content to identify team and card type           │
│  • Split into individual card images (front/back detection)     │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│  Step 2: Identify Card Backsides                                │
│  • Detect which cards have backside content                     │
│  • Flag cards that need default backsides added                 │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│  Step 3: Copy Team-Specific Backsides                           │
│  • Apply custom backsides from config/teams/{team}/card-backside/│
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│  Step 4: Copy Default Backsides                                 │
│  • Add default backsides for remaining cards                    │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│  Step 5: Copy 3D Box Models                                     │
│  • Copy team-specific or default box.obj files to output        │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│  Step 6: Generate TTS JSON Objects                              │
│  • Create TTS-compatible JSON for each team's card deck         │
│  • Include mesh URLs, deck state, card positions                │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│  Step 7: Generate Display Table Grid                            │
│  • Create master TTS object with all teams in alphabetical grid │
│  • 7-column layout with hand triggers and team labels           │
└─────────────────────────────────────────────────────────────────┘
```

### Input → Output Flow

```
input/legionaries.pdf  →  [PIPELINE]  →  output_v2/legionaries/
                                            ├── datacards/
                                            │   ├── card-001-front.png
                                            │   └── card-001-back.png
                                            ├── equipment/
                                            ├── faction-rules/
                                            └── ...
                                         
                                         tts_objects/
                                            ├── legionariesCards.json
                                            └── display-table/
                                                └── kt_all_teams_grid.json
```

## 🚀 Setup

### Prerequisites

- **Python 3.11+** (3.12+ recommended)
- **Poetry** for dependency management
- **Git** for version control

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/kt-datacards.git
   cd kt-datacards
   ```

2. **Install dependencies with Poetry**
   ```bash
   poetry install
   ```

3. **Activate the Poetry environment**
   ```bash
   poetry shell
   ```

That's it! The pipeline is ready to use.

### Optional: pyenv for Python Version Management

If you need to manage multiple Python versions:

```bash
pyenv install 3.12.5
pyenv local 3.12.5
```

## 📖 Usage

### Quick Start with Task Runner (Recommended)

Install [Task](https://taskfile.dev/) for simplified pipeline management:

```bash
# Install Task (Windows)
choco install go-task
# or: scoop install task

# Run full pipeline
task all

# Run specific pipeline steps
task pipeline:process      # Process PDFs and identify teams
task pipeline:extract      # Extract card images from PDFs
task pipeline:backsides    # Add backsides to cards
task pipeline:urls         # Generate datacards-urls.json
task pipeline:tokens       # Generate token integration

# Process specific teams
task pipeline:team TEAMS="kasrkin blooded"

# Deploy with branch-specific URLs for testing
task pipeline:deploy-acc
task pipeline:deploy-dev
task pipeline:deploy-main

# Infrastructure & utilities
task infra:check-env       # Check environment setup
task infra:test-imports    # Test Python imports
task infra:test-team       # Quick test on single team

# See all available tasks
task --list
```

See [Taskfile Guide](docs/TASKFILE-GUIDE.md) for complete documentation on branch deployment workflows, team-specific processing, and testing strategies.

### Manual Usage: Direct Python Commands

Place your Kill Team PDF exports in the `input/` directory, then run:

```bash
# Full pipeline
poetry run python script/run_pipeline.py --step all

# Individual steps
poetry run python script/run_pipeline.py --step process
poetry run python script/run_pipeline.py --step extract
poetry run python script/run_pipeline.py --step backsides
poetry run python script/run_pipeline.py --step urls
poetry run python script/run_pipeline.py --step tokens
```

This executes all steps automatically. Progress is displayed in real-time, and results are saved to:
- `output_v2/{teamname}/` - Organized card images
- `metadata/{teamname}/` - Card metadata JSON
- `tts_objects/` - TTS-ready JSON objects

### Available Command Line Options

```bash
# Process specific teams only
python script/run_pipeline.py --teams kasrkin blooded

# Use custom branch for GitHub URLs (for testing deployments)
python script/run_pipeline.py --branch acc

# Run specific pipeline step
python script/run_pipeline.py --step extract

# Custom DPI for image extraction
python script/run_pipeline.py --dpi 600

# Verbose logging
python script/run_pipeline.py -v

# Log to file
python script/run_pipeline.py --log-file pipeline.log

# Combine options
python script/run_pipeline.py --teams ratlings --branch dev -v
```

**Available steps:** `process`, `extract`, `backsides`, `urls`, `tokens`, `all`

## 📁 Project Structure

```
kt-datacards/
├── input/                          # Place your PDF exports here (transient/import only)
├── processed/                      # Intermediate processing files (incl. extracted tokens)
├── output_v2/                      # Final organized card images
│   └── {teamname}/
│       ├── datacards/
│       ├── equipment/
│       ├── faction-rules/
│       ├── firefight-ploys/
│       ├── operatives/
│       └── strategy-ploys/
├── metadata/                       # Card metadata and tracking
│   └── {teamname}/
│       ├── cards.json              # Card metadata
│       ├── backsides.json          # Backside status
│       └── extraction.json         # Extraction tracking
├── tts_objects/                    # TTS-ready JSON files
│   ├── {teamname}Cards.json        # Individual team decks
│   └── display-table/
│       └── kt_all_teams_grid.json  # Master grid with all teams
├── config/                         # Configuration and assets
│   ├── team-config.yaml            # Team name mappings
│   ├── defaults/                   # Default assets
│   │   ├── box/                    # Default 3D box model
│   │   ├── card-backside/          # Default card backs
│   │   └── tts-image/              # Default preview image
│   └── teams/{teamname}/           # Team-specific assets
│       ├── box/                    # Custom 3D box (optional)
│       ├── card-backside/          # Custom card backs (optional)
│       └── tts-image/              # Custom preview (optional)
├── script/                         # Main pipeline scripts
│   ├── run_pipeline.py             # Main entry point
│   ├── config.py                   # Centralized configuration
│   ├── models.py                   # Data models (Team, CardType, Datacard)
│   ├── managers.py                 # Data management (TeamDataManager, etc.)
│   ├── pipeline/                   # Pipeline implementation
│   │   ├── pipeline.py             # Pipeline orchestration
│   │   ├── pdf_processor.py       # PDF identification
│   │   ├── image_extractor.py     # Card extraction
│   │   ├── backside_processor.py  # Backside management
│   │   └── token_integration.py   # Token generation
│   ├── generators/                 # TTS object generation
│   │   ├── generate.py             # Main generator entry point
│   │   └── objects/
│   │       └── tts_objects.py      # TTS JSON generation
│   ├── tools/                      # Maintenance utilities
│   │   ├── extract_tokens.py       # Token extraction from PDFs
│   │   └── add_token_transparency_bg_sample.py  # Token transparency
│   └── token_tools/                # Token generation
│       ├── generate_tts_tokens.py  # Generate TTS token objects
│       ├── generate_team_token_bag.py  # Team token bags
│       └── add_tokens_to_box.py    # Embed tokens in card boxes
└── docs/                           # Project documentation
    ├── README.md                   # Documentation index
    ├── DEVELOPMENT.md              # Development guidelines
    ├── card-structure.md           # Card format documentation
    └── display-table-generation.md # Display table docs
```

### Key Directories

- **`input/`**: Drop your PDF exports here (any filename works, supports subdirectories)
- **`output_v2/`**: Organized card images ready for TTS
- **`tts_objects/`**: Complete TTS JSON objects you can import directly
- **`config/teams/`**: Add team-specific assets (custom backsides, box models, icons)
- **`script/`**: Pipeline implementation with clean separation of concerns

### Architecture

The pipeline uses clear separation between input and configuration:
- **Input**: `input/` - Recursively processes all PDFs (root and any subdirectories)
- **Config**: `config/` - Static configuration files (team mappings, custom backsides)
- **Models**: Data models (Team, CardType, Datacard) with type safety
- **Processors**: PDF processing, image extraction, backside management
- **Generators**: URL and TTS object generation
- **Pipeline**: Main orchestrator coordinating all components

Key features:
- Clean architecture with proper separation of concerns
- Type safety with type hints throughout
- Comprehensive error handling and logging
- Easy to extend with new card types or processors
- Self-documenting code with clear module boundaries

## 🤝 Contributing

Contributions are welcome! Whether you want to add new teams, improve card detection, or enhance TTS output, we'd love your help.

### Ways to Contribute

1. **Add New Teams**: Submit PDFs and team-specific assets
2. **Improve Detection**: Enhance team/card type identification accuracy
3. **Add Features**: Stats extraction, automated testing, better error handling
4. **Fix Bugs**: Found an issue? Open a PR with a fix
5. **Documentation**: Improve setup guides, add examples, clarify workflows

### Getting Started

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes**
   - Follow the style in existing code
   - Test your changes with the full pipeline
   - Update documentation as needed
4. **Commit with clear messages**
   ```bash
   git commit -m "Add: Custom backside support for Necron teams"
   ```
5. **Push and create a Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

### Development Guidelines

- **Python Style**: Follow PEP 8 conventions
- **Testing**: Run the full pipeline on test data before submitting
- **Documentation**: Update relevant docs for new features
- **Dependencies**: Add new packages via `poetry add package-name`

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for detailed development rules and project architecture.

For a quick overview of the project workflow, see [docs/README.md](docs/README.md).

### Adding Custom Team Assets

To add custom assets for a specific team:

1. Create folder: `config/teams/{teamname}/`
2. Add assets:
   - `card-backside/` - Custom card back images
   - `box/box.obj` - Custom 3D box model
   - `tts-image/preview.jpg` - Custom TTS preview image
3. Run pipeline - custom assets are automatically applied


## 📧 Contact

Questions? Issues? Open a [GitHub Issue](https://github.com/yourusername/kt-datacards/issues) or start a [Discussion](https://github.com/yourusername/kt-datacards/discussions).

---

**Made with ⚔️ for the Kill Team community**
