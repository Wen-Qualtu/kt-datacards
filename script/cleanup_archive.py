"""
Cleanup archive folder to only keep GUIDs as filenames.
Extracts the GUID from nested archive names and renames files.
"""
import os
import re
import shutil

def extract_guid(filename):
    """Extract GUID from filename (last occurrence in nested names)."""
    # Look for GUID pattern (8-4-4-4-12 hex digits)
    guid_pattern = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
    matches = re.findall(guid_pattern, filename, re.IGNORECASE)
    if matches:
        # Return the last GUID found (the original one)
        return matches[-1]
    return None

def cleanup_archive():
    """Rename all archive files to just their GUID."""
    archive_dir = 'input/_archive'
    
    if not os.path.exists(archive_dir):
        print(f"Archive directory not found: {archive_dir}")
        return
    
    files_renamed = 0
    files_skipped = 0
    
    print(f"Cleaning up archive directory: {archive_dir}\n")
    
    for filename in os.listdir(archive_dir):
        if not filename.endswith('.pdf'):
            continue
        
        guid = extract_guid(filename)
        if not guid:
            print(f"⚠️  No GUID found in: {filename}")
            files_skipped += 1
            continue
        
        new_filename = f"{guid}.pdf"
        
        # Skip if already correctly named
        if filename == new_filename:
            files_skipped += 1
            continue
        
        old_path = os.path.join(archive_dir, filename)
        new_path = os.path.join(archive_dir, new_filename)
        
        # Handle duplicates by keeping the file (don't overwrite)
        if os.path.exists(new_path):
            print(f"✓ Duplicate found, removing: {filename}")
            os.remove(old_path)
        else:
            os.rename(old_path, new_path)
            print(f"✓ Renamed: {filename[:60]}... → {new_filename}")
        
        files_renamed += 1
    
    print(f"\n{'='*60}")
    print(f"Cleanup complete!")
    print(f"Files renamed/removed: {files_renamed}")
    print(f"Files skipped: {files_skipped}")
    print(f"{'='*60}")

if __name__ == '__main__':
    cleanup_archive()
