# Kill Team Spawner Token

A lightweight alternative to the Manager bag for spawning Kill Team card boxes in Tabletop Simulator.

## Features

- **Simple Token**: Small green button token you can place anywhere
- **Interactive Selection**: Click button to see all 44 teams in a numbered list
- **Flexible Input**: Spawn by team number (1-44) or name (partial match supported)
- **No Updates Needed**: Always fetches latest team boxes from GitHub
- **Chat Commands**: Power users can use `/spawn <team>` in chat
- **Multi-Spawn**: Easy to spawn the same team multiple times

## How to Use

### Method 1: Button Click (Recommended)
1. Place the spawner token on your table
2. Click the **"Spawn Team"** button
3. Input dialog shows all 44 teams alphabetically numbered
4. Type a team number (e.g., `12`) or name (e.g., `kasrkin`)
5. Team box spawns at your pointer position

### Method 2: Chat Command
Type in chat: `/spawn <team>`

Examples:
- `/spawn 5` - Spawns team #5
- `/spawn kasrkin` - Spawns Kasrkin
- `/spawn death` - Spawns Death Korps (partial match)

## Team List

The spawner shows all teams in alphabetical order:

```
 1. Angels Of Death
 2. Battleclade
 3. Blades Of Khaine
 4. Blooded
 5. Brood Brothers
 6. Canoptek Circle
 7. Chaos Cult
 8. Corsair Voidscarred
 9. Death Korps
10. Deathwatch
... (44 total)
```

## Advantages over Manager Bag

| Feature | Spawner Token | Manager Bag |
|---------|---------------|-------------|
| **Size** | Small token | Large bag with 44 embedded boxes |
| **Updates** | No update needed | Must click "Reload Teams" |
| **Multi-spawn** | Click & select again | Need to take, copy, return |
| **Simplicity** | 2 clicks to spawn | Take from bag, search/browse |
| **Storage** | ~6KB JSON | ~80MB JSON with all boxes |
| **Network** | Downloads only requested teams | Pre-loads all teams |

## When to Use Each

**Use Spawner Token when:**
- You want a lightweight solution
- You spawn teams on-demand
- You need multiple copies of the same team
- You have limited bandwidth/storage
- You want simplicity

**Use Manager Bag when:**
- You want offline play (all teams embedded)
- You use the display table with grid layout
- You need the "Place/Recall Teams" functionality
- You frequently browse through all teams

## Files

- **Object**: `tts_objects/display-table/kt_team_spawner.json`
- **Script**: `config/defaults/tts-script/team-spawner-script.lua`
- **Image**: `config/defaults/tts-image/spawner-token.png`
- **Data Source**: `output_v2/tts-card-boxes.json`

## Technical Details

The spawner:
1. Loads team list from `tts-card-boxes.json` on startup
2. Builds lookup tables for fast name/number matching
3. Supports partial name matching (case-insensitive)
4. Fetches team box JSON from GitHub when requested
5. Spawns at player's pointer position (or above spawner if no pointer)

## Regenerating

To regenerate the spawner with updated script:

```bash
poetry run python script/generate_team_spawner.py
```

This embeds the latest Lua script into the JSON object.
