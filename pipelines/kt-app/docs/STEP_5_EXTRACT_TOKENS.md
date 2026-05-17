# Step 5: Extract Tokens

## Purpose

Extract token images from team PDFs, apply transparency, and cut them into the correct shapes for use in Tabletop Simulator. Also generates the token bag mesh (a 3D container object) that holds all tokens for a team.

---

## Script

`pipelines/kt-app/steps/5_extract_tokens.py`

---

## Input

| Path | Description |
|------|-------------|
| Team PDF files (token-guide and/or datacards) | Source of token artwork |
| `config/team-config.yaml` | Token shape definitions per team |
| `config/defaults/tts-token/input/template-round-cutter.png` | Round shape mask template |
| `config/defaults/tts-token/input/template-diamond-cutter.png` | Diamond shape mask template |
| `config/defaults/tts-token/input/template-octagon-cutter.png` | Octagon shape mask template |
| `config/defaults/tts-token/input/template-operative-cutter.png` | Operative silhouette mask template |
| `config/defaults/tts-token/square-bag-mesh.obj` | Base mesh for the token bag |

---

## Output

| Path | Description |
|------|-------------|
| `output/{team}/tokens/{team}-{token-name}.png` | Token image with transparency |
| `output/{team}/tokens/{team}-token-bag.obj` | Token bag 3D mesh |

---

## Execution

```bash
poetry run python pipelines/kt-app/steps/5_extract_tokens.py
```

### Options

| Flag | Description |
|------|-------------|
| `--teams NAME [NAME ...]` | Process only the specified team(s) |

---

## Processing Steps

### Phase 1: Detect Token Contours

The PDF pages containing token artwork are rendered to a high-resolution image using PyMuPDF. OpenCV contour detection is then used to locate individual token regions on the page.

Each detected contour is:
1. Bounding-box cropped from the rendered page
2. Saved as a candidate token image

Token areas are identified by their position on known token-guide page layouts. Where multiple tokens are present, they are separated by contour isolation.

### Phase 2: Apply Shape Masks

Each token candidate is matched to a token name (from `config/team-config.yaml` or derived from page context) and assigned a shape:

| Shape | Used For |
|-------|----------|
| `round` | Standard circular tokens |
| `diamond` | Diamond-shaped objective or marker tokens |
| `octagon` | Octagonal tokens |
| `operative` | Tokens using an operative silhouette outline |

The appropriate shape mask template is loaded and applied to the token image. Pixels outside the mask shape are made fully transparent. The result is a PNG with an alpha channel.

### Phase 3: Generate Token Bag Mesh

A token bag `.obj` file is generated for the team. This is a 3D mesh used in TTS as the container object for all of a team's tokens. The mesh is derived from `config/defaults/tts-token/square-bag-mesh.obj` and customized with team-specific dimensions or texture coordinates as needed.

---

## Output Format

**Token images**: PNG with transparency (alpha channel). Transparent areas allow TTS to render the token with correct shape against any background.

**Token bag mesh**: Wavefront OBJ format (`.obj`). Referenced by the TTS JSON object generated in Step 7.

---

## Output Structure

```
output/kommandos/tokens/
├── kommandos-breach.png
├── kommandos-conceal.png
├── kommandos-engage.png
├── kommandos-injured.png
└── kommandos-token-bag.obj
```

---

## Configuration

### Token Shapes in team-config.yaml

Each team's entry in `config/team-config.yaml` may include a `tokens` section defining the shape for each token by name:

```yaml
- slug: kommandos
  tokens:
    breach: round
    conceal: round
    engage: round
    injured: operative
```

If no explicit shape is defined for a token, `round` is used as the default.

---

## Error Handling

- **No token pages found in PDF**: Warning logged; team is skipped for token output
- **Contour detection finds no tokens**: Warning logged; check source PDF quality
- **Unknown token name**: Token is saved with a generic filename; warning logged
- **Missing shape template**: Error logged; step exits

---

**Last Updated**: May 17, 2026
