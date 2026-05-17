# Step 3: Extract Team Data

## Purpose

Extract structured operative stat data from classified datacard PDFs. For each team, reads the PDF text layer to pull out operative stats (APL, movement, wounds, save, weapons, abilities) and produces a `{team}-team-data.json` file. Also extracts names and content from other card types for use as GMNotes in TTS objects.

---

## Script

`pipelines/kt-app/steps/3_extract_team_data.py`

---

## Input

| Path | Description |
|------|-------------|
| `layers/kt-app/classified/{team}/structure.json` | Card structure from Step 2 |
| `layers/kt-app/extracted/{team}/cards/datacards/*.pdf` | Single-page datacard PDFs |
| `layers/kt-app/extracted/{team}/cards/{type}/*.pdf` | Other card type PDFs (for GMNotes content) |

---

## Output

| Path | Description |
|------|-------------|
| `output/{team}/data/{team}-team-data.json` | Structured operative stats and card content |

---

## Execution

```bash
poetry run python pipelines/kt-app/steps/3_extract_team_data.py
```

### Options

| Flag | Description |
|------|-------------|
| `--teams NAME [NAME ...]` | Process only the specified team(s) |

---

## Processing Steps

### 1. Load structure.json

Reads `layers/kt-app/classified/{team}/structure.json` to get the list of operatives and their front/back PDF paths.

### 2. Extract Operative Stats from Datacards

For each operative's front page, the PDF text layer is read using PyMuPDF. The following stat fields are extracted:

| Field | Description |
|-------|-------------|
| `name` | Operative name |
| `apl` | Action Point Limit |
| `movement` | Movement value (in inches) |
| `wounds` | Wound count |
| `save` | Save characteristic (e.g. `3+`) |
| `weapons` | List of weapons with profiles (range, attacks, hit, wound, rend, damage) |
| `abilities` | Operative abilities (name + rules text) |
| `keywords` | Keyword list |

For operatives with multiple back pages, stats may continue across pages. All pages for an operative are read and their content merged.

### 3. Extract Content from Other Card Types

For non-datacard card types (faction-rules, strategy-ploys, firefight-ploys, equipment), the text content is extracted and stored under the card name. This content is used to populate GMNotes fields in the TTS JSON objects (Step 7), enabling stat display on hover in-game.

### 4. Write team-data.json

All extracted data is serialized to `output/{team}/data/{team}-team-data.json`.

---

## Output Format

```json
{
  "team": "kommandos",
  "operatives": [
    {
      "name": "Kommando Boy",
      "apl": 2,
      "movement": 3,
      "wounds": 8,
      "save": "4+",
      "weapons": [
        {
          "name": "Slugga",
          "profiles": [
            {
              "range": "6",
              "attacks": 4,
              "hit": "4+",
              "wound": "4+",
              "rend": 0,
              "damage": "3/4"
            }
          ]
        }
      ],
      "abilities": [
        {
          "name": "Sneaky Gitz",
          "text": "While this operative is..."
        }
      ],
      "keywords": ["INFANTRY", "KOMMANDOS"]
    }
  ],
  "cards": {
    "strategy-ploys": [
      {
        "name": "Take 'em Down!",
        "text": "Use this Strategic Ploy..."
      }
    ]
  }
}
```

---

## Downstream Use

`team-data.json` is consumed by Step 7 (`7_generate_tts_objects.py`) to:

- Embed operative stats into the `GMNotes` field of TTS card objects (enables stat display on hover)
- Generate Lua script data tables for interactive stat card displays

---

## Error Handling

- **Missing structure.json**: Step logs an error and skips the team
- **Unparseable stat line**: Field is set to `null` and a warning is logged; processing continues
- **Missing operative PDF**: Warning logged; operative is included with null stats
- **Encoding issues in PDF text**: Characters are normalized; unrecognized symbols are replaced

---

**Last Updated**: May 17, 2026
