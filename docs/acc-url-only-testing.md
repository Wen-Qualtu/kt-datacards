# Acc URL-Only Acceptance Baseline

This phase retargets the existing artifacts after PR #88 merged into `acc`.
It does not run the pipeline or migrate generated team data to the prepared
schema. The purpose is to test existing objects before regeneration.

## Allowed Changes

- Own-repository URLs in tracked JSON and runtime sources point to `acc`,
  including URLs embedded in scripts and saved objects.
- Generator and node-builder URL defaults use `acc`. Explicit branch overrides
  remain available.
- The retargeting utility, its tests, and this note document the migration.

## Preserved Baseline

No object generation, model-script recomposition, schema migration, GUID changes,
transform changes, timestamp updates, or metadata-hash recalculation is performed.
The utility preserves formatting and asserts byte equality after normalizing only
repository branch references. JSON is validated but is not reserialized.

Run `python -m tools.retarget_tts_urls` for a read-only check. A complete migration
reports zero pending substitutions. Applying requires `--apply` and is permitted
only on the `acc` branch. The local audit report records relative paths, URL
counts, before/after hashes, and branch-normalized hashes.

Existing unrelated manager-object edits are preserved in the working tree. Only
the URL-retargeted committed versions belong in the acceptance publication.

## Acceptance Checks

Load the saved manager and node objects from the `acc` branch into TTS. Check
box spawning, individual-object updates, box updates, model stat/loadout loading,
movement, special rules, and saved-state round trips before regenerating outputs.
The existing metadata hashes intentionally remain unchanged in this phase.

The automated checks verify exact frozen GMNotes parity and URL-only changes;
they do not replace in-game compatibility testing. Do not promote the `acc`
reference defaults to `main` as a production change.