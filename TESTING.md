# Test Plan — Integrated Pipeline

Backlog of tests we want. **Not implemented yet** — noted here so regressions from
future changes get caught automatically instead of by manual version-control review.
Motivation: in prior implementations a change in one place silently broke another, and
large runs produce too many changed files to eyeball.

Suggested stack: `pytest`. Put tests under `tests/`.

## 1. Track-parity test (highest value)
Both sources must produce identical integration filenames for every team.
- For a batch of teams, run `build_structure` for `kt-app` and `warcom`, then assert
  the derived integration filename sets are equal (wraps `tools/compare_classified`).
- Expected today: **47 MATCH / 0 DIFF**. Any DIFF fails the test.
- This is the "processes a batch of PDFs and validates the tracks agree" test.

## 2. Golden/snapshot test for structure manifests
Freeze known-good output so accidental changes are caught.
- Store expected `{team}-structure.json` (or the derived integration filename list) as
  fixtures for a representative set of teams.
- Assert `build_structure` output matches the golden fixture byte-for-byte (after
  normalizing path separators).
- When output legitimately changes, regenerate fixtures deliberately (review the diff).

## 3. Determinism / idempotency test
- Running `build_structure` twice for a team yields identical output.
- Running `kt-app` then `warcom` (or vice-versa) does not alter the other track's files.
- Full determinism check: purge `layers/`, run source A, run source B, confirm identical;
  re-run A and confirm still identical.

## 4. `card_naming` unit tests (fast, no PDFs)
Pure-function coverage on representative text inputs:
- `slug()` — apostrophes/periods dropped, non-ASCII stripped.
- `classified_name()` — team/type/name assembly.
- `has_backside_continue()`, `has_own_cards()`, `is_datacard_front()` — true/false cases.
- `detect_type()`, `extract_name()`, `extract_datacard_name()`.
- `special_case_group_size()` — fires only on the rule header, not bodies mentioning it.

## 5. `integrate_classified` filename test
- Given a structure-manifest fixture, assert produced integration filenames match
  expected, including multi-card `-{n}` suffixing and slug rules.

## 6. On-disk coverage test
- Every `front`/`back` path referenced in a structure manifest exists on disk.
- (Optional) every extracted card PDF is referenced by the manifest (no orphans/drops).

## 7. Special-case regression tests (targeted)
Assert exact entity counts/names for the messy multi-card rules we fixed:
- angels-of-death / warpcoven — 4-card faction rules.
- pathfinders — 3-card faction rule AND equipment stays 4 distinct (no fusion).
- elucidian-starstriders, gellerpox-infected, hunter-clade — 3-card faction rules.
- canoptek-circle, hierotek-circle — Necron OWN CARD datacard overflow (op-1/2/3).
- hunter-clade — operative-selection overflow (both + front).
- inquisitorial-agents — requisition sub-cards (7 faction entities, army names).
