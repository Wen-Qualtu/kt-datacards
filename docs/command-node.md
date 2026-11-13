# Command Node prototype

The saved object is built with `python -m tools.build_command_node`. Its default
destination is `dev/command-node.json`; use `--overwrite` only to replace an
earlier build. Use `--branch feature/command-node` to target that published
branch. The editable source is `config/defaults/tts-script/command-node.lua`.

In Tabletop Simulator, start the node, choose a team and quantities, then create
the placement slots. Select each slot in the panel to adjust its loadout. Place
one model on each named outline and confirm. The node validates placements before
applying stats, and reports a slot if it needs attention. Already-applied slots
are skipped on retry after an error.

This is a prototype, not yet fully validated in Tabletop Simulator. The node
fetches the team index, selected team's object URL metadata and team data live,
then fetches the shared model loader when confirming. Team data is not embedded
in the node. Applying stats can reset a model's wounds and install
the existing KTUI script on an unprepared model. Test on copies of models first.

The stats pipeline adds a `node` field to each datacard with weapon classifications,
loadout indexes, and weapon-rule names. Rule descriptions are stored once per team
in `node_weapon_rules`. The TTS pipeline references the existing
`output/{team}/data/{team}-team-data.json` in team metadata and generates
`output/_generic-tts-objects/command-node-loader.lua`. These outputs and metadata
must be generated and published on the chosen branch before the node can load a
team. Existing metadata without a team-data URL produces a clear error; the node
does not download the full box. Card boxes keep their existing data path and do not
use the new fields yet. Old `*-node-data.json` files from earlier prototype runs
are no longer generated or used.

Roster legality, faction choices, counters, movement actions, and roster saving
are not included. Selection choices default to the first option in each active
group. Slot and helper visuals, timing, and model detection need in-game testing.

Run the isolated tests from the repository root:

```powershell
python -m pytest tests/test_command_node.py -q
npx --yes --package=fengari-node-cli fengari tests/command-node-test.lua
```