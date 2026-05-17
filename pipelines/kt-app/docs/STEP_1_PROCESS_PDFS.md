# Step 1: Process PDFs

## Purpose

Scan the `input/` directory for Kill Team app PDF exports, identify which team each PDF belongs to, classify it by card type, copy it to `layers/kt-app/processed/`, and split it into single-page PDFs in `layers/kt-app/extracted/`. Unchanged PDFs are skipped using hash-based change detection.

---

## Script

`pipelines/kt-app/steps/1_process_pdfs.py`

---

## Input

- **Directory**: `input/` (searched recursively)
- **Files**: `*.pdf` — PDF exports from the Kill Team mobile app

---

## Output

| Path | Description |
|------|-------------|
| `layers/kt-app/processed/{team}/{team}-{type}.pdf` | Classified source PDF, renamed to canonical form |
| `layers/kt-app/extracted/{team}/cards/{type}/{team}-{type}-page_N.pdf` | Individual single-page PDFs |
| `layers/kt-app/metadata.json` | Per-file SHA hashes for change detection |

---

## Execution

```bash
poetry run python pipelines/kt-app/steps/1_process_pdfs.py
```

### Options

| Flag | Description |
|------|-------------|
| `--teams NAME [NAME ...]` | Process only the specified team(s) by slug |
| `--force` | Re-process all PDFs, ignoring cached hashes |

Examples:

```bash
# Process all PDFs
poetry run python pipelines/kt-app/steps/1_process_pdfs.py

# Process only two teams
poetry run python pipelines/kt-app/steps/1_process_pdfs.py --teams kommandos pathfinders

# Force re-process everything
poetry run python pipelines/kt-app/steps/1_process_pdfs.py --force
```

---

## Processing Steps

### 1. Discover PDFs

Recursively scans `input/` for all `*.pdf` files.

### 2. Hash-Based Change Detection

For each discovered PDF, a SHA hash is computed and compared against the record in `layers/kt-app/metadata.json`. If the hash matches the stored value and `--force` is not set, the PDF is skipped.

Updated hashes are written back to `metadata.json` after processing.

### 3. Identify Team

The PDF filename is matched against team entries in `config/team-config.yaml`. Each team entry has a canonical name and a list of aliases. Matching is case-insensitive and normalizes separators.

If no team match is found, the PDF is logged as unrecognized and skipped.

### 4. Classify Card Type

The filename is also matched against known card type keywords to determine what kind of PDF it is:

| Card Type | Description |
|-----------|-------------|
| `datacards` | Operative stat cards |
| `faction-rules` | Faction-specific rules |
| `token-guide` | Token reference guide |
| `operatives-selection` | Operative selection reference |
| `equipment` | Equipment cards |
| `strategy-ploys` | Strategic ploys |
| `firefight-ploys` | Firefight tactical ploys |

If the type cannot be determined from the filename, the PDF is logged and skipped.

### 5. Copy to Processed

The source PDF is copied to:

```
layers/kt-app/processed/{team}/{team}-{type}.pdf
```

This provides a clean, canonically named copy of the source regardless of the original filename.

### 6. Split into Single-Page PDFs

Using PyMuPDF, each page of the processed PDF is written out as a separate single-page PDF:

```
layers/kt-app/extracted/{team}/cards/{type}/{team}-{type}-page_1.pdf
layers/kt-app/extracted/{team}/cards/{type}/{team}-{type}-page_2.pdf
...
```

Single-page PDFs are the unit of work for all downstream steps.

---

## Output Structure

```
layers/kt-app/
├── metadata.json
├── processed/
│   └── kommandos/
│       ├── kommandos-datacards.pdf
│       ├── kommandos-faction-rules.pdf
│       └── ...
└── extracted/
    └── kommandos/
        └── cards/
            ├── datacards/
            │   ├── kommandos-datacards-page_1.pdf
            │   ├── kommandos-datacards-page_2.pdf
            │   └── ...
            └── faction-rules/
                ├── kommandos-faction-rules-page_1.pdf
                └── ...
```

---

## Configuration

### `config/team-config.yaml`

Defines all known teams with:
- `slug`: canonical kebab-case identifier (used as folder name)
- `name`: display name
- `aliases`: list of alternate name patterns used to match filenames

Example entry:
```yaml
- slug: kommandos
  name: Kommandos
  faction: xenos
  aliases:
    - kommando
    - ork kommandos
```

---

## Error Handling

- **Unrecognized team**: PDF is skipped; warning logged with the filename
- **Unrecognized type**: PDF is skipped; warning logged
- **Corrupt PDF**: Logged as an error; remaining PDFs continue to process
- **Missing input directory**: Script exits with an error

---

**Last Updated**: May 17, 2026
