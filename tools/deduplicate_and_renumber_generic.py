#!/usr/bin/env python3
"""
Remove duplicate images from _generic folder and renumber sequentially.

This tool:
1. Identifies duplicates using perceptual hash
2. Removes duplicates (keeping the first occurrence)
3. Renumbers all remaining files sequentially (001, 002, 003...)
4. Regenerates metadata
"""

import json
import shutil
from pathlib import Path
from collections import defaultdict

GENERIC_FOLDER = Path("layers/warcom/extracted/_generic")
METADATA_FILE = GENERIC_FOLDER / "generic-artwork-metadata.json"
BACKUP_FOLDER = GENERIC_FOLDER / "_backup_duplicates"


def hamming_distance(hash1: str, hash2: str) -> int:
    """Compute Hamming distance between two hex hash strings."""
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 999
    
    int1 = int(hash1, 16)
    int2 = int(hash2, 16)
    xor = int1 ^ int2
    distance = bin(xor).count('1')
    return distance


def find_duplicates_to_remove(metadata_path: Path, threshold: int = 5):
    """
    Find duplicate images to remove.
    
    Returns set of filenames to remove (keeping the first from each duplicate group).
    """
    
    with metadata_path.open("r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    images = metadata["images"]
    
    print("=" * 70)
    print("Finding Duplicates for Removal")
    print("=" * 70)
    print(f"Total images: {len(images)}")
    print(f"Perceptual hash threshold: {threshold}/64 bits")
    print("Strategy: Keep first occurrence, remove subsequent duplicates\n")
    
    to_remove = set()
    kept_images = []
    
    for i, img in enumerate(images):
        if img["filename"] in to_remove:
            continue  # Already marked for removal
        
        # Check against all kept images
        is_duplicate = False
        for kept_img in kept_images:
            phash1 = img.get("perceptual_hash", "")
            phash2 = kept_img.get("perceptual_hash", "")
            
            if not phash1 or not phash2:
                continue
            
            distance = hamming_distance(phash1, phash2)
            
            if distance <= threshold:
                print(f"  Duplicate found (distance={distance}):")
                print(f"    KEEP:   {kept_img['filename']}")
                print(f"    REMOVE: {img['filename']}")
                to_remove.add(img["filename"])
                is_duplicate = True
                break
        
        if not is_duplicate:
            kept_images.append(img)
    
    print(f"\n{'=' * 70}")
    print(f"Summary:")
    print(f"  Original count: {len(images)}")
    print(f"  To remove: {len(to_remove)}")
    print(f"  Final count: {len(images) - len(to_remove)}")
    print(f"{'=' * 70}\n")
    
    return to_remove


def backup_and_remove_duplicates(generic_folder: Path, to_remove: set):
    """Backup duplicates to subfolder and remove them."""
    
    if not to_remove:
        print("No duplicates to remove.")
        return
    
    # Create backup folder
    backup_folder = generic_folder / "_backup_duplicates"
    backup_folder.mkdir(exist_ok=True)
    
    print(f"Backing up and removing {len(to_remove)} duplicate files...")
    
    for filename in sorted(to_remove):
        src = generic_folder / filename
        dst = backup_folder / filename
        
        if src.exists():
            print(f"  {filename} → _backup_duplicates/")
            shutil.move(str(src), str(dst))
        else:
            print(f"  ⚠ Warning: {filename} not found")
    
    print(f"✓ Moved {len(to_remove)} files to {backup_folder}\n")


def renumber_sequential(generic_folder: Path):
    """Renumber all generic artwork files sequentially without gaps."""
    
    # Get all image files
    image_files = []
    for ext in [".jpg", ".jpeg", ".png"]:
        image_files.extend(generic_folder.glob(f"generic-artwork-*{ext}"))
    
    # Sort by current number
    def get_number(path):
        try:
            return int(path.stem.split("-")[-1])
        except ValueError:
            return 999999
    
    image_files = sorted(image_files, key=get_number)
    
    print(f"Renumbering {len(image_files)} files sequentially...")
    print("=" * 70)
    
    # Create temporary names to avoid conflicts
    temp_renames = []
    for idx, old_path in enumerate(image_files, 1):
        temp_name = f"temp_{idx:03d}{old_path.suffix}"
        temp_path = generic_folder / temp_name
        temp_renames.append((old_path, temp_path))
    
    # First pass: rename to temp names
    for old_path, temp_path in temp_renames:
        old_path.rename(temp_path)
    
    # Second pass: rename to final names
    for idx, (_, temp_path) in enumerate(temp_renames, 1):
        final_name = f"generic-artwork-{idx:03d}{temp_path.suffix}"
        final_path = generic_folder / final_name
        
        old_num = get_number(temp_renames[idx-1][0])
        if old_num != idx:
            print(f"  {temp_renames[idx-1][0].name} → {final_name}")
        
        temp_path.rename(final_path)
    
    print(f"{'=' * 70}")
    print(f"✓ Renumbered {len(image_files)} files (001-{len(image_files):03d})\n")


def main():
    """Main entry point."""
    if not METADATA_FILE.exists():
        print(f"❌ Error: Metadata file not found: {METADATA_FILE}")
        print("Run 'poetry run python tools/regenerate_generic_metadata.py' first.")
        return
    
    print("\n🔍 STEP 1: Find duplicates\n")
    to_remove = find_duplicates_to_remove(METADATA_FILE, threshold=5)
    
    if to_remove:
        print(f"\n📦 STEP 2: Backup and remove duplicates\n")
        backup_and_remove_duplicates(GENERIC_FOLDER, to_remove)
    else:
        print("\n✓ No duplicates found, skipping removal\n")
    
    print(f"🔢 STEP 3: Renumber files sequentially\n")
    renumber_sequential(GENERIC_FOLDER)
    
    print(f"✅ COMPLETE!")
    print(f"\nNext step: Run 'poetry run python tools/regenerate_generic_metadata.py'")
    print(f"to regenerate metadata with new numbering.\n")


if __name__ == "__main__":
    main()
