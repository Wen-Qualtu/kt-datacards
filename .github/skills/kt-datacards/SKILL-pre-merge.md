---
description: kt-datacards pre-merge / pre-deploy verification — flag TTS update-loop risks, missing hashes, partial-run cascade churn, structure↔output drift, and non-main URL leaks before code is merged or pushed. Load when the user asks for a pre-merge check, pre-deploy check, "ready to merge?", "ready to push?", or any equivalent gating question.
tags: [kill-team, kt-datacards, pre-merge, pre-deploy, verification, tts, timestamps]
---

# kt-datacards — Pre-merge / Pre-deploy Verification

## When to Use This Skill

Load when the user asks anything that gates a merge/push/deploy, e.g.:
- "pre-merge check", "ready to merge?", "ready to push?", "ready to deploy?"
- "verify before commit", "any issues before I merge?", "deploy check"
- After a multi-step pipeline run, before the user commits the changes
- Anytime large batches of `output/` / `tts_objects/` / `object-urls.json` files are staged

Also load **SKILL-tts.md** for context on the TTS update mechanism.

---

## Run the standard check suite

```powershell
python .github/skills/kt-datacards/tools/check_all.py
```

`check_all.py` runs every check below and exits non-zero on any FAIL. Use it as
the single command in CI / pre-merge gates; the individual scripts are also
runnable on their own for focused debugging.

| Check script | What it asserts | Severity |
|---|---|---|
| `check_urls_main_branch.py` | Every github raw URL inside `output/**/*.json` points to `/main/` (no feature-branch URL leaks) | FAIL |
| `check_hash_baseline.py` | Every entry in every `output/*/{team}-object-urls.json` carries a `hash` field | FAIL |
| `check_timestamp_alignment.py` | For every team, bag's `LuaScriptState.lastCardUpdate` >= max `modified` across that team's `object-urls.json` entries (TTS update-loop prevention) | FAIL |
| `check_structure_cards.py` | Every datacards entity in `layers/kt-app/classified/{team}/structure.json` has the expected front/back JPG(s) under `output/{team}/cards/datacards/` (own-cards groups expected as `{slug}-cardN-{front,back}.jpg`) | FAIL |

Each script lives in `.github/skills/kt-datacards/tools/` and is fully
self-contained — no project dependencies beyond the standard library.

### Reporting

```
=== check_urls_main_branch.py ===
Scanned 1917 JSON files under output/
PASS  All github raw URLs point to /main/

=== check_hash_baseline.py ===
Checked 47 teams
PASS  All object-urls entries carry a `hash` field

=== check_timestamp_alignment.py ===
Checked 47 teams
PASS  All teams aligned (bag.lastCardUpdate >= obj-urls max modified)

=== check_structure_cards.py ===
Checked 47 teams
PASS  Every structure.json datacard entity has its expected card image(s)

READY TO MERGE — all checks PASS
```

### Verdict policy
- **READY TO MERGE** — `check_all.py` exits 0.
- **READY WITH WARNINGS** — only manual narrative additions you want to surface (none are emitted by the scripts today).
- **BLOCKED** — any script exits non-zero. Do not propose committing until resolved.

---

## Fix-it recipes (linked from check output)

### TTS update-loop alignment fail
- Recommended: full step 7 regen for the affected team(s).
  `python pipelines/kt-app/steps/7_generate_tts_objects.py --teams <team>`
- Surgical (no cascade churn): bump `bag.LuaScriptState.lastCardUpdate` to match
  `obj-urls.box.modified` and refresh `obj-urls.box.hash` — see
  `/memories/repo/kt-app-step7-timestamp-alignment.md` for the exact recipe.

### Missing `hash` field
- Run step 7 once for that team. The hash-aware generator populates `hash`
  on every entry while preserving URLs/modified for unchanged content.

### structure ↔ card image drift
- Re-run step 4 for the affected team:
  `python pipelines/kt-app/steps/4_extract_card_images.py --teams <team> --force`
- If step 2 also changed, run step 2 first then step 4.

### Non-`main` URL leak
- An asset URL was generated against a feature/dev branch (likely via
  `KT_DATACARDS_URL_BRANCH=<other>` in the environment). Re-run step 7 with
  the env var unset or set to `main`.

---

## DO NOT

- Do not auto-fix anything from inside this skill. Report and recommend; let the user choose the fix.
- Do not stage or commit during a pre-merge audit. The check scripts are read-only.
- Do not delete the `hash` field from an object-urls entry to "force" a refresh — that just disables change-detection.
- Do not add new check scripts here that depend on network access — keep them read-only and offline.
