# Step 2: Classify Structure

## Purpose

Read single-page PDFs from `layers/kt-app/extracted/`, determine whether each page is a card front or back, pair fronts with their corresponding backs, extract operative names from datacard fronts, and write the resulting structure to `layers/kt-app/classified/{team}/structure.json`. This JSON file is the primary artifact consumed by all subsequent steps.

---

## Script

`pipelines/kt-app/steps/2_classify_structure.py`

---

## Input

- **Directory**: `layers/kt-app/extracted/{team}/cards/{type}/`
- **Files**: Single-page PDFs produced by Step 1 (e.g. `kommandos-datacards-page_1.pdf`)
- **Config**: `config/team-config.yaml`

---

## Output

| Path | Description |
|------|-------------|
| `layers/kt-app/classified/{team}/structure.json` | Full card structure with front/back pairs and operative names |

---

## Execution

```bash
poetry run python pipelines/kt-app/steps/2_classify_structure.py
```

### Options

| Flag | Description |
|------|-------------|
| `--teams NAME [NAME ...]` | Process only the specified team(s) |

---

## Processing Steps

### 1. Read Single-Page PDFs

For each team and card type, all single-page PDFs from `layers/kt-app/extracted/{team}/cards/{type}/` are loaded and sorted in page order.

### 2. Classify Front vs. Back

Each PDF page is analyzed to determine whether it is a card front or a card back. Classification is based on the content of the PDF's text layer and/or visual layout:

- **Front pages** contain operative names, stat blocks, or rules content
- **Back pages** contain continuation content (additional abilities or weapons) or a generic back design

**Orientations:**
- **Portrait pages** are typically single-sided — they represent standalone cards with no back
- **Landscape pages** are typically double-sided — alternating pages form front/back pairs

### 3. Pair Fronts and Backs

Pages are grouped into card entities. Each entity represents one card (or one operative, for datacards) and may contain:

- A single front page (no back)
- A front page and one or more back pages

For datacards, an operative with extensive stat lines or many abilities may span more than two pages; all such pages are grouped under the same entity.

### 4. Extract Operative Names

For `datacards` card type, the operative name is extracted from the text layer of the front page. This name is used as the canonical identifier for the card in all downstream steps.

For other card types, a card name is derived from the PDF filename or content.

### 5. Write structure.json

The completed structure is written to `layers/kt-app/classified/{team}/structure.json`.

---

## structure.json Format

```json
{
  "team": "kommandos",
  "card_types": {
    "datacards": [
      {
        "name": "Kommando Boy",
        "front": "kommandos-datacards-page_1.pdf",
        "backs": ["kommandos-datacards-page_2.pdf"]
      },
      {
        "name": "Kommando Nob",
        "front": "kommandos-datacards-page_3.pdf",
        "backs": []
      }
    ],
    "faction-rules": [
      {
        "name": "kommandos-faction-rules",
        "front": "kommandos-faction-rules-page_1.pdf",
        "backs": ["kommandos-faction-rules-page_2.pdf"]
      }
    ]
  }
}
```

Each entry in a card type list includes:
- `name`: the operative name (datacards) or card identifier (other types)
- `front`: path to the front-page PDF (relative to the extracted directory)
- `backs`: list of back-page PDF paths (empty list if single-sided)

---

## Card Layout Handling

### Single-Sided (Portrait)

Portrait-orientation pages are treated as front-only cards. No back pairing is performed. These are used for faction-rules, equipment, ploys, and token-guide cards.

### Double-Sided (Landscape)

Landscape-orientation pages are treated as front/back pairs. The front and back for each operative are identified from the page sequence and content classification.

---

## Error Handling

- **No PDFs found for a team/type**: Logged as a warning; other types continue
- **Classification ambiguity**: Logged; the page is assigned to front by default
- **Duplicate operative names**: A suffix (e.g. `_2`) is appended to ensure uniqueness
- **Missing team in config**: Logged as an error; team is skipped

---

**Last Updated**: May 17, 2026
