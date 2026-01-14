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

### Basic Usage: Process All PDFs

Place your Kill Team PDF exports in the `input/` directory, then run:

```bash
poetry run python script/run_pipeline.py --step all
```

This executes all 7 steps automatically. Progress is displayed in real-time, and results are saved to:
- `output_v2/{teamname}/` - Organized card images
- `metadata/{teamname}/` - Card metadata JSON
- `tts_objects/` - TTS-ready JSON objects

### Process Specific Steps

Run individual pipeline steps:

```bash
# Extract cards from PDFs only
poetry run python script/run_pipeline.py --step 1

# Generate TTS objects only (steps 1-5 must be complete)
poetry run python script/run_pipeline.py --step 6

# Generate display table grid only
poetry run python script/run_pipeline.py --step 7
```

### Process Specific Teams

```bash
# Process only one team
poetry run python script/run_pipeline.py --step all --team legionaries

# Process multiple teams
poetry run python script/run_pipeline.py --step all --team legionaries kommandos kasrkin
```

## 📁 Project Structure

```
kt-datacards/
├── input/                          # Place your PDF exports here
├── processed/                      # Intermediate processing files
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
├── dev/                            # Development utility scripts
├── script/                         # Main pipeline scripts
│   ├── run_pipeline.py             # Main entry point
│   └── src/                        # Pipeline implementation
└── docs/                           # Project documentation
    ├── README.md                   # Documentation index
    ├── DEVELOPMENT.md              # Development guidelines
    ├── card-structure.md           # Card format documentation
    └── display-table-generation.md # Display table docs
```

### Key Directories

- **`input/`**: Drop your PDF exports here (any filename works)
- **`output_v2/`**: Organized card images ready for TTS
- **`tts_objects/`**: Complete TTS JSON objects you can import directly
- **`config/teams/`**: Add team-specific assets (custom backsides, box models, icons)

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
