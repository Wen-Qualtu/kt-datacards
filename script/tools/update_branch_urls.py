"""
Update GitHub URLs to use a specific branch (for testing).

This script updates all GitHub URLs in Python scripts to use a specific branch
instead of 'main', allowing us to test restructuring changes before merging.
"""

import argparse
from pathlib import Path
import re


def update_github_urls(branch_name: str):
    """Update all GitHub URLs to use the specified branch."""
    
    # Files that contain GitHub URLs
    files_to_update = [
        'script/src/generators/tts_generator.py',
        'script/generate_tts_metadata.py',
        'script/update_token_timestamps.py',
        'script/add_token_update_to_cardboxes.py',
        'script/add_timestamp_checking.py',
        'config/defaults/tts-script/team-spawner-script.lua',
        'config/defaults/tts-script/display-table-manager-script.lua',
    ]
    
    # Pattern to match GitHub URLs
    pattern = r'https://raw\.githubusercontent\.com/Wen-Qualtu/kt-datacards/main/'
    replacement = f'https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{branch_name}/'
    
    updated_count = 0
    
    for file_path_str in files_to_update:
        file_path = Path(file_path_str)
        
        if not file_path.exists():
            print(f"⚠️  Skipping {file_path}: not found")
            continue
        
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if file has URLs to update
        if pattern not in content:
            print(f"⊙ {file_path}: no URLs to update")
            continue
        
        # Replace URLs
        new_content = re.sub(pattern, replacement, content)
        
        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # Count replacements
        count = content.count('main/') - new_content.count('main/')
        print(f"✓ {file_path}: updated {count} URL(s)")
        updated_count += count
    
    print(f"\n✓ Total: {updated_count} URLs updated to use branch '{branch_name}'")


def main():
    parser = argparse.ArgumentParser(
        description='Update GitHub URLs to use a specific branch'
    )
    parser.add_argument(
        'branch',
        type=str,
        help='Branch name to use in URLs (e.g., restructure-tts-objects)'
    )
    
    args = parser.parse_args()
    update_github_urls(args.branch)


if __name__ == '__main__':
    main()
