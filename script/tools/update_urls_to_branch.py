"""
Update all GitHub URLs in output files to use a specific branch.

This is useful for testing changes on a branch before merging to main.
"""

import json
import re
from pathlib import Path
import subprocess


def get_current_branch():
    """Get the current git branch name."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Error getting current branch: {e}")
        return None


def update_urls_in_json(file_path: Path, old_branch: str, new_branch: str) -> int:
    """Update all GitHub URLs in a JSON file to use the new branch."""
    if not file_path.exists():
        print(f"⚠️  Skipping {file_path}: not found")
        return 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to match GitHub URLs with branch name
    pattern = f'https://raw\\.githubusercontent\\.com/Wen-Qualtu/kt-datacards/{re.escape(old_branch)}/'
    replacement = f'https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{new_branch}/'
    
    # Count replacements
    count = content.count(f'/{old_branch}/')
    
    if count == 0:
        return 0
    
    # Replace URLs
    new_content = re.sub(pattern, replacement, content)
    
    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    return count


def main():
    """Update all output files to use the current branch."""
    # Get current branch
    branch = get_current_branch()
    
    if not branch:
        print("Error: Could not determine current branch")
        return
    
    if branch == 'main':
        print("⚠️  Currently on 'main' branch - no changes needed")
        return
    
    print(f"Updating URLs from 'main' to '{branch}'...")
    print("=" * 60)
    
    total_updates = 0
    
    # Update metadata files
    print("\nMetadata files:")
    metadata_files = [
        Path('output_v2/tts-metadata.json'),
        Path('output_v2/tts-card-boxes.json'),
        Path('output_v2/datacards-urls.json'),
    ]
    
    for file_path in metadata_files:
        count = update_urls_in_json(file_path, 'main', branch)
        if count > 0:
            print(f"  ✓ {file_path.name}: updated {count} URL(s)")
            total_updates += count
        else:
            print(f"  ⊙ {file_path.name}: no URLs to update")
    
    # Update all TTS object JSON files
    print("\nTTS card box objects:")
    tts_dir = Path('tts_objects')
    if tts_dir.exists():
        card_files = list(tts_dir.glob('*/*Cards.json'))
        for file_path in sorted(card_files):
            count = update_urls_in_json(file_path, 'main', branch)
            if count > 0:
                print(f"  ✓ {file_path.parent.name}/{file_path.name}: updated {count} URL(s)")
                total_updates += count
    
    # Update all token bag JSON files
    print("\nTTS token bag objects:")
    if tts_dir.exists():
        token_files = list(tts_dir.glob('*/tokens/*-tokenbag.json'))
        for file_path in sorted(token_files):
            count = update_urls_in_json(file_path, 'main', branch)
            if count > 0:
                print(f"  ✓ {file_path.parent.parent.name}/tokens/{file_path.name}: updated {count} URL(s)")
                total_updates += count
    
    # Update display table JSON
    print("\nDisplay table:")
    display_table = tts_dir / 'display-table' / 'kt_all_teams_grid.json'
    if display_table.exists():
        count = update_urls_in_json(display_table, 'main', branch)
        if count > 0:
            print(f"  ✓ {display_table.name}: updated {count} URL(s)")
            total_updates += count
    
    print("\n" + "=" * 60)
    print(f"✓ Total: {total_updates} URLs updated to use branch '{branch}'")


if __name__ == '__main__':
    main()
