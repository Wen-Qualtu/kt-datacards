# Step 7: Generate TTS Objects

## Purpose

Generate the Tabletop Simulator save file (JSON) for each team. This is the file that gets loaded directly into TTS — it defines the cardbox 3D object, all card decks and individual cards, token bag, operative stat data (embedded as GMNotes and Lua script tables), and all asset URLs.

---

## Script

`pipelines/kt-app/steps/7_generate_tts_objects.py`

---

## Input

| Path | Description |
|------|-------------|
| `layers/kt-app/classified/{team}/structure.json` | Card structure with operative names and card types |
| `output/{team}/cards/{card_type}/*.jpg` | Card face images (from Step 4) |
| `output/{team}/cardbox/{team}-card-box.obj` | Cardbox mesh (from Step 6) |
| `output/{team}/cardbox/{team}-card-box-texture.jpg` | Cardbox texture (from Step 6) |
| `output/{team}/tokens/*.png` | Token images (from Step 5) |
| `output/{team}/tokens/{team}-token-bag.obj` | Token bag mesh (from Step 5) |
| `output/{team}/data/{team}-team-data.json` | Operative stats (from Step 3) |
| `config/team-config.yaml` | Team display name and faction |
| `config/defaults/tts-script/` | Default Lua scripts |

---

## Output

| Path | Description |
|------|-------------|
| `output/{team}/tts_objects/{Team Name} Box.json` | TTS save file for the team |
| `output/object-urls.json` | Flat URL index of all TTS objects |

---

## Execution

```bash
poetry run python pipelines/kt-app/steps/7_generate_tts_objects.py
```

### Options

| Flag | Description |
|------|-------------|
| `--teams NAME [NAME ...]` | Process only the specified team(s) |
| `--branch BRANCH` | GitHub branch to use for raw URLs (default: `main`) |
| `--force` | Regenerate all objects, ignoring change detection |

Examples:

```bash
# Default run
poetry run python pipelines/kt-app/steps/7_generate_tts_objects.py

# Test with a dev branch (URLs point to dev branch instead of main)
poetry run python pipelines/kt-app/steps/7_generate_tts_objects.py --branch dev --force

# Regenerate one team
poetry run python pipelines/kt-app/steps/7_generate_tts_objects.py --teams kommandos --force
```

---

## Processing Steps

### 1. Build Asset URL Map

For every file in `output/{team}/`, a GitHub raw URL is computed:

```
https://raw.githubusercontent.com/{owner}/{repo}/{branch}/output/{team}/{relative_path}
```

These URLs are the paths TTS uses to fetch textures, meshes, and scripts at runtime. The `--branch` flag controls which branch is used; default is `main`.

### 2. Build Card Deck Objects

For each card type in `structure.json`, a TTS deck object is constructed. Each card in the deck has:

- `FaceURL`: GitHub raw URL for the front image
- `BackURL`: GitHub raw URL for the back image
- `Name`: card name (operative name for datacards, card identifier for others)

Decks are grouped by card type (e.g. one deck for datacards, one for strategy-ploys, etc.).

### 3. Embed Operative Stats (GMNotes and Lua)

Operative stats from `output/{team}/data/{team}-team-data.json` are embedded into the TTS objects in two ways:

**GMNotes** — A JSON-encoded string attached to each card object. TTS displays this data when a player hovers over the card. It contains the full stat block: APL, movement, wounds, save, weapons, abilities.

**Lua script tables** — Stats are also encoded into the cardbox's Lua script as data tables. This enables interactive stat card overlays and UI elements built into the TTS mod.

### 4. Build Token Bag Object

A TTS bag object is constructed for the team's tokens. Each token inside the bag references:

- `CustomImage.ImageURL`: GitHub raw URL for the token PNG
- `CustomMesh.MeshURL`: GitHub raw URL for the token mesh OBJ
- `Name`: token name

### 5. Assemble Cardbox Object

The top-level TTS object is the cardbox — a custom mesh object containing all decks and the token bag as nested objects. It references:

- Mesh URL: `output/{team}/cardbox/{team}-card-box.obj`
- Texture URL: `output/{team}/cardbox/{team}-card-box-texture.jpg`
- Lua script (from `config/defaults/tts-script/`)

### 6. Write TTS Save File

The complete TTS object hierarchy is serialized to JSON and written to:

```
output/{team}/tts_objects/{Team Name} Box.json
```

The filename uses the team's display name (from `config/team-config.yaml`), not the slug.

### 7. Update object-urls.json

`output/object-urls.json` is a flat index of all TTS save file URLs across all teams. It is updated with the URL for this team's save file. This index is consumed by the TTS update Lua script to discover available team boxes.

---

## Output Structure

```
output/kommandos/
└── tts_objects/
    └── Kommandos Box.json

output/
└── object-urls.json
```

---

## URL Format

All asset URLs in the output JSON follow this pattern:

```
https://raw.githubusercontent.com/{owner}/{repo}/main/output/{team}/{path}
```

Example:
```
https://raw.githubusercontent.com/owner/kt-datacards/main/output/kommandos/cards/datacards/Kommando Boy-front.jpg
```

---

## Error Handling

- **Missing card images**: Warning logged; card is omitted from the deck
- **Missing team-data.json**: GMNotes fields are left empty; warning logged
- **Missing cardbox assets**: Error logged; TTS object is not written for the team
- **Missing structure.json**: Error logged; team is skipped entirely

---

**Last Updated**: May 17, 2026
