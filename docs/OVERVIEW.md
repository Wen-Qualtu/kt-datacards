# Kill Team Datacards: Project Overview

## What This Project Does

This project automates converting Warhammer 40,000: Kill Team datacards into assets for a Tabletop Simulator (TTS) mod. It takes PDF source files — either exported from the official Kill Team mobile app or scraped from Warhammer Community — and produces card images, token images, 3D cardbox meshes, and TTS-ready JSON objects that can be loaded directly into a TTS game.

The outputs are committed to the `main` branch of this repository. GitHub raw URLs serve the image files directly to TTS at runtime; no separate hosting infrastructure is needed.

---

## Two Pipelines

### kt-app Pipeline (`pipelines/kt-app/`)

Processes PDFs exported from the **Kill Team mobile app**. This is the primary pipeline for up-to-date content.

- 8 steps (Steps 1-7 produce output; Step 8 is a legacy compatibility step)
- Outputs to `output/{team}/`
- Also maintains `output_v2/` and `tts_objects/` for legacy TTS boxes (Step 8 only)

Use this pipeline when:
- You have fresh PDFs exported from the Kill Team app
- You need to update operative stats, card images, or TTS objects

See: [pipelines/kt-app/docs/PIPELINE_OVERVIEW.md](../pipelines/kt-app/docs/PIPELINE_OVERVIEW.md)

### warcom Pipeline (`pipelines/warcom/`)

Processes PDFs scraped from the **Warhammer Community website**. Useful for bulk downloads when app exports are unavailable.

- 5 steps
- Outputs to `output/{team}/`

Use this pipeline when:
- You want to scrape the full set of PDFs directly from warcom
- The app pipeline is unavailable or impractical

See: [pipelines/warcom/docs/PIPELINE_OVERVIEW.md](../pipelines/warcom/docs/PIPELINE_OVERVIEW.md)

---

## Output Structure

Both pipelines write to the same flat `output/` structure:

```
output/
├── {team}/
│   ├── cards/
│   │   ├── datacards/
│   │   │   ├── {operative-name}-front.jpg
│   │   │   └── {operative-name}-back.jpg
│   │   ├── equipment/
│   │   ├── faction-rules/
│   │   ├── firefight-ploys/
│   │   ├── operatives-selection/
│   │   ├── strategy-ploys/
│   │   └── token-guide/
│   ├── tokens/
│   │   └── {team}-{token-name}.png
│   ├── cardbox/
│   │   ├── {team}-card-box.obj
│   │   └── {team}-card-box-texture.jpg
│   ├── data/
│   │   └── {team}-team-data.json
│   └── tts_objects/
│       └── {Team Name} Box.json
└── object-urls.json
```

Teams are identified by a kebab-case slug (e.g. `kommandos`, `angels-of-death`). The `output/` folder is flat by team slug — there is no faction subdirectory at this level.

**The `output/` folder structure is immutable.** TTS cards reference exact GitHub raw URLs. Never rename, restructure, or move files in `output/` — only add new files or update existing ones.

---

## Legacy Compatibility

### `output_v2/`

An older output structure organized as `output_v2/{faction}/{team}/`. Still maintained by kt-app Step 8 for TTS boxes that have not yet been updated to the new `output/` format.

- Card images use a different naming convention
- Contains its own URL index files (`datacards-urls.json`, `tts-card-boxes.json`)
- **Will be deprecated and removed** once all active TTS boxes have migrated to `output/`

### `tts_objects/`

Legacy TTS save file location at the repo root, organized as `tts_objects/{team}/`. Also maintained by kt-app Step 8.

- Contains rewritten TTS JSON files pointing to `output_v2/` URLs
- **Will be deprecated** alongside `output_v2/`

Neither `output_v2/` nor `tts_objects/` should be written to directly — Step 8 derives their content from `output/` automatically.

---

## Team Configuration

All team metadata lives in `config/team-config.yaml`. This file defines:

- **Canonical team slug** (kebab-case, used as folder name in `output/`)
- **Display name** (used in TTS object names and box textures)
- **Faction** (`imperium`, `chaos`, or `xenos`)
- **Aliases** (alternate names used during PDF identification)
- **Token shapes** per token (round, diamond, octagon, operative silhouette)

Both pipelines read this file to identify which team a PDF belongs to and to look up display names for TTS output.

---

## GitHub Raw URL Hosting

Files committed to the `main` branch are publicly accessible via:

```
https://raw.githubusercontent.com/{owner}/{repo}/main/{path}
```

TTS JSON objects embed these URLs directly for card face images, token textures, cardbox meshes, and scripts. When a new team is processed and committed to `main`, TTS can immediately load the assets by URL — no deployment step required.

The `output/object-urls.json` file is a flat index of all hosted object URLs, used by the TTS update Lua script to discover and spawn new content.

---

## Repository Folder Map

```
kt-datacards/
├── config/
│   ├── team-config.yaml               # All team metadata and aliases
│   ├── defaults/
│   │   ├── card-backside/             # Default card back images
│   │   └── tts-script/                # Default Lua scripts
│   ├── pipelines/
│   │   └── warcom/                    # warcom extraction templates
│   └── teams/{team}/                  # Per-team overrides (icon, box art, backsides)
├── docs/                              # Project-level documentation
├── input/                             # Drop PDFs here for kt-app pipeline
├── layers/
│   ├── kt-app/                        # kt-app intermediate files
│   │   ├── metadata.json              # Hash-based change detection
│   │   ├── processed/{team}/          # Classified source PDFs
│   │   ├── extracted/{team}/          # Single-page PDFs
│   │   └── classified/{team}/         # structure.json + classified PDFs
│   └── warcom/                        # warcom intermediate files
│       ├── staging/                   # Downloaded source PDFs
│       └── extracted/{team}/          # Extracted cards and tokens
├── output/                            # Final output (both pipelines) — immutable structure
├── output_v2/                         # Legacy output (maintained by kt-app Step 8)
├── pipelines/
│   ├── kt-app/
│   │   ├── docs/                      # kt-app pipeline documentation
│   │   ├── steps/                     # Step scripts 1-8
│   │   └── utils/                     # Shared utilities
│   └── warcom/
│       ├── docs/                      # warcom pipeline documentation
│       ├── pdf_process_pipeline.py    # Main orchestrator
│       └── steps/                     # Step scripts 1-5
├── tts_objects/                       # Legacy TTS save files (maintained by kt-app Step 8)
└── tools/                             # Standalone utility scripts
```

---

## Tech Stack

| Package | Purpose |
|---------|---------|
| Python 3.11+ | Runtime |
| Poetry | Dependency management |
| PyMuPDF (`fitz`) | PDF rendering and text extraction |
| OpenCV (`cv2`) | Image processing and contour detection |
| Pillow | Image compositing and format conversion |
| PyYAML | Configuration file parsing |

---

**Last Updated**: May 17, 2026
