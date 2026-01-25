# Display Table Scripts

Scripts for managing the TTS display table with the Manager bag.

## Scripts

### `extract_manager_bag.py`
Extracts a minimal Manager bag from the display table for version control.
- **Input**: `tts_objects/display-table/kt_display_table.json`
- **Output**: `tts_objects/manager/kt_manager_bag.json`
- **Run**: Before regenerating display table

### `generate_display_table.py`
Regenerates the full display table JSON from the Manager bag.
- **Input**: `tts_objects/manager/kt_manager_bag.json`
- **Output**: `tts_objects/display-table/kt_display_table.json`
- **Run**: After updating Manager bag

## Workflow

1. Extract current Manager: `python script/display_table/extract_manager_bag.py`
2. Make changes to Manager bag JSON
3. Regenerate display table: `python script/display_table/generate_display_table.py`
