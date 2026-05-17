# kt-app Pipeline Overview

## Purpose

Process Kill Team datacards from PDFs exported out of the **Kill Team mobile app**. The pipeline takes raw app exports from the `input/` folder and produces card images, token images, cardbox meshes, operative stat data, and TTS-ready JSON objects in `output/{team}/`.

---

## Pipeline Steps

| Step | Script | Purpose | Key Input | Key Output |
|------|--------|---------|-----------|------------|
| **1** | `1_process_pdfs.py` | Identify, classify, and split PDFs | `input/*.pdf` | `layers/kt-app/processed/`, `layers/kt-app/extracted/` |
| **2** | `2_classify_structure.py` | Pair front/back pages, extract operative names | `layers/kt-app/extracted/` | `layers/kt-app/classified/{team}/structure.json` |
| **3** | `3_extract_team_data.py` | Extract operative stats and ability text | `layers/kt-app/classified/` | `output/{team}/data/{team}-team-data.json` |
| **4** | `4_extract_card_images.py` | Render PDF pages to JPEG card images | `layers/kt-app/classified/` | `output/{team}/cards/{card_type}/*.jpg` |
| **5** | `5_extract_tokens.py` | Extract token images with transparency | Team PDFs | `output/{team}/tokens/*.png` |
| **6** | `6_generate_tts_assets.py` | Generate cardbox 3D mesh and texture | Config + icons | `output/{team}/cardbox/` |
| **7** | `7_generate_tts_objects.py` | Generate TTS save file JSON | `output/{team}/` | `output/{team}/tts_objects/{Name} Box.json` |
| **8** | `8_generate_legacy_output.py` | **Legacy only.** Mirror output to `output_v2/` and `tts_objects/` | `output/{team}/` | `output_v2/`, `tts_objects/` |

Step 8 is a temporary compatibility step that will be removed when `output_v2/` is fully deprecated.

---

## Running the Pipeline

### Prerequisites

```bash
poetry install
```

### Run Individual Steps

Each step is an independent script and can be run on its own:

```bash
poetry run python pipelines/kt-app/steps/1_process_pdfs.py
poetry run python pipelines/kt-app/steps/2_classify_structure.py
poetry run python pipelines/kt-app/steps/3_extract_team_data.py
poetry run python pipelines/kt-app/steps/4_extract_card_images.py
poetry run python pipelines/kt-app/steps/5_extract_tokens.py
poetry run python pipelines/kt-app/steps/6_generate_tts_assets.py
poetry run python pipelines/kt-app/steps/7_generate_tts_objects.py
poetry run python pipelines/kt-app/steps/8_generate_legacy_output.py
```

Steps are designed to be run in sequence (1 through 7), but each carries its own metadata so they can be re-run individually when needed. For example, if only card images changed, re-run Steps 4 and 7 without re-running Steps 1-3.

### Process Specific Teams

Most steps accept a `--teams` flag to limit processing to one or more teams:

```bash
poetry run python pipelines/kt-app/steps/1_process_pdfs.py --teams kommandos pathfinders
poetry run python pipelines/kt-app/steps/4_extract_card_images.py --teams kommandos
```

### Force Re-processing

Use `--force` to bypass hash-based change detection and reprocess all files:

```bash
poetry run python pipelines/kt-app/steps/1_process_pdfs.py --force
```

---

## Intermediate Directory Structure (`layers/kt-app/`)

```
layers/kt-app/
├── metadata.json                          # Hash-based change detection (Step 1)
├── processed/
│   └── {team}/
│       ├── {team}-datacards.pdf
│       ├── {team}-faction-rules.pdf
│       ├── {team}-equipment.pdf
│       └── ...
├── extracted/
│   └── {team}/
│       └── cards/
│           ├── datacards/
│           │   ├── {team}-datacards-page_1.pdf
│           │   ├── {team}-datacards-page_2.pdf
│           │   └── ...
│           ├── faction-rules/
│           ├── equipment/
│           └── ...
└── classified/
    └── {team}/
        ├── structure.json                 # Card structure with front/back pairs
        └── cards/
            ├── datacards/
            │   ├── {operative-name}-front.pdf
            │   ├── {operative-name}-back.pdf
            │   └── ...
            └── ...
```

---

## Key Concepts

### Hash-Based Change Detection

Step 1 records a SHA hash for each input PDF in `layers/kt-app/metadata.json`. On subsequent runs, unchanged PDFs are skipped. Use `--force` to override.

### Card Types

| Type | Description | Orientation |
|------|-------------|-------------|
| `datacards` | Per-operative stat cards | Landscape |
| `faction-rules` | Faction-specific rules | Portrait |
| `token-guide` | Token reference guide | Portrait |
| `operatives-selection` | Operative selection reference | Portrait |
| `equipment` | Equipment cards | Portrait |
| `strategy-ploys` | Strategic ploys | Portrait |
| `firefight-ploys` | Firefight tactical ploys | Portrait |

### structure.json

The key intermediate artifact produced by Step 2. It describes all cards for a team — which pages are fronts, which are backs, operative names, and card type groupings. All subsequent steps read from this file.

### GitHub Raw URL Hosting

TTS JSON objects reference GitHub raw URLs pointing to the `main` branch. Files committed to `main` are immediately accessible to TTS without any separate deployment step.

---

## Legacy Compatibility (Step 8)

Step 8 exists solely to keep the old `output_v2/{faction}/{team}/` structure and `tts_objects/{team}/` location populated for TTS boxes that have not yet migrated to the `output/` format. It:

- Reads from `output/{team}/` (never modifies it)
- Copies card images with legacy naming conventions to `output_v2/`
- Rewrites TTS JSON URLs to point at `output_v2/` paths and writes to `tts_objects/`
- Rebuilds `output_v2/datacards-urls.json` and `output_v2/tts-card-boxes.json`

This step will be removed once the legacy structures are deprecated.

---

## Documentation

- [STEP_1_PROCESS_PDFS.md](STEP_1_PROCESS_PDFS.md) — PDF identification, classification, and splitting
- [STEP_2_CLASSIFY_STRUCTURE.md](STEP_2_CLASSIFY_STRUCTURE.md) — Front/back pairing and structure.json
- [STEP_3_EXTRACT_TEAM_DATA.md](STEP_3_EXTRACT_TEAM_DATA.md) — Operative stats extraction
- [STEP_4_EXTRACT_CARD_IMAGES.md](STEP_4_EXTRACT_CARD_IMAGES.md) — PDF-to-JPEG rendering
- [STEP_5_EXTRACT_TOKENS.md](STEP_5_EXTRACT_TOKENS.md) — Token image extraction
- [STEP_6_GENERATE_TTS_ASSETS.md](STEP_6_GENERATE_TTS_ASSETS.md) — Cardbox mesh and texture
- [STEP_7_GENERATE_TTS_OBJECTS.md](STEP_7_GENERATE_TTS_OBJECTS.md) — TTS save file generation
- [STEP_8_GENERATE_LEGACY_OUTPUT.md](STEP_8_GENERATE_LEGACY_OUTPUT.md) — Legacy output maintenance

---

**Last Updated**: May 17, 2026
