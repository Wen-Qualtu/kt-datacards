# KT Datacards Processor

This project processes Kill Team datacard PDFs and extracts individual cards as JPG images for use in Tabletop Simulator.

## Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Workflow

### 1. Process Raw PDFs
Place PDF files (exported from Kill Team mobile app) in the `input/` folder and run:
```bash
python script/process_raw_pdfs.py
```

This script:
- Identifies team names and card types from PDF content
- Renames and organizes PDFs into `processed/<team-name>/` folders
- Archives original files to `archive/<team-name>/` (keeps GUIDs)
- Uses team name mapping from `input/config/team-name-mapping.yaml`

### 2. Extract Card Images
Once PDFs are organized in `processed/`, extract individual cards:
```bash
python script/extract_pages.py
```

This script:
- Reads PDFs from `processed/<team-name>/` folders
- Extracts each card as a separate JPG image
- Saves to `output/<team-name>/<card-type>/` folders
- Names cards based on extracted text (e.g., `trooper-gunner_front.jpg`)

### 3. Add Default Backsides
Some cards don't have backs in the PDF. Add default backsides:
```bash
python script/add_default_backsides.py
```

This uses backsides from:
- **Default**: `input/config/card-backside/default/default-backside-{portrait|landscape}.jpg`
- **Team-specific** (optional): `input/config/card-backside/team/{team-name}/backside-{portrait|landscape}.jpg`

Team-specific backsides override defaults if present.

### 4. Generate URL CSV
Create a CSV with GitHub raw URLs for all cards:
```bash
python script/generate_urls.py
```

Generates `datacards-urls.csv` with URLs for use in Tabletop Simulator.

## Folder Structure

```
kt-datacards/
├── input/              # Raw PDF files (place new PDFs here)
├── processed/          # Organized PDFs by team
│   └── <team-name>/
├── output/             # Final card images (referenced by TTS)
│   └── <team-name>/
│       ├── datacards/
│       ├── equipment/
│       └── ...
├── archive/            # Original PDFs with GUIDs
│   └── <team-name>/
└── script/
    ├── config/
    │   ├── team-mapping.yaml
    │   ├── defaults/               # Default backside images
    │   │   ├── default-backside-portrait.jpg
    │   │   └── default-backside-landscape.jpg
    │   └── team-backsides/         # Team-specific backsides (optional)
    │       └── <team-name>/
    │           ├── backside-portrait.jpg
    │           └── backside-landscape.jpg
- **Custom Backsides**: Place team-specific backsides in `input/config/card-backside/team/{team-name}/`
  - `backside-portrait.jpg` for equipment, ploys, etc.
  - `backside-landscape.jpg` for datacards
    └── ...
```

## Configuration

- **DPI**: Adjust resolution in `extract_pages.py` (default: 300)
- **Team Mapping**: Edit `input/config/team-name-mapping.yaml` to map team name variations
