# Tools

Utility scripts for managing and updating TTS objects.

## Available Tools

### `update_manager.py`
Unified Manager bag update utility.
```bash
# Update Manager from template
python script/tools/update_manager.py --from-template

# Sync Manager to display table
python script/tools/update_manager.py --sync-display-table

# Do both
python script/tools/update_manager.py --all
```

### `update_cardbox_features.py`
Update features in card box Lua scripts.
```bash
# Update cache busting for all teams
python script/tools/update_cardbox_features.py --update-cache-busting

# Update specific teams only
python script/tools/update_cardbox_features.py --update-cache-busting --teams kasrkin blooded
```

### `update_token_timestamps.py`
Add or update token timestamp checking in card boxes.
```bash
python script/tools/update_token_timestamps.py
```

### `verify_timestamps.py`
Verify that card boxes have timestamp fields.
```bash
python script/tools/verify_timestamps.py
```

### `add_backsides.py`
Add backside images to datacards (usually part of pipeline).
```bash
python script/tools/add_backsides.py
```

## Purpose

These tools are for:
- One-time feature additions to existing TTS objects
- Debugging and verification
- Manual fixes when needed

Most functionality is integrated into the main pipeline (`run_pipeline.py`).
