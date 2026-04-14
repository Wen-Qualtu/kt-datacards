---
description: kt-datacards project orientation — directory structure, critical constraints, naming conventions, config system, team identification, and dependencies. Load this first when working on any part of the project.
tags: [kill-team, project-structure, config, naming-conventions, kill-team-datacards]
---

# kt-datacards Project — Structure & Rules

## When to Use This Skill

Load for any task on this project. Covers:
- Project layout and directory purposes
- Critical rules AI agents must never violate
- Config file formats and team naming
- Python coding standards and naming conventions

For pipeline/extraction work also load **SKILL-etl.md**.  
For TTS object generation, Lua, or timestamp work also load **SKILL-tts.md**.

---

## 🚨 Critical Constraints

### 1. Never Break TTS URLs
**The `output/` folder structure is IMMUTABLE.**
- TTS cards reference exact GitHub raw URLs like `https://raw.githubusercontent.com/.../output/{team}/cards/...`
- ✅ DO: Add new files or update existing image content
- ❌ DON'T: Rename folders, restructure paths, or move files in `output/`

### 2. Logging — No Print Statements
ALL pipeline scripts MUST use Python's `logging` module exclusively.
- ✅ `logging.info()`, `logging.warning()`, `logging.error()`, `logging.debug()`
- ❌ `print(...)` anywhere in pipeline code
- CLI flag: `--log-level DEBUG|INFO|WARNING|ERROR`
- Format: `'%(levelname)s: %(message)s'`

### 3. Paths via pathlib Only
- ✅ `workspace_root = Path(__file__).parent.parent.parent`
- ✅ `output_dir = workspace_root / "output"`
- ❌ Hardcoded strings like `"c:/project/output"`

### 4. Data Quality Over Speed
Accuracy is paramount for stats extraction. Warn/error rather than produce wrong data.

---

## 📁 Repository Structure

```
kt-datacards/
├── config/
│   ├── team-config.yaml           # Master team registry (names, factions, aliases, tokens)
│   ├── team-guids.json            # TTS GUID assignments per team
│   ├── weapon_rules.json          # Weapon rule definitions with descriptions
│   ├── defaults/                  # Default assets for all teams
│   │   ├── box/                   # Default cardbox mesh/textures
│   │   ├── card-backside/         # Default card back images
│   │   ├── tts-image/             # Default TTS object images
│   │   ├── tts-script/            # Default Lua scripts
│   │   └── tts-token/             # Default token meshes/scripts
│   ├── pipelines/warcom/          # Warcom scraping patterns
│   └── teams/{teamname}.yaml      # Team-specific overrides
├── input/                         # Raw unprocessed PDFs (kt-app pipeline)
├── processed/{team}/              # Organized PDFs: {team}-datacards.pdf
├── output/                        # ⚠️ IMMUTABLE — TTS references these URLs
│   └── {teamname}/
│       ├── cards/{cardtype}/      # Card images
│       ├── textures/              # Team box textures
│       ├── tokens/                # Processed token images
│       └── tts/                   # TTS object JSON files
├── output_v2/                     # Active faction-organized output (current pipeline)
│   ├── .tts-image-hashes.json     # Hash cache for change detection
│   ├── datacards-urls.json        # All card URLs by team
│   ├── tts-metadata.json          # Timestamps for TTS update checking
│   ├── chaos/{teamname}/
│   ├── imperium/{teamname}/
│   └── xenos/{teamname}/
│       └── datacards/             # Extracted card JPGs
├── metadata/{team}/               # Per-team metadata JSONs
│   ├── card_index.json            # Card number → operative name mapping
│   ├── extraction_metadata.json   # Extraction details (⚠️ OFTEN MALFORMED)
│   └── token_index.json           # Token inventory
├── tts_objects/{team}/            # Generated TTS save JSON files
├── layers/
│   ├── kt-app/                    # kt-app pipeline intermediate data
│   └── warcom/                    # warcom pipeline intermediate data
│       ├── staging/               # Downloaded PDFs awaiting processing
│       └── extracted/{teamname}/  # Extracted cards and tokens
├── script/                        # PRIMARY pipeline (kt-app)
│   ├── run_pipeline.py            # CLI entry point
│   ├── generate_tts_objects.py    # Standalone TTS generation
│   ├── generate_tts_metadata.py   # Metadata generation
│   └── src/
│       ├── pipeline.py            # Pipeline orchestrator
│       ├── generators/            # TTS, URL, display table generators
│       ├── managers/              # Management utilities
│       ├── models/                # Data models (Team, Card, Token)
│       ├── processors/            # PDF, image, token processors
│       ├── token_tools/           # Token-specific utilities
│       └── utils/                 # Shared utilities
├── pipelines/warcom/              # Legacy pipeline (kept for reference)
│   ├── pdf_process_pipeline.py    # Warcom orchestrator
│   └── steps/                    # Numbered step implementations
├── tools/                         # Standalone utility scripts
├── dev/                           # Development/debugging scripts
├── docs/                          # Human-facing documentation
└── archive/                       # Source PDFs archived by team
```

---

## 🏗️ Architecture Principles

- **Models**: Data structures (`Team`, `Card`, `Token`) in `script/src/models/`
- **Processors**: Business logic (extraction, classification) in `script/src/processors/`
- **Generators**: Output creation (TTS objects, URLs) in `script/src/generators/`
- **Utils**: Shared utilities (file I/O, logging) in `script/src/utils/`
- **Dependency Injection**: Pass dependencies explicitly via parameters, never hardcode paths

---

## 📝 Naming Conventions

### Python Code

| Thing | Convention | Example |
|-------|-----------|---------|
| Files/modules | `snake_case` | `pdf_processor.py` |
| Classes | `PascalCase` | `TeamMetadata`, `TTSCard` |
| Functions/methods | `snake_case`, verb-based | `process_raw_pdfs()` |
| Variables | `snake_case`, full words (not abbrevs) | `team_identifier`, not `team_id` |
| Constants | `UPPER_SNAKE_CASE` | `DEFAULT_DPI`, `MAX_WORKERS` |
| Booleans | `is_*`, `has_*`, `should_*` prefix | `is_token_guide` |

### Config / YAML

| Thing | Convention | Example |
|-------|-----------|---------|
| Team slugs | `kebab-case` | `angels-of-death` |
| Card types | `kebab-case` | `datacards`, `firefight-ploys` |
| Metadata keys | `snake_case` | `last_updated`, `content_hash` |

---

## ⚙️ Config System

### `config/team-config.yaml` — Master Registry
```yaml
teams:
  hearthkyn-salvagers:
    canonical_name: "Hearthkyn Salvagers"
    faction: "xenos"              # imperium | chaos | xenos
    army: "leagues-of-votann"
    aliases:
      - "hearthkyn salvagers"
      - "salvagers"
    tokens:
      - name: "Void Armor"
        shape: "round"
        type: "token"
      - name: "Breach"
        shape: "octagon"
        type: "marker"
```

### `config/team-guids.json` — TTS GUIDs
```json
{
  "angels-of-death": {
    "card-box": "abc123",
    "token-bag": "def456"
  }
}
```

### `config/weapon_rules.json`
```json
{
  "Lethal 5+": {
    "description": "Critical hits on 5+ instead of 6",
    "icon": "lethal"
  }
}
```

### `config/teams/{team}.yaml` — Team Overrides
Individual overrides applied on top of defaults.

### `config/defaults/` — Templates
Default assets shared by all teams: box mesh/textures, card backside, Lua scripts, token meshes.

---

## 🏷️ Team Identification

### Team Slug
- Lowercase hyphenated: `angels-of-death`, `corsair-voidscarred`, `tempestus-aquilons`
- Used in all file paths, config keys, and folder names

### Canonical Name
- From `team-config.yaml` `canonical_name` field
- Title case: `"Angels of Death"`, `"Corsair Voidscarred"`

### Faction
- Three values: `imperium`, `chaos`, `xenos`
- Determines subfolder in `output_v2/`

### Name Normalization
```python
def roster_slug(s: str) -> str:
    """Strip non-ASCII for filename/path matching."""
    return re.sub(r"[^\x00-\x7f]", "", s)
```
Needed because operative names can contain: `ô`, `â`, `'` (smart quote), `‑` (non-breaking hyphen).

### Card Nickname Format (TTS)
```
[FF5500]E[-] {8/8} Stalker Alpha
│       │ │  │     └─ Operative name
│       │ │  └─ Current/max wounds
│       │ └─ Order state indicator (- = uncommitted)
│       └─ Order type (E=Engage, C=Conceal)
└─ Color code
```
When matching nicknames, strip the order prefix and wounds portion.

---

## ⚠️ Metadata Reliability

`extraction_metadata.json` is **often malformed** for some teams. **Always** wrap in try/except:

```python
try:
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
except json.JSONDecodeError:
    logger.warning(f"Malformed extraction_metadata.json for {team}")
    metadata = {}
```

Known malformed teams: `battleclade`, `deathwatch`, `exaction-squad`

---

## 🔧 Dependencies

```toml
# pyproject.toml (Python 3.11+)
pymupdf = "*"         # PDF text extraction and rendering
pillow = "*"          # Image manipulation
pypdf2 = "*"          # PDF processing
pytesseract = "*"     # OCR (fallback)
pyyaml = "*"          # Config parsing
pandas = "*"          # Data processing
opencv-python = "*"   # Image processing, contour detection
requests = "*"        # Web scraping (warcom pipeline)
beautifulsoup4 = "*"  # HTML parsing (warcom pipeline)
```

### Running Commands
```powershell
poetry install                  # Install all dependencies
poetry run python script/run_pipeline.py --step all
poetry run python script/run_pipeline.py --step extract --teams kasrkin
poetry run black .              # Code formatting
```
