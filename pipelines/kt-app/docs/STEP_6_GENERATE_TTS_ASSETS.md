# Step 6: Generate TTS Assets

## Purpose

Generate the 3D cardbox mesh (`.obj`) and its texture (`.jpg`) used to represent a team's card box in Tabletop Simulator. The box is a small 3D object that players click to spawn card decks in-game.

---

## Script

`pipelines/kt-app/steps/6_generate_tts_assets.py`

---

## Input

| Path | Description |
|------|-------------|
| `config/team-config.yaml` | Team display name and faction |
| `config/teams/{team}/icon.png` | Team icon image |
| `layers/warcom/extracted/_generic/generic-artwork-001.jpeg` | Generic background art for box faces |
| `config/teams/{team}/box/` | Optional team-specific box texture overrides |

---

## Output

| Path | Description |
|------|-------------|
| `output/{team}/cardbox/{team}-card-box-texture.jpg` | 6-face UV texture for the box mesh |
| `output/{team}/cardbox/{team}-card-box.obj` | Wavefront OBJ mesh for the cardbox |

---

## Execution

```bash
poetry run python pipelines/kt-app/steps/6_generate_tts_assets.py
```

### Options

| Flag | Description |
|------|-------------|
| `--teams NAME [NAME ...]` | Process only the specified team(s) |

---

## Box Dimensions

The cardbox model represents a small physical card box:

| Dimension | Value |
|-----------|-------|
| Width | 2 cm |
| Length | 5 cm |
| Height | 3.5 cm |

These dimensions are reflected in the OBJ vertex coordinates.

---

## Texture Layout

The box texture is a single JPEG image (`714 × 585 px`) containing a UV layout for all 6 faces of the box:

| Face | Content |
|------|---------|
| `SIDE_A` (front) | Team icon + team name |
| `TOP` | Team name |
| `SIDE_B` (back) | Generic background art |
| `SIDE_C` (left) | Generic background art |
| `SIDE_D` (right) | Generic background art |
| `BOTTOM` | Generic background art |

The UV map in the OBJ file maps each face of the box geometry to the correct region of this texture image.

### SIDE_A Composition

SIDE_A is the most visible face. It is composited by:
1. Placing the generic background art as the base layer
2. Overlaying the team icon, centered and scaled to fit
3. Rendering the team display name as text below the icon

### Team-Specific Overrides

If `config/teams/{team}/box/` contains a pre-built texture image, it is used directly instead of the generated composite. This allows fully custom box art for teams that need it.

---

## Processing Steps

### 1. Load Team Config

Reads `config/team-config.yaml` for the team's display name and slug.

### 2. Load Assets

- Team icon: `config/teams/{team}/icon.png`
- Background art: `layers/warcom/extracted/_generic/generic-artwork-001.jpeg`

### 3. Composite Texture

The 714 × 585 px texture canvas is prepared. Each face region is filled:
- Non-SIDE_A faces: tiled or cropped from the generic background art
- SIDE_A: composited with icon and team name text overlay
- TOP: team name text rendered into the face region

If a team-specific box texture override exists in `config/teams/{team}/box/`, it replaces the generated texture entirely.

### 4. Write Texture JPEG

The composited texture is saved to `output/{team}/cardbox/{team}-card-box-texture.jpg`.

### 5. Generate OBJ Mesh

A Wavefront OBJ file is generated with:
- 8 vertices defining the box corners at the specified dimensions
- UV coordinates mapping each face to the correct region of the texture
- Face definitions for all 6 sides

The OBJ is written to `output/{team}/cardbox/{team}-card-box.obj`.

---

## Output Structure

```
output/kommandos/cardbox/
├── kommandos-card-box-texture.jpg    # 714x585 px UV texture
└── kommandos-card-box.obj            # 3D mesh
```

---

## Error Handling

- **Missing team icon**: Warning logged; SIDE_A is rendered with text only (no icon)
- **Missing generic background art**: Error logged; step exits
- **Missing team config entry**: Error logged; team is skipped

---

**Last Updated**: May 17, 2026
