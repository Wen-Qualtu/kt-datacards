#!/usr/bin/env python3
"""
Unified Manager update utility - combines all Manager-related updates.

This tool can update the Manager bag Lua script in multiple locations:
- Standalone Manager bag (tts_objects/manager/kt_manager_bag.json)
- Display table Manager (tts_objects/display-table/kt_display_table.json)

Usage:
    python tools/update_manager.py --from-template
    python tools/update_manager.py --update-cache-busting
    python tools/update_manager.py --update-button-layout
"""

import json
import argparse
from pathlib import Path


def update_manager_lua(manager_path: Path, lua_script: str, description: str):
    """Update Manager Lua script in a JSON file."""
    print(f"Updating {manager_path.name}...")
    
    with open(manager_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Update Lua script
    data['ObjectStates'][0]['LuaScript'] = lua_script
    
    with open(manager_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Updated {manager_path.name} - {description}")


def update_from_template():
    """Update Manager Lua from template file."""
    template_path = Path('config/defaults/tts-script/manager-script.lua')
    manager_path = Path('tts_objects/manager/kt_manager_bag.json')
    
    if not template_path.exists():
        print(f"❌ Template not found: {template_path}")
        return
    
    with open(template_path, 'r', encoding='utf-8') as f:
        lua_script = f.read()
    
    update_manager_lua(manager_path, lua_script, "from template")


def update_in_display_table():
    """Update Manager Lua in display table."""
    manager_path = Path('tts_objects/manager/kt_manager_bag.json')
    display_table_path = Path('tts_objects/display-table/kt_display_table.json')
    
    if not manager_path.exists():
        print(f"❌ Manager bag not found: {manager_path}")
        return
    
    # Read Manager Lua
    with open(manager_path, 'r', encoding='utf-8') as f:
        manager_data = json.load(f)
    
    lua_script = manager_data['ObjectStates'][0]['LuaScript']
    
    # Update display table
    update_manager_lua(display_table_path, lua_script, "synced from Manager bag")


def main():
    parser = argparse.ArgumentParser(description='Update Manager bag Lua scripts')
    parser.add_argument('--from-template', action='store_true',
                       help='Update Manager from template file')
    parser.add_argument('--sync-display-table', action='store_true',
                       help='Sync Manager Lua to display table')
    parser.add_argument('--all', action='store_true',
                       help='Update from template and sync to display table')
    
    args = parser.parse_args()
    
    if args.all or args.from_template:
        update_from_template()
    
    if args.all or args.sync_display_table:
        update_in_display_table()
    
    if not any([args.from_template, args.sync_display_table, args.all]):
        parser.print_help()


if __name__ == '__main__':
    main()
