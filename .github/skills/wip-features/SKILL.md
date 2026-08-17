---
name: wip-features
description: 'Roadmap + resume-state for in-progress kt-datacards features that span multiple sessions/PCs. USE WHEN: resuming or continuing work on the KTUI Extender integration or the Attack Callout feature; asking "where did we leave off"; picking up on another machine; deciding the next step for these two features. Points at the branches, files, decisions, and next actions so work can continue without re-deriving context.'
---

# WIP / Open Features

Resume-state for features that are mid-flight across sessions/PCs. Update this file
as features progress. Detailed verified notes also live in local repo memory
(`/memories/repo/ktui-extender-extraction.md`) but that is machine-local — **this
file is the git-tracked source of truth** for cross-PC continuity.

Conventions honored: never commit generated artifacts (`layers/**`, `output/**`);
only `main` with explicit per-time approval; experimental work on feature branches.

---

## Feature A — KTUI Extender integration (make our "Load stats" give the full real KTUI mini)

**Branch:** `feat/ktui-extender-extract`

**Goal.** One click of the card's **Load stats** turns a plain model into the *real*
KTUI mini (dynamic colour health bar, order tokens, table Save/Load Positions +
Ready Operatives, per-model Save/Load place) **plus** our own actions — so players
never need the physical **KT Command Node UI Extender** (the round-trip that wipes
our injected blocks).

**Why the old mimic isn't enough.** Our bundled `config/defaults/tts-script/ktui-mini-modelscript.lua`
(14.8 KB, 45 fns) only draws a static grey wound box and no live order token. The real
extender model script (35.8 KB, 61 fns) has `buildHPBar`/`getWoundPanelWidth`,
order system, and the table-control RPC hooks.

### The recipe (locked)
```
composed_model_script = patch( extracted real extender ) + our extension Lua
```
That composed script REPLACES the mimic as the `KTUI_MODELSCRIPT` our cards stamp.

**patch() layer** (deterministic, anchor-based, each verified — fails loud on drift):
1. heal `getWoundPanelWidth` (2 bare `if` → `elseif`) — **append-safety only**; the bar
   already renders fine on the real extender, but the missing `end`s would otherwise
   swallow anything appended below. Bar-neutral.
2. remove the `Movement` context item (+ dead `agregaRuta`) — we load our own movement.
3. guard the one unguarded game-log call (`gameLogAppendOperativeChangedState`, bare-table safety).
- `owner` (`state.owner`) is set **card-side** on load (only the card knows who clicked).
- Keep `agregaCono` (targeting lines), Change UI position, Update stats.

### Files (all on the branch)
| File | Role |
|---|---|
| `dev/extract_ktui_extender.py` | manual-trigger extractor: mod JSON → `dev/ktui-extender-modelscript.lua` (vendored verbatim, provenance header). Re-run when the owner updates the extender. |
| `dev/ktui-extender-modelscript.lua` | vendored real extender model script (tracked). |
| `dev/build_ktui_model_script.py` | the composer: patch(vendored) + `ktui-extension.lua` → `dev/ktui-model-composed.lua`; validates balance (append-safe). |
| `dev/ktui-extension.lua` | OUR model-side additions (POC: chained-onLoad proof block). **Grows to carry move/sprint/callout hooks.** |
| `dev/ktui-model-composed.lua` | generated composed script (the future `KTUI_MODELSCRIPT`). |
| `dev/build_ktui_composed_loader.py` + `dev/ktui-composed-loader-card.*` | dev pad to stamp the composed script onto a model for isolated testing. |

### Code seams already wired (default behavior unchanged)
- `pipeline/steps/tts_impl.py` — `KT_KTUI_MODELSCRIPT` env var overrides the model script
  path (default = mimic). Used to build sample boxes with the composed script.
- `config/defaults/tts-script/datacard-load-stats.lua` — `diffAndApply(model, data, playerColor)`
  now sets `owner` (+ `saveState`) on a fresh stamp, guarded so the mimic is unaffected.

### How to build/test sample boxes (regenerate; do NOT commit output)
```powershell
python dev/extract_ktui_extender.py           # needs dev/3573927734.json (gitignored)
python dev/build_ktui_model_script.py         # -> dev/ktui-model-composed.lua
$env:PYTHONPATH="."; $env:KT_KTUI_MODELSCRIPT="dev/ktui-model-composed.lua"
python -m pipeline.main --source kt-app --step generate_tts --teams hearthkyn-salvagers,angels-of-death --force
Remove-Item env:KT_KTUI_MODELSCRIPT
```
Load the box → put any model on a card → right-click **Load stats** (one click) → expect
dynamic bar + order token + owner set + `KT: extension OK` item; Movement item gone.

### Verified facts (so we don't re-derive)
- Table controls discover models by **tag** (`getAllObjects()` + `hasTag('KTUIMini')`), not a
  private registry → our stamped models are found by the *existing* table buttons.
- Owner is set the way the extender does: `model.call("setOwningPlayer", steam_id)` after stamp.
- Cards + extender are **enough**; the Command Node adds nothing our card stat-load misses
  (only real gap was `owner`, now handled). One unguarded game-log call → guarded in patch.
- TTS/MoonSharp accepts `!=`; strict `luaparser` doesn't — sanitize `!=`→`~=` for parse checks only.

### Action gating & modularity (how it works TODAY — keep this model)
- Gating is done at CREATION, not runtime. Two gates:
  1. Build-time embed (`tts_impl.py` ~L1697): MOUNTED card embeds `SPRINT_TOOL_CODE` only,
     non-MOUNTED embeds `MOVE_TOOL_CODE` only. Unused tool never ships on the card.
  2. Card onLoad menu gate (`datacard-load-stats.lua` L45-49): item added only if the code
     var exists AND `hasKeyword("MOUNTED")` matches — one GMNotes read, no per-action logic.
     "Load everything" (afterStatsLoaded L1045) auto-adds the right one by keyword.
- Today the model gets a tool via runtime `injectBlock` (START/END markers) on "Add … action".

### Lua block inventory (modularity audit — verified)
MODULAR `.lua` files (STATIC / logic-only — same code every team, read `state` at runtime):
`move-tool.lua`, `sprint-movement-tool.lua`, `ktui-mini-modelscript.lua` (default model),
`datacard-load-stats.lua` (card loader), `single-object-updater.lua`, `intermediate-updater.lua`,
`team-spawner-*.lua`, `display-table-manager-script.lua`, `bag-of-bags-reload-script.lua`,
`tts-update-rules-in-box-script.lua`.
DATA-PARAMETERIZED (Lua generated in `tts_impl.py` from team-config — ONE builder serves all 48
teams; this is CORRECT, not a wart):
- Faction-rule popups: `_build_select1_lua` (L2201) / `_build_select2_lua` (L2379).
- Counters/tokens: `_build_operative_counters_lua` (L2945) / `_build_operative_counter_lua` (L2755).

PRINCIPLE (decided): static/logic-only block -> `.lua` file; data-parameterized block -> keep the
Python generator (preserves cross-team reuse; static files would force per-team hardcoding).
Do NOT force the generators into files. Only if an inline builder becomes unwieldy, the middle
option is a `.lua` TEMPLATE with `{{tokens}}` that Python still fills with the data (keeps reuse) —
optional polish, not a goal.
CLEANUP: `faction-rule-chapter-tactics.lua` is ORPHANED (not referenced in code; only in
pipeline-state fingerprints) — verify + remove.

### NEXT STEPS to productionize
1. Move the composer output into `config/` as the default `KTUI_MODELSCRIPT`
   (or run the composer as a build step); drop the env-var gate once it's the default.
2. **Compose per-keyword variants at build time** (preferred — keeps gating at creation):
   `composed_mounted = patch(extender)+ktui-extension.lua+sprint-movement-tool.lua`;
   `composed_default = patch(extender)+ktui-extension.lua+move-tool.lua`. Embed the right
   variant per card (same MOUNTED gate), so one stamp bakes in the correct movement — no
   runtime inject. Shared always-on hooks (owner, callout) live in `ktui-extension.lua`;
   keyword-specific tools are appended by the composer. Keep one source file per tool.
3. Rebuild all 48 boxes; verify bar + tokens + table Save/Load + Ready work with the
   physical extender ABSENT, and 0 unexpected card-image churn.
4. Attribution: keep the extender authors' credit (Nyirsh, Feuerfritas, Ixidior, Mal20k).

---

## Feature B — Attack Callout (chat call-outs for a model's weapons)

**Branch:** `feat/attack-callout-poc` (pushed, parked)

**Goal.** Two context items ("Ranged attacks" / "Close combat attacks") + two rebindable
hotkeys ("KT: Call out ranged/melee attacks") that print a model's weapon group to chat,
one weapon per line: `[R/M] {name}   ATK: {A} @ {HIT}   DMG: {n/crit}   WR: {rules}`.
Injured operatives show the +1 hit in red with a medical cross (✚), matching the KTUI
wound-bar injured state (`state.wounds < max/2`). Chat-only (dice auto-roll deferred —
the old model's `KTUIDiceRoller`/`askSpawn` is stale).

### Files (on `feat/attack-callout-poc`)
- `dev/build_callout_loader.py` → `dev/callout-loader-card.json` / `.lua`: dev loader that
  injects the callout block (`-- START/END KT_ATTACK_CALLOUT_V1 --`) onto a KTUI mini via a
  chained onLoad. Load stats first (populates `state.info.weapons`).

### Status / next steps
- POC validated (Lua parses, labels ATK/DMG/WR, injured red ✚). Awaiting in-TTS validation
  of format + the ✚ glyph rendering (fallback to text if it doesn't render).
- To productionize: fold the callout block into the model-side extension (Feature A's
  `ktui-extension.lua`) so every operative gets it on load, then rebuild boxes.
- Note: the real extender already has a `callback_Attack` — reconcile/replace as needed.

---

## Feature C — Smart Targeting Lines (BACKLOG / future idea)

**Idea.** Extend the extender's targeting-lines tool (`agregaCono`, kept in the composed
script) so it auto-detects KT cover/obscurity from the drawn shooter→target line and
lights up a "Cover" / "Obscured" indicator.

**Feasibility: CONFIRMED possible.** TTS `Physics.cast` returns the objects a line
crosses/near; we already use ray, sphere, and box casts (`move-tool.lua` L275,
`datacard-load-stats.lua` L80, `tts-update-rules-in-box-script.lua` L798 sphere,
`team-spawner-clean-script.lua` L122 box). Cast shooter-base → target-base and read
`hit.hit_object`.

**Official rules (verbatim intent — keep exact). Ref: https://battlekit.killteam.ru/ (Cover / Obscured / Intervening).**
- INTERVENING (the core primitive): the shooter's player draws imaginary straight lines ~1mm
  diameter from ANY ONE point of its base to EVERY facing part of the target's base. Terrain that
  AT LEAST ONE line crosses is "intervening"; terrain that ALL lines cross is "WHOLLY intervening".
  The shooter chooses the origin point (can lean left/right for a better angle) → so an auto-tool
  is an AID/approximation, not authoritative. Determined in 3D when heights differ (Vantage);
  otherwise top-down is fine. (For non-operative sources like markers, treat all parts as the base.)
- COVER: an operative is in cover if there is INTERVENING terrain within ITS 1" control range
  (i.e. near the TARGET when shooting). Exceptions: NOT in cover if within 2" of the other
  operative; terrain within control range but NOT intervening does not count (must be between them).
  Outcome (we can surface via `state.order`): Conceal + cover → NOT a valid target; Engage + cover
  → valid target but gets a COVER SAVE.
- OBSCURED: an operative is obscured if there is INTERVENING HEAVY terrain that is >1" from BOTH
  operatives. Heavy terrain within 1" of EITHER operative does not obscure — BUT this is PART-based:
  being within 1" of a terrain feature doesn't stop the REST of that feature (the part >1" from both)
  from obscuring. So classify by the intervening POINT, not the whole piece.
  Outcome: attacker discards one success; all crits are retained as normal successes (cannot crit).

**Mechanism.**
- The official targeting-lines model IS a ray fan: from ONE shooter-base point → every facing part
  of the target base (a cone). `Physics.cast` returns `hit.point` (see `move-tool.lua` L283), so per
  hit we can measure distance to the target and to the shooter, and classify the exact part hit.
- Cover: any intervening hit with `distance(hit.point, target) − targetRadius < 1"` AND bases >2" apart.
- Obscured: any intervening HEAVY hit with `hit.point` >1" from BOTH operatives.
- Track BOTH "intervening" (≥1 ray crosses) and "wholly intervening" (ALL rays cross) — some rules need it.
- 3D is AUTOMATIC: `Physics.cast` is 3D, so casting from the shooter point at its real height to
  points on the target base at their height handles Vantage line-of-sight for free. Only the Vantage
  GAME EFFECTS (extra Accuracy / save changes) are a separate later layer — the geometry is not.
- ≤2" apart → no cover/obscured (base-to-base distance check).
- Preferred impl = RAY FAN (shooter-point → sampled points across the target base: edges + between).
  Per-ray `hit.point` classification NATURALLY satisfies (a) "intervening" (only terrain the
  sightlines actually cross), (b) the cone (fan spans the base width), and (c) the PART-based obscured
  rule (each ray classifies the exact part hit). A single center line or a sphere-at-target both need
  extra filtering to approximate "intervening" + the part-based nuance, so the fan is cleaner.

**Dependencies / limits (honest).**
- Terrain must have colliders (most killzone terrain does; flat decor may be missed).
- Light-vs-heavy typing needs a terrain TAG or name→type mapping. MVP: detect ANY terrain
  in the way ("cover"/"obscured" flags) without the light/heavy split.
- Center-to-center is a simplification vs KT's base-edge/all-sightlines — build it as a
  HELPER/indicator, not a perfect rules enforcer. Accuracy ceiling depends on terrain tagging.
- Multiple rule sources/edge cases exist (see the user's cover-matrix image) — start with the
  core cover/obscured/2" cases, iterate.

**Terrain typing — investigated in the base mod (2026-08-17).**
- Terrain IS visible in the mod (~3.5k candidate objects). At runtime read
  `hit.hit_object.getName()` + `.getTags()`.
- TYPE lives in the NICKNAME, not tags. ~554 pieces / 27 distinct names carry Light/Heavy (+ traits
  like Vantage / Traversable / Door / Scramble / Scalable / Insignificant), e.g. "Light Rubble",
  "Heavy Rubble", "Capillary Tower (Heavy)", "G3: Heavy Terrain", "Heavy, Door, Vantage". Some are
  MIXED (Heavy base + "On Top: Light" = Vantage). Runtime can classify these by parsing getName().
- NO terrain-type TAG scheme exists. Tags are killzone-set groupings (`ITD_Piece`, `Tomb_World_1..6`,
  `Barrier`, `_Octarius`, `_Moroch`, `_Bheta_Decima_*`) + `KT_Objective`. => asking the creator to add
  Light/Heavy(+Vantage) TAGS to pieces is the real fix.
- GAP: ~2.9k pieces / 35 names have NO type in the name:
  * BLANK-nickname killzone sets (Tomb World, ITD "Into the Dark", Bheta-Decima) — identified ONLY by
    a set-tag, no per-piece name → CANNOT be classified by name/tag (different pieces share tag+blank
    name). These NEED creator tags (or a fragile mesh-URL map).
  * Named-but-untyped Into-the-Dark pieces (Open/Closed Door, Breachable Wall, Hatchway, Pillar,
    Teleport pad) — a small finite list the user can hand-classify.
- PLAN: temp repo `name→type` mapping (seed the 27 typed names automatically from nicknames; user
  hand-fills the ~20 named-untyped). Real fix = creator-added tags. "is-terrain" runtime heuristic =
  set-tag OR terrain nickname, EXCLUDING `KTUIMini`/`Operative`/`KTUIToken*`/`KT24Token`/`KT_Objective`.
- Survey scripts (temp, not committed): `$TEMP/kt-split/survey_terrain.py`, `seed_terrain_map.py`.

**Status:** idea only, not started. Verdict = worth building later; NOT binned.

---

## Cross-cutting reminders
- Force composed URLs for a test build by deleting `output/{team}/{team}-object-urls.json` first.
- `git`/`gh` write to stderr (PowerShell shows "NativeCommandError" but the command succeeds);
  push exit code 1 is usually just the >50 MB large-file warning.
- Never write absolute paths into any artifact; store workspace-relative POSIX paths or URLs.
