# Shared Team-Data Preparation

## Ownership

`content_analysis` produces the raw content map. `extract_stats.prepare_team_data`
prepares model data before writing the published team-data JSON:

- `model_data_version: 1` identifies the prepared model fields.
- Each operative has normalized `stats`, `abilities`, `actions`, and applicable
  `upgrades`. Existing source stat and ability fields remain during migration.
- Each weapon has `type` (`melee` or `ranged`), normalized `stats`, and resolved
  `weapon_rules`. Definitions are derived from `config/weapon_rules.json`; that
  file remains authoritative and participates in the step's input hashes.
- Indexed loadout `selection` belongs to the operative. It preserves the existing
  `groups`, `fixed`, and optional `exclusive_sets` GMNotes structure.
- The team-level operative-selection card retains its text and other content,
  but no longer duplicates the operative-name-to-selection mapping.
- New output omits `node` and `node_weapon_rules`.

Card serialization consumes these prepared fields without reclassifying weapons,
matching weapon-rule definitions, or rebuilding indexed selection. It still
accepts legacy raw team data. The node accepts prepared data and retains its
legacy adapter for already-published team data. Card Lua contracts are unchanged.

## Compatibility Gate

Before this refactor, the exact compact UTF-8 GMNotes serialization was captured
as SHA-256 hashes for 453 operatives across 48 teams in
`tests/fixtures/gmnotes-preprocessing-baseline.json`.

Run `python -m tools.check_gmnotes_parity` to verify prepared output against that
frozen baseline. The baseline-recording command refuses to overwrite an existing
baseline; do not regenerate it merely to make a failing test pass.

`tests/test_command_node.py` also exercises actual card embedding with raw and
prepared team data for every team. Both the written `GMNotes` strings and card
`LuaScript` strings must remain exactly equal. Additional tests cover source-data
immutability, idempotent preparation, prepared-data Lua parity, and legacy input.

## Migration Boundary

This verifies parity with the feature branch immediately before this refactor,
not complete compatibility against `main` or every released updater.

No production team JSON, cardbox, asset, or pipeline-state regeneration is part
of the source refactor. Integrate and generate `acc`-targeted test artifacts only
after review, then test old-box loading and update paths before any release.