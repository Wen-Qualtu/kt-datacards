#!/usr/bin/env python3
"""
Regenerate metadata for generic background images in _generic folder.

This tool:
1. Scans all images in the _generic folder
2. Renames any team-specific filenames to generic-artwork-XXX.ext format
3. Computes exact hash (SHA256) and perceptual hash (pHash) for each image
4. Generates updated generic-artwork-metadata.json
"""

import json
import hashlib
from pathlib import Path
from PIL import Image
import cv2
import numpy as np

GENERIC_FOLDER = Path("layers/warcom/extracted/_generic")


def compute_image_hash(image_path: Path) -> str:
    """Compute SHA256 hash of image file."""
    sha256 = hashlib.sha256()
    with image_path.open("rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_perceptual_hash(image_path: Path, hash_size: int = 16) -> str:
    """
    Compute perceptual hash (pHash) for visual similarity detection.
    Similar images will have similar hashes even if compression differs.
    """
    try:
        # Read image bytes
        image_bytes = image_path.read_bytes()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return "0000000000000000"
        
        # Convert to grayscale and resize
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (hash_size, hash_size), interpolation=cv2.INTER_AREA)
        
        # Compute DCT and extract low frequencies
        dct = cv2.dct(np.float32(resized))
        dct_low = dct[:8, :8]
        median = np.median(dct_low)
        
        # Create binary hash
        hash_bits = (dct_low > median).flatten()
        hash_int = 0
        for bit in hash_bits:
            hash_int = (hash_int << 1) | int(bit)
        
        return format(hash_int, '016x')
    except Exception as e:
        print(f"⚠ Warning: Could not compute pHash for {image_path.name}: {e}")
        return "0000000000000000"


def rename_team_files(generic_folder: Path) -> None:
    """Rename any team-specific files to generic-artwork-XXX format."""
    image_files = sorted([
        f for f in generic_folder.glob("*")
        if f.suffix.lower() in [".jpg", ".jpeg", ".png"] 
        and not f.name.startswith("generic-artwork-")
        and f.name != "generic-artwork-metadata.json"
    ])
    
    if not image_files:
        print("✓ No team-specific files to rename")
        return
    
    # Find all existing generic numbers
    existing_generic = []
    for ext in [".jpg", ".jpeg", ".png"]:
        existing_generic.extend(generic_folder.glob(f"generic-artwork-*{ext}"))
    
    used_numbers = set()
    for f in existing_generic:
        try:
            num = int(f.stem.split("-")[-1])
            used_numbers.add(num)
        except ValueError:
            pass
    
    print(f"   Found {len(existing_generic)} existing generic files")
    print(f"  Existing numbers in use: {sorted(used_numbers)[:20]}...")
    
    # Find next available number
    next_num = 1
    
    print(f"Found {len(image_files)} team-specific files to rename:")
    for old_file in image_files:
        # Find next available number starting from current position
        while next_num in used_numbers:
            next_num += 1
        
        new_name = f"generic-artwork-{next_num:03d}{old_file.suffix}"
        new_path = generic_folder / new_name
        print(f"  {old_file.name} → {new_name}")
        old_file.rename(new_path)
        used_numbers.add(next_num)
        next_num += 1  # Move to next number for next iteration
    
    print(f"✓ Renamed {len(image_files)} files")


def generate_metadata(generic_folder: Path) -> None:
    """Generate metadata JSON for all generic background images."""
    
    # Get all image files
    image_files = []
    for ext in [".jpg", ".jpeg", ".png"]:
        image_files.extend(generic_folder.glob(f"generic-artwork-*{ext}"))
    image_files = sorted(image_files)
    
    print(f"\nProcessing {len(image_files)} images...")
    
    images_metadata = []
    
    for idx, image_path in enumerate(image_files, 1):
        print(f"  [{idx}/{len(image_files)}] {image_path.name}")
        
        # Load image for dimensions
        img = Image.open(image_path)
        width, height = img.size
        aspect_ratio = round(width / height, 2)
        orientation = "landscape" if width >= height else "portrait"
        file_size_kb = image_path.stat().st_size // 1024
        
        # Compute hashes
        image_hash = compute_image_hash(image_path)
        perceptual_hash = compute_perceptual_hash(image_path)
        
        images_metadata.append({
            "filename": image_path.name,
            "page_number": 0,  # Generic backgrounds have no source page
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
            "file_size_kb": file_size_kb,
            "orientation": orientation,
            "xref": 0,  # No xref for manually curated images
            "image_hash": image_hash,
            "perceptual_hash": perceptual_hash
        })
    
    # Create metadata JSON
    metadata = {
        "team": "generic",
        "pdf": "multiple",
        "total_images": len(images_metadata),
        "images": images_metadata
    }
    
    # Write metadata file
    metadata_path = generic_folder / "generic-artwork-metadata.json"
    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Generated metadata for {len(images_metadata)} images")
    print(f"✓ Saved to {metadata_path}")


def main():
    """Main entry point."""
    if not GENERIC_FOLDER.exists():
        print(f"❌ Error: Generic folder not found: {GENERIC_FOLDER}")
        return
    
    print("=" * 60)
    print("Generic Background Metadata Regeneration")
    print("=" * 60)
    
    # Step 1: Rename any team-specific files
    print("\nStep 1: Renaming team-specific files...")
    rename_team_files(GENERIC_FOLDER)
    
    # Step 2: Generate metadata
    print("\nStep 2: Generating metadata...")
    generate_metadata(GENERIC_FOLDER)
    
    print("\n" + "=" * 60)
    print("✓ Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
