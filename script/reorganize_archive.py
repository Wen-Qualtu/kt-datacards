"""
Reorganize archive folder to have team subfolders.
Moves GUID files from flat structure to team-based subfolders.
"""
import os
import re
from pathlib import Path
import shutil

def find_team_for_guid(guid, input_folder):
    """Find which team folder contains a PDF with this GUID in its name."""
    # Search through all team folders in input
    for team_dir in Path(input_folder).iterdir():
        if not team_dir.is_dir():
            continue
        if team_dir.name.startswith('_'):  # Skip _archive, _raw
            continue
        
        # Check if any PDF in this team folder references this GUID
        for pdf_file in team_dir.glob('*.pdf'):
            if guid.lower() in pdf_file.name.lower():
                return team_dir.name
    
    return None

def reorganize_archive():
    """Move archive files into team subfolders."""
    archive_dir = Path('input/_archive')
    input_dir = Path('input')
    
    if not archive_dir.exists():
        print(f"Archive directory not found: {archive_dir}")
        return
    
    files_moved = 0
    files_orphaned = 0
    
    print(f"Reorganizing archive into team subfolders...\n")
    
    # Get all PDF files in the root of archive (not in subfolders)
    for pdf_file in archive_dir.glob('*.pdf'):
        guid = pdf_file.stem  # Filename without .pdf
        
        # Find which team this GUID belongs to
        team_name = find_team_for_guid(guid, input_dir)
        
        if team_name:
            # Create team subfolder in archive
            team_archive_folder = archive_dir / team_name
            team_archive_folder.mkdir(parents=True, exist_ok=True)
            
            # Move file to team subfolder
            new_path = team_archive_folder / pdf_file.name
            if new_path.exists():
                print(f"  ✓ Skipped (already exists): {team_name}/{pdf_file.name}")
            else:
                shutil.move(str(pdf_file), str(new_path))
                print(f"  ✓ Moved to {team_name}/{pdf_file.name}")
            files_moved += 1
        else:
            print(f"  ⚠️  No team found for: {pdf_file.name}")
            files_orphaned += 1
    
    print(f"\n{'='*60}")
    print(f"Reorganization complete!")
    print(f"Files moved: {files_moved}")
    print(f"Orphaned files: {files_orphaned}")
    print(f"{'='*60}")

if __name__ == '__main__':
    reorganize_archive()
