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

There is one pipeline, the `pipeline/` Python package at the repo root. It has two
interchangeable extraction front-ends (**tracks**) that converge on a single
source-agnostic integration layer, then share the rest of the asset/TTS generation:

- `--source kt-app` — processes PDFs exported from the Kill Team mobile app (`input/`).
- `--source warcom` — processes official PDFs scraped from Warhammer Community.

The full run is 12 ordered steps:

```
 1  front_end            raw source → per-card split PDFs (layers/{track}/…)
 2  extract_artwork      raw source → lore art + icons (layers/integration/{team}/artwork)
 3  build_structure      split PDFs → layers/{track}/structure/{team}-structure.json
 4  integrate_classified extracted + structure → layers/integration/{team}/*.pdf + manifest.json
 5  content_analysis     classified PDFs + manifest → content maps + pipeline-state.json
 6  extract_backsides    artwork → output/{team}/card-backside/*
 7  extract_tokens       content + artwork → output/{team}/tokens/*.png
 8  generate_dice        artwork + config → output/{team}/dice/*
 9  generate_box_texture artwork + config → output/{team}/cardbox/*
10  generate_card_images classified PDFs + backsides + content → output/{team}/cards/*
11  extract_stats        content → output/{team}/data/{team}-team-data.json
12  generate_tts         cards + stats + dice + cardbox → output/{team}/tts_objects/*.json
```

Steps 1–4 are track-specific (need `--source`); steps 5–12 operate only on the shared
integration layer and are source-agnostic. Run `python -m pipeline.main --list` to see
the step list.

### Input → Output Flow

```
input/legionaries.pdf  →  [PIPELINE]  →  output/legionaries/
                                            ├── cards/
                                            │   ├── datacards/
                                            │   ├── equipment/
                                            │   └── faction-rules/
                                            ├── tokens/
                                            ├── dice/
                                            ├── cardbox/
                                            ├── data/
                                            │   └── legionaries-team-data.json
                                            └── tts_objects/
                                                └── Legionaries.json
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

Run the pipeline from the repo root with `PYTHONPATH` set to the repo root.

### Basic Usage: Process All Teams

Place your Kill Team PDF exports in the `input/` directory, then run:

```bash
python -m pipeline.main --source kt-app
```

This executes all 12 steps for every team on the `kt-app` track. Progress is displayed
in real-time, and results are saved to `output/{team}/` (cards, tokens, dice, cardbox,
data, and `tts_objects/`).

Use `--source warcom` instead to process official Warhammer Community PDFs.

### List Steps

```bash
python -m pipeline.main --list
```

### Process Specific Steps

```bash
# Run a single step
python -m pipeline.main --source kt-app --step extract_artwork

# Run a range of steps
python -m pipeline.main --source kt-app --from build_structure --to content_analysis

# Generate only the TTS objects (shared step — no --source needed for steps 5–12)
python -m pipeline.main --step generate_tts
```

### Process Specific Teams

```bash
# Process only one team
python -m pipeline.main --source kt-app --teams legionaries

# Process multiple teams (comma-separated, no spaces)
python -m pipeline.main --source kt-app --teams legionaries,kommandos,kasrkin
```

### Useful Flags

- `--teams a,b` — comma-separated team filter (default: all teams)
- `--step X` — run a single named step
- `--from X --to Y` — run an inclusive range of steps
- `--jobs N` — parallel worker count
- `--force` — ignore caches and regenerate

## 📁 Project Structure

```
kt-datacards/
├── pipeline/                       # The pipeline (Python package)
│   ├── main.py                     # Entry point (python -m pipeline.main)
│   ├── steps/                      # One module per pipeline step
│   └── utils/                      # Shared helpers (paths, artwork, etc.)
├── input/                          # Raw kt-app PDF exports (transient/import only)
├── input_archive/                  # Archived source PDFs by team
├── layers/                         # Intermediate data
│   ├── kt-app/                     # kt-app track staging/extracted/structure (gitignored)
│   ├── warcom/                     # warcom track staging/extracted/structure (gitignored)
│   └── integration/                # Shared classified PDFs + per-team pipeline-state.json
├── output/                         # Final assets (referenced by TTS via main-branch URLs)
│   ├── {teamname}/
│   │   ├── cards/                  # Card images by type
│   │   ├── tokens/                 # Processed token images
│   │   ├── dice/                   # Team dice assets
│   │   ├── cardbox/                # Card box mesh/texture
│   │   ├── data/                   # {team}-team-data.json
│   │   └── tts_objects/            # TTS-ready JSON objects
│   └── _generic-tts-objects/       # Shared/generic TTS objects
├── config/                         # Configuration and assets
│   ├── team-config.yaml            # Team name mappings, factions, tokens
│   ├── defaults/                   # Default assets (box, card-backside, tts-image, ...)
│   ├── teams/{teamname}.yaml       # Team-specific overrides
│   └── pipelines/warcom/           # Warcom card templates / scrape config
├── tools/                          # Standalone utility scripts
├── dev/                            # Development/debugging scripts
└── docs/                           # Project documentation
```

### Key Directories

- **`input/`**: Drop your kt-app PDF exports here (any filename works)
- **`layers/integration/`**: Shared, source-agnostic classified PDFs + per-team state
- **`output/{team}/`**: Final assets (cards, tokens, dice, cardbox, data, tts_objects)
- **`config/teams/`**: Add team-specific overrides (custom backsides, box models, tokens)

> Output assets are referenced by TTS via `main`-branch raw URLs:
> `https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/{team}/...`


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
