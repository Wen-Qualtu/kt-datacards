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

### NEXT STEPS to productionize
1. Move the composer output into `config/` as the default `KTUI_MODELSCRIPT`
   (or run the composer as a build step); drop the env-var gate once it's the default.
2. Grow `dev/ktui-extension.lua` (→ `config/`) to carry the real move/sprint/callout hooks
   (the blocks the cards inject today), so a single stamp includes them.
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

## Cross-cutting reminders
- Force composed URLs for a test build by deleting `output/{team}/{team}-object-urls.json` first.
- `git`/`gh` write to stderr (PowerShell shows "NativeCommandError" but the command succeeds);
  push exit code 1 is usually just the >50 MB large-file warning.
- Never write absolute paths into any artifact; store workspace-relative POSIX paths or URLs.
