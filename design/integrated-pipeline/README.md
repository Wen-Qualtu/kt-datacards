# Integrated Pipeline — Design

Living design docs for merging the **kt-app** and **warcom** pipelines into a single,
source-parameterized pipeline with shared utilities.

> Status: **iterating**. We refine these docs before/while building under `pipelines/integrated/`.

## Goal (one-liner)
One pipeline, `--source kt-app|warcom`. The source only changes the **extraction front-end**;
from the **classified** merge point onward there is a single shared track. All reusable logic
lives in `pipelines/integrated/utils/` as proper functions — not locked inside step scripts.

Why two sources: GW sometimes updates only one of the two datacard sources (and not always the
same one). Both tracks emit the **identical** file set into the shared classified layer, so you
run whichever source was updated and everything downstream is source-agnostic.

## Build/rollout constraints (acc phase)
- Build **next to** existing code; don't disturb current `layers/kt-app/*`, `layers/warcom/*`.
- New intermediates under `layers/acc/...`; final images under `output_acc/` (never `output/` = production).
- The `acc` prefix is temporary — dropped when ready. Eventual targets: `layers/shared/...`, `output/`.
- `output_acc/` makes parity diffs against production `output/` trivial.

## Docs
| File | Purpose | Status |
|------|---------|--------|
| [01-flow.md](01-flow.md) | End-to-end stage flow | **approved** |
| 02-layout.md | Directory + module layout | todo |
| 03-utils.md | Shared utils / adapters surface | todo |
| 04-open-questions.md | Decisions to lock | todo |

## Iteration log
- **R1** — Initial flow drafted. Feedback applied: drop kt-app `processed` (split straight into
  `extracted`); structure stays **split per track**; after classified add a **content analysis**
  stage (detailed content investigation) feeding all downstream steps.
- **R2** — Flow feedback applied: classified naming has **no `-front`/`-back` postfix** (one PDF
  per card; backsides produced later, not stored in classified); content analysis = full per-card
  content map mirroring today's `structure.json`; downstream **ordering** locked — icon + backside
  extraction first (split from dice), then card processing/stats/dice in parallel, **TTS last**.
- **R3** — Split into **two parallel one-off-per-team lanes** off `extracted`: card lane
  (classified → content analysis) and asset lane (icon + artwork → backside). Icon + artwork +
  backside are predecessors for card image processing. **Dice + box textures scoped to TTS only.**
- **R4** — Scoped the "shared one-off per team" box to the **asset lane only** (icon + artwork,
  backside, dice, box texture). Card lane (classified → content analysis) sits outside that box.
- **R5** — Moved **tokens** into the shared asset box (one-off per team); tokens depend on the
  **content map** (which card/token-guide to read) and the **icon** (token-bag image).
- **R6** — Icon + artwork extraction now runs on the **raw source** (`input/` and
  `layers/warcom/staging`), not on structure. Two scripts per source: icon/artwork extraction →
  shared **artwork layer** (`layers/.../artwork`), and card splitting → `extracted`. The artwork
  **layer** is its own block; downstream assets (backside, dice, box, tokens) reference the layer.
