# Display Table Generation

## Overview

The `generate_display_table.py` script generates the TTS (Tabletop Simulator) display table JSON file that shows all team card bags in a grid layout.

## File Location

- **Script**: `dev/generate_display_table.py`
- **Output**: `tts_objects/display-table/kt_all_teams_grid.json`

## What It Does

1. **Loads Base Structure**: Creates the table configuration with HandTriggers (player zones), lighting, and other TTS settings
2. **Finds All Teams**: Scans `tts_objects/` for all `*Cards.json` files
3. **Sorts Alphabetically**: Arranges teams in alphabetical order by name
4. **Positions in Grid**: Places each team bag in a 10x4 grid layout
5. **Updates Metadata**: Sets current timestamp and adds all teams to ComponentTags
6. **Outputs JSON**: Writes the complete display table file

## Grid Layout

- **Grid Size**: 7 columns × 6+ rows
- **Spacing**: 12.46 units horizontal, 7.51 units vertical
- **Starting Position**: Top-left at (-37.58, 22.38)
- **Height**: 3.46 units above table

## Usage

```bash
python dev/generate_display_table.py
```

## When to Run

The display table is **automatically generated** at the end of the full pipeline. However, you can also run it manually when:
- You add a new team to the project
- Team JSON files are updated with new content
- You need to regenerate the display table independently

**Note**: The pipeline automatically runs this script as the final step (Step 7) after all teams are processed.

## Output

The script generates a ~3.2 MB JSON file containing:
- 10 HandTrigger objects (player zones)
- 44 Custom_Model_Bag objects (one per team)
- Table configuration and lighting settings
- ComponentTags with all team names

## Verification

After running, you can verify the output by:
1. Checking the file size (should be around 3.2 MB)
2. Reviewing the console output for team count
3. Comparing with git diff to see what changed
4. Loading the file in Tabletop Simulator

## Technical Details

### Grid Calculation

Each team's position is calculated based on its alphabetical index:
- Row = index ÷ 7
- Column = index % 7
- X = -37.5753365 + (column × 12.4553365)
- Z = 22.3820934 - (row × 7.51)

### Team Bag Structure

Each team bag includes:
- Custom 3D model (OBJ file)
- Texture (JPG file)
- Contained card objects (decks and individual cards)
- Lua script for setup/recall/update functionality
- Tags for organization

## Notes

- The script preserves the exact structure and formatting of the original file
- Only the timestamp and ComponentTags are updated
- Team positions are deterministic based on alphabetical sorting
- The file is compatible with TTS v14.1.8+
- Grid positions are calculated to match the workshop file (ID: 3646032507)
- Small position variations may occur due to TTS physics but don't affect functionality
