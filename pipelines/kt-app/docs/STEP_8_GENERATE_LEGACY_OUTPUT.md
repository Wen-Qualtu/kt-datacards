# Step 8: Generate Legacy Output

> **This is a temporary compatibility step.** It exists solely to keep the old `output_v2/` and `tts_objects/` structures up to date for TTS boxes that have not yet migrated to the current `output/` format. This step will be removed when `output_v2/` is fully deprecated.

---

## Purpose

Read the canonical output from `output/{team}/` and mirror it into the legacy directory structures (`output_v2/` and `tts_objects/`) using the old naming conventions and URL schemes. Does not modify `output/` in any way.

---

## Script

`pipelines/kt-app/steps/8_generate_legacy_output.py`

---

## Input

| Path | Description |
|------|-------------|
| `output/{team}/cards/{card_type}/*.jpg` | Card images produced by Step 4 |
| `output/{team}/tts_objects/{Name} Box.json` | TTS save files produced by Step 7 |
| `config/team-config.yaml` | Team slug, display name, and faction |

---

## Output

| Path | Description |
|------|-------------|
| `output_v2/{faction}/{team}/{legacy-type}/` | Card images with legacy naming |
| `tts_objects/{team}/{Name} Cards.json` | TTS save files with legacy URLs |
| `output_v2/datacards-urls.json` | Flat array of all legacy datacard image URLs |
| `output_v2/tts-card-boxes.json` | Index of all teams and their legacy TTS object URLs |

---

## Execution

```bash
poetry run python pipelines/kt-app/steps/8_generate_legacy_output.py
```

This step has no `--force` or incremental tracking — it runs fully every time and rebuilds all legacy output from scratch.

### Options

| Flag | Description |
|------|-------------|
| `--teams NAME [NAME ...]` | Process only the specified team(s) |

---

## Processing Steps

### 1. Mirror Card Images to output_v2

For each team and card type, card images are copied from `output/{team}/cards/{card_type}/` to `output_v2/{faction}/{team}/{legacy-type}/` with legacy filename conventions.

**Card type name mapping:**

| New name | Legacy name |
|----------|-------------|
| `operatives-selection` | `operatives` |
| `token-guide` | `faction-rules` (with `markertoken-guide` filename prefix) |
| All others | Same name |

**Filename convention:**

New format: `{name}-{front|back}.jpg`
Legacy format: `{team}-{name}_{front|back}.jpg`

Example:
- New: `output/kommandos/cards/datacards/Kommando Boy-front.jpg`
- Legacy: `output_v2/xenos/kommandos/datacards/kommandos-Kommando Boy_front.jpg`

### 2. Rewrite TTS JSON URLs

For each team's TTS save file in `output/{team}/tts_objects/`, the JSON is read and all embedded GitHub raw URLs are rewritten to point to the `output_v2/` path structure.

URL rewriting:
- Input URL pattern: `.../output/{team}/cards/{card_type}/{name}-{side}.jpg`
- Output URL pattern: `.../output_v2/{faction}/{team}/{legacy-type}/{team}-{name}_{side}.jpg`

The rewritten JSON is written to `tts_objects/{team}/{Name} Cards.json`.

Note the filename difference:
- New: `{Team Name} Box.json`
- Legacy: `{Team Name} Cards.json`

### 3. Rebuild datacards-urls.json

`output_v2/datacards-urls.json` is a flat JSON array of all legacy datacard image URLs across all teams. It is rebuilt from scratch from the set of files written to `output_v2/`.

### 4. Rebuild tts-card-boxes.json

`output_v2/tts-card-boxes.json` is a JSON object mapping team slugs to their legacy TTS save file URLs. It is rebuilt from scratch.

---

## Legacy Directory Structure

```
output_v2/
├── xenos/
│   └── kommandos/
│       ├── datacards/
│       │   ├── kommandos-Kommando Boy_front.jpg
│       │   ├── kommandos-Kommando Boy_back.jpg
│       │   └── ...
│       ├── faction-rules/
│       │   ├── kommandos-faction-rules_front.jpg
│       │   ├── kommandos-faction-rules_back.jpg
│       │   └── kommandos-markertoken-guide_front.jpg
│       └── ...
├── imperium/
├── chaos/
├── datacards-urls.json
└── tts-card-boxes.json

tts_objects/
└── kommandos/
    └── Kommandos Cards.json
```

---

## Deprecation Plan

Step 8 and the `output_v2/` structure will be removed when:

1. All active TTS save files have been updated to reference `output/` URLs directly
2. The legacy `tts_objects/` save files at the repo root are no longer in use
3. `output_v2/` has been confirmed safe to delete

At that point, delete:
- `pipelines/kt-app/steps/8_generate_legacy_output.py`
- `output_v2/`
- `tts_objects/`
- This documentation file

---

**Last Updated**: May 17, 2026
