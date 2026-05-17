# Step 4: Extract Card Images

## Purpose

Render each classified PDF page to a JPEG image at 300 DPI. Produces a front and back image for every card. Where no back page exists in the source PDF, a default backside image is used. Output images are written to `output/{team}/cards/{card_type}/`.

---

## Script

`pipelines/kt-app/steps/4_extract_card_images.py`

---

## Input

| Path | Description |
|------|-------------|
| `layers/kt-app/classified/{team}/structure.json` | Card structure with front/back pairs (from Step 2) |
| `layers/kt-app/extracted/{team}/cards/{type}/*.pdf` | Single-page PDFs to render |
| `config/defaults/card-backside/default-backside-portrait.jpg` | Default back for portrait cards |
| `config/defaults/card-backside/default-backside-landscape.jpg` | Default back for landscape cards |
| `config/teams/{team}/card-backside/` | Optional team-specific backside overrides |

---

## Output

| Path | Description |
|------|-------------|
| `output/{team}/cards/{card_type}/{name}-front.jpg` | Front face image |
| `output/{team}/cards/{card_type}/{name}-back.jpg` | Back face image |

---

## Execution

```bash
poetry run python pipelines/kt-app/steps/4_extract_card_images.py
```

### Options

| Flag | Description |
|------|-------------|
| `--teams NAME [NAME ...]` | Process only the specified team(s) |
| `--dpi N` | Render resolution (default: 300) |

Examples:

```bash
# Default run
poetry run python pipelines/kt-app/steps/4_extract_card_images.py

# Single team at higher DPI
poetry run python pipelines/kt-app/steps/4_extract_card_images.py --teams kommandos --dpi 400
```

---

## Processing Steps

### 1. Load structure.json

Reads `layers/kt-app/classified/{team}/structure.json` to enumerate all cards, their front/back page paths, and their names.

### 2. Render PDF Pages to JPEG

For each front page and back page, PyMuPDF renders the PDF at the specified DPI (default: 300). The rendered image is saved as JPEG with quality 90.

**JPEG quality 90** is chosen as a balance between visual fidelity and file size. At 300 DPI, quality 90 produces files approximately 3.5x smaller than equivalent PNGs with negligible visible quality loss for card images.

### 3. Apply Default Backsides

If a card has no back page in the source PDF (i.e., `backs` is empty in structure.json), the appropriate default backside image is copied as the back:

- Portrait cards → `config/defaults/card-backside/default-backside-portrait.jpg`
- Landscape cards → `config/defaults/card-backside/default-backside-landscape.jpg`

**Team-specific overrides**: If `config/teams/{team}/card-backside/` contains a matching backside file for the team, it is used in preference to the default.

### 4. Naming Convention

Output filenames follow different conventions by card type:

**Datacards** — named by operative name only:
```
Kommando Boy-front.jpg
Kommando Boy-back.jpg
```

**All other card types** — prefixed with `{team}-{card-name}`:
```
kommandos-faction-rules-front.jpg
kommandos-faction-rules-back.jpg
kommandos-take-em-down-front.jpg
kommandos-take-em-down-back.jpg
```

---

## Output Structure

```
output/kommandos/cards/
├── datacards/
│   ├── Kommando Boy-front.jpg
│   ├── Kommando Boy-back.jpg
│   ├── Kommando Nob-front.jpg
│   ├── Kommando Nob-back.jpg
│   └── ...
├── faction-rules/
│   ├── kommandos-faction-rules-front.jpg
│   └── kommandos-faction-rules-back.jpg
├── equipment/
│   ├── kommandos-stikkbomb-front.jpg
│   └── kommandos-stikkbomb-back.jpg
└── strategy-ploys/
    └── ...
```

---

## Configuration

### Default Backsides

| File | Used For |
|------|----------|
| `config/defaults/card-backside/default-backside-portrait.jpg` | Portrait cards with no source back |
| `config/defaults/card-backside/default-backside-landscape.jpg` | Landscape cards with no source back |

### Team-Specific Backsides

Place override files in `config/teams/{team}/card-backside/`. The step checks this directory first and falls back to the defaults if no team-specific file is found.

---

## Error Handling

- **Missing PDF page**: Warning logged; card is skipped
- **Corrupt PDF**: Error logged; card is skipped; processing continues for remaining cards
- **Missing output directory**: Created automatically

---

**Last Updated**: May 17, 2026
