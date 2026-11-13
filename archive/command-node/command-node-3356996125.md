# KT Command Node 2024 archive

- Workshop: https://steamcommunity.com/sharedfiles/filedetails/?id=3356996125
- Title: KT Command Node 2024 - Beta, by mal20k; forked from Focks' KT 2021 Command Node.
- File: `command-node-3356996125.json`, copied unchanged from the local Tabletop Simulator Workshop cache.
- Save date: 2024-12-07; cached locally on 2026-03-04. This is not necessarily the latest Workshop version.
- SHA-256: `990450515e93c30498df362bc71485731b6059f8afb4b1e6a842a28ad1ab582c`.

The save contains the Command Node object's Lua script and an embedded model
script in its saved state, for reference or loading in Tabletop Simulator.

`command-node-3356996125-script-api.json` is the unmodified response from
https://datateamapp.azurewebsites.net/api/Scripts/ModelNode, retrieved on
2026-11-13. It contains the API's model and node update scripts, which may
differ from those in the Workshop save. The version endpoint reported model 15
and node 23 at retrieval time. SHA-256:
`c7700b01343e7fe7516e8b0502bfff89c28c984ed3fc86dc14c4c24c425a82d9`.

This is not a self-contained offline backup: the script references the
DataTeamApp roster encoding API and Steam-hosted assets, which are not included.
The encoder page and script API responded at retrieval time, but the original
roster-to-model workflow has not been verified.

The separate `3573927734` save is the Killzone base table, not the standalone
Command Node or UI Extender. Its extracted model script is already vendored in
`config/defaults/tts-script/ktui-extender-modelscript.lua`.

## Upstream source snapshots

Both upstream repositories were archived and read-only when these commit-pinned
source ZIPs were downloaded on 2026-11-13. They include the upstream licenses and
files at those commits, but not Git history.

- Command Node: https://github.com/mal20k/command-node, commit
	`cc370c765621a3bd20a577768e0f4e6fc57d08d9`, Unlicense. The snapshot
	`command-node-source-cc370c7.zip` contains the Node and model `.ttslua`
	sources and the upstream save. SHA-256:
	`d5c8dac396c3ced88ff60e03173b9955e3f0e89322071728fe67df4a968d5ec5`.
- KTUI: https://github.com/mal20k/KTUI, commit
	`1cfdd7b42f3f1ae0b1ccc67750ecf3dfc6922d1d`, GPL-3.0. The snapshot
	`ktui-source-1cfdd7b.zip` contains the extender and miniature Lua sources,
	UI resources, and tests. SHA-256:
	`2b4926bdeecb1f300afe34cd32c9ae8ea98a5af0a7690380563f1a6859fbe923`.

Check the applicable license obligations before reusing or distributing code
derived from either snapshot, especially the GPL-licensed KTUI source.