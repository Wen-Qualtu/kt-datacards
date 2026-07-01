# new_implementation — Integrated Datacard Pipeline (sandbox)

Fully **detached** rebuild of the kt-app + warcom pipelines into one source-parameterized
pipeline. Nothing here touches the production code/outputs at the repo root until it works.

Design: see [../design/integrated-pipeline/01-flow.md](../design/integrated-pipeline/01-flow.md) (flow approved).

## Layout
```
new_implementation/
  input/            raw PDFs for the kt-app track
  layers/           intermediate layers (per-track + shared)
  output/           final outputs (cards, tokens, data, tts_objects, ...)
  pipeline/
    main.py         orchestrator: --source kt-app|warcom, --teams, --step, --list
    steps/          one module per flow stage (main calls these)
    utils/          paths, naming, shared helpers
```

## Run
```powershell
# from new_implementation/
python -m pipeline.main --list
python -m pipeline.main --source kt-app --teams kasrkin
python -m pipeline.main --source warcom --step integrate_classified --teams kasrkin
```

## Pipeline order (from the approved flow)
Front-end (track-specific, by `--source`) → artwork extraction (raw source → shared artwork layer)
→ structure (per track) → classified (shared merge) → content analysis (shared) →
asset lane (backsides, tokens, dice, box texture) → card images + stats → **TTS (last)**.

## Status
Scaffolding. Each step is a stub with PORT-FROM (which current file to base it on) and
SOURCE-DECISION (kt-app vs warcom) notes. We fill them in one by one.

## Layer paths (inside this sandbox)
| Path | Stage | Scope |
|------|-------|-------|
| `layers/{track}/staging/` | warcom scrape target | track |
| `layers/{track}/extracted/` | per-card split PDFs | track |
| `layers/{track}/structure/{team}-structure.json` | structure manifest | track |
| `layers/shared/artwork/` | icons + artwork | shared (both tracks write) |
| `layers/shared/classified/{team}-{type}-{name}.pdf` | merge point | shared |
| `layers/shared/content/{team}-content.json` | content map | shared |
| `output/{team}/...` | final assets | shared |
