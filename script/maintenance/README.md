# Maintenance Scripts

**⚠️ These are legacy migration and one-time update scripts.**

These scripts were used for historical migrations and updates to existing TTS objects. They are kept for reference but should **not** be run as part of the regular pipeline.

## Migration Scripts (Historical)

### Token Integration
- `add_token_update_to_cardboxes.py` - Added token update functions to card boxes
- `add_timestamp_checking.py` - Added smart timestamp checking to token updates
- `update_cardbox_lua_for_tokens.py` - Migrated Lua to handle token bags
- `update_token_timestamps.py` - Updated token timestamp tracking

### Manager Updates
- `add_manager_self_update.py` - Added self-update functionality to Manager
- `update_manager_button_layout.py` - Changed Manager UI to 2x2 grid
- `update_manager_cache_busting.py` - Updated Manager cache busting
- `update_manager_lua_in_display_table.py` - Updated display table Manager Lua

### General Updates
- `update_cache_busting.py` - Migrated from random to timestamp cache busting
- `fix_onload.py` - Fixed corrupted onload functions
- `add_backsides.py` - Added backside images to cards (now integrated in pipeline)

## ⚠️ Warning

**Do not run these scripts unless you know exactly what you're doing.** They were designed for one-time migrations and may overwrite or break existing TTS objects if run incorrectly.

If you need to make similar updates, copy and adapt the relevant script rather than running the original.
