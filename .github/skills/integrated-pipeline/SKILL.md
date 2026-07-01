---
name: integrated-pipeline
description: 'Understand and work with the integrated kt-datacards pipeline under new_implementation/ (the merged kt-app + warcom tracks). USE WHEN: running or debugging the new pipeline; asking where artwork/icons/classified PDFs/content/metadata live; editing pipeline steps or paths.py; adding a team; understanding the layers/integration per-team layout; wiring the --source kt-app|warcom track selector. This is the refactor sandbox, NOT the production script/ or pipelines/ tracks. DO NOT USE FOR: the legacy production pipeline in script/ or the warcom/kt-app pipelines under pipelines/.'
---

# Integrated Pipeline (new_implementation/)

The `new_implementation/` sandbox is the merged pipeline: two extraction front-ends
(`kt-app` and `warcom`) that converge on a single **source-agnostic integration layer**.
Everything is self-contained under `new_implementation/` and detached from the production
pipelines at the repo root (`script/`, `pipelines/`).

## When to Use
- Running or debugging the new pipeline (`python -m pipeline.main ...`).
- Locating outputs: artwork, icons, classified PDFs, content maps, metadata.
- Editing a step in `pipeline/steps/` or a path helper in `pipeline/utils/paths.py`.
- Onboarding on another machine / continuing work in a fresh clone.

## Layer Layout (source of truth: `pipeline/utils/paths.py`)

```
new_implementation/
  input/                          raw PDFs for the kt-app track (UUID-named)
  layers/
    {track}/                      track = kt-app | warcom  (GITIGNORED — reproducible)
      staging/                    warcom scrape target ({team}-datacards.pdf)
      extracted/                  per-card split PDFs
      structure/{team}-structure.json
    integration/                  SHARED, source-agnostic merge point (COMMITTED)
      pipeline-state.json         global index: teams -> state path + last_updated, last_run
      {team}/                     one folder per team
        {team}-{type}-{name}.pdf  classified single-card PDFs (no -front/-back postfix)
        manifest.json             entity grouping (copy of structure manifest)
        content/{team}-content.json
        {team}-pipeline-state.json step completion + output hashes (change detection)
        artwork/                  lore art jpegs + {team}-artwork-metadata.json
          icons/                  token, token-transparent, portrait, landscape
  output/{team}/...               final assets (cards, tokens, dice, cardbox, data)
```

Key facts:
- **Per-team** integration folders. Each team's run state (step completion + output
  hashes) lives in `{team}/{team}-pipeline-state.json` — rewritten wholly per run, so
  there are no stale cross-team keys. A global `pipeline-state.json` at the integration
  root is a *derived* index (teams -> state path + `last_updated`, plus `last_run`),
  rebuilt by scanning the per-team files so it too is stale-key free.
- `layers/kt-app/` and `layers/warcom/` are **gitignored** (reproducible staging/extract).
  `layers/integration/**` and `output/**` **are committed**.
- Icons are **byte-identical** across both tracks by design. warcom additionally emits
  page-0 portrait/landscape backside icons; kt-app does not.
- warcom emits some lore art slots as `.png` (alpha) rather than `.jpeg` — expected.

### paths.py helpers (use these, never hardcode)
| Helper | Returns |
|--------|---------|
| `INTEGRATION` | `layers/integration` |
| `PIPELINE_STATE_INDEX` | `layers/integration/pipeline-state.json` (global index) |
| `integration_team_dir(team)` | `layers/integration/{team}` |
| `classified_file(team, type, name)` | `.../{team}-{type}-{name}.pdf` |
| `integration_manifest_file(team)` | `.../{team}/manifest.json` |
| `content_dir(team)` / `content_file(team)` | `.../{team}/content[/{team}-content.json]` |
| `artwork_team_dir(team)` | `.../{team}/artwork` (icons in `artwork/icons/`) |
| `pipeline_state_file(team)` | `.../{team}/{team}-pipeline-state.json` |
| `track_dir` / `staging_dir` / `extracted_dir` / `structure_dir` / `structure_file` | per-track layers |
| `team_output(team)` | `output/{team}` |

There are **no** `SHARED`, `ARTWORK`, `CONTENT`, or `INTEGRATION_MANIFESTS` constants
(removed in the shared→integration rename). Config still reads from the repo root:
`REPO_ROOT/config/team-config.yaml` via `paths.TEAM_CONFIG`.

## Running the Pipeline

Always run from the `new_implementation/` directory (the PowerShell cwd resets to the repo
root between commands — prefix with `Set-Location C:\git\kt-datacards\new_implementation`).

```powershell
# full run for one track
python -m pipeline.main --source kt-app --teams kasrkin

# single step (comma-separated teams; NO spaces)
python -m pipeline.main --step extract_artwork --source warcom --teams kasrkin,mandrakes --force

# range of steps
python -m pipeline.main --source kt-app --from build_structure --to content_analysis --teams kasrkin

# list steps
python -m pipeline.main --list
```

Flags: `--source kt-app|warcom` (required for front-end/source steps), `--teams a,b`
(comma-separated, default all), `--step`, `--from`/`--to`, `--force` (ignore caches).

## Step Order & Scope (`pipeline/main.py` → `STEP_ORDER`)

| # | Step | Scope | Reads → Writes |
|---|------|-------|----------------|
| 1 | `front_end` | track | raw source → `layers/{track}/extracted` (via `track_kt_app` / `track_warcom`) |
| 2 | `extract_artwork` | source | raw source → `integration/{team}/artwork/{,icons}` |
| 3 | `build_structure` | source | extracted → `layers/{track}/structure/{team}-structure.json` |
| 4 | `integrate_classified` | source | extracted + structure → `integration/{team}/*.pdf` + `manifest.json` |
| 5 | `content_analysis` | shared | integration PDFs + manifest → `integration/{team}/content/*.json` + per-team `{team}-pipeline-state.json` + global `pipeline-state.json` index |
| 6 | `extract_backsides` | shared | artwork → `output/{team}/card-backside/*` |
| 7 | `extract_tokens` | shared | content + artwork → `output/{team}/tokens/*.png` |
| 8 | `generate_dice` | shared | artwork + config → `output/{team}/dice/*` |
| 9 | `generate_box_texture` | shared | artwork + config → `output/{team}/cardbox/*` |
| 10 | `generate_card_images` | shared | integration PDFs + backsides + content → `output/{team}/cards/*` |
| 11 | `extract_stats` | shared | content → `output/{team}/data/{team}-team-data.json` |
| 12 | `generate_tts` | shared | all of the above → TTS objects |

Scope meaning: **track** = front-end resolved by `--source`; **source** = shared code that
still needs the raw/track input (takes `--source`); **shared** = operates only on the
integration layer, source-agnostic (no `--source` needed).

## Key Behaviors & Gotchas

- **Icon splash detection** (`pipeline/utils/artwork.py` → `find_kill_team_page`): picks the
  page with the LARGEST "KILL TEAM" title `> min_title_size` (default `30.0`). The ~40pt
  splash beats the ~18pt operatives heading. Returns `-1` (no icon) for old-format PDFs with
  no splash (e.g. sanctifiers `eng_25-02`) — a data gap, not a bug.
- **Heavy pixel work is centralized** in `pipeline/utils/artwork.py` so both tracks can't
  drift. Step modules only resolve *where the PDF is* and *which team it is*.
- **Per-team state is rewritten wholly each run** (no cross-team merge), so it never holds
  stale keys. The global `pipeline-state.json` index is rebuilt by scanning the per-team
  state files, so it stays authoritative automatically — no delete-and-regenerate dance.
- **ETL rule:** never hand-edit intermediate/output artifacts (`*-content.json`, `manifest.json`,
  extracted images, `output/*`, metadata). Fix the step source and re-run with `--force`.

## Onboarding on a New Machine

1. Clone repo; `layers/kt-app/` + `layers/warcom/` are gitignored, so re-fetch/re-scrape
   raw inputs: kt-app PDFs go in `new_implementation/input/`; warcom PDFs go in
   `new_implementation/layers/warcom/staging/{team}-datacards.pdf`.
2. `layers/integration/**` and `output/**` come with the repo (committed artifacts).
3. Run from `new_implementation/`: `python -m pipeline.main --list` to confirm steps load.
4. Regenerate a team end-to-end to validate: `python -m pipeline.main --source warcom --teams kasrkin --force`.
