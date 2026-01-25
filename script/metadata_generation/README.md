# Metadata Generation Scripts

Scripts for generating metadata files for TTS objects and GitHub.

## Scripts

### `generate_metadata.py`
Generates the main output metadata YAML file with all team information.
- **Input**: Processed datacards in `output_v2/`
- **Output**: `output_v2/metadata.yaml`
- **Used by**: Pipeline step 5

### `generate_tts_metadata.py`
Generates TTS-specific metadata files (tts-metadata.json, tts-manager.json).
- **Input**: Team card boxes in `output_v2/`
- **Output**: Various TTS metadata files
- **Used by**: Pipeline step 6

### `generate_tts_objects.py`
Generates complete TTS JSON objects with preview images.
- **Input**: Card boxes and metadata
- **Output**: TTS objects with embedded preview images
- **Run**: After generating card boxes

### `generate_urls.py`
Generates the datacards-urls.json file with GitHub raw URLs.
- **Input**: Team card boxes
- **Output**: `output_v2/datacards-urls.json`
- **Used by**: Pipeline for URL generation

### `create_manager_metadata.py`
Creates metadata for the Manager bag for GitHub display.
- **Input**: Manager bag JSON
- **Output**: Manager metadata file
- **Run**: When updating Manager bag

## Usage

These scripts are typically run by the main pipeline, but can be run individually:

```bash
# Generate main metadata
python script/metadata_generation/generate_metadata.py

# Generate TTS metadata
python script/metadata_generation/generate_tts_metadata.py

# Generate URLs
python script/metadata_generation/generate_urls.py

# Create Manager metadata
python script/metadata_generation/create_manager_metadata.py
```
