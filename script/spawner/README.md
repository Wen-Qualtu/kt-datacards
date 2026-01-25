# Spawner Scripts

Scripts for generating and managing the Kill Team spawner token.

## Scripts

### `generate_spawner_image.py`
Generates the PNG image showing all available teams in a 4-column layout.
- **Input**: `output_v2/tts-card-boxes.json`
- **Output**: `output_v2/team-spawner-image.png`
- **Dynamic**: Auto-calculates layout based on team count

### `generate_team_spawner.py`
Generates the complete spawner token TTS object with embedded Lua script.
- **Input**: `config/defaults/tts-script/team-spawner-script.lua`
- **Output**: `tts_objects/display-table/kt_team_spawner.json`

## Usage

Generate the spawner image after adding/removing teams:
```bash
python script/spawner/generate_spawner_image.py
```

Generate the complete spawner token object:
```bash
python script/spawner/generate_team_spawner.py
```
