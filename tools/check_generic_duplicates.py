#!/usr/bin/env python3
"""
Check for duplicate images in the _generic folder using exact and perceptual hashes.
"""

import json
from pathlib import Path
from collections import defaultdict

GENERIC_FOLDER = Path("layers/warcom/extracted/_generic")
METADATA_FILE = GENERIC_FOLDER / "generic-artwork-metadata.json"


def hamming_distance(hash1: str, hash2: str) -> int:
    """Compute Hamming distance between two hex hash strings."""
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 999
    
    int1 = int(hash1, 16)
    int2 = int(hash2, 16)
    xor = int1 ^ int2
    distance = bin(xor).count('1')
    return distance


def find_duplicates(metadata_path: Path, threshold: int = 15):
    """Find duplicate images using exact and perceptual hashes."""
    
    with metadata_path.open("r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    images = metadata["images"]
    
    print("=" * 70)
    print("Duplicate Image Detection")
    print("=" * 70)
    print(f"Total images: {len(images)}")
    print(f"Perceptual hash threshold: {threshold}/64 bits\n")
    
    # Check for exact hash duplicates
    exact_hash_map = defaultdict(list)
    for img in images:
        exact_hash_map[img["image_hash"]].append(img["filename"])
    
    exact_duplicates = {k: v for k, v in exact_hash_map.items() if len(v) > 1}
    
    if exact_duplicates:
        print(f"🔴 Found {len(exact_duplicates)} groups of EXACT duplicates (byte-identical):")
        for hash_val, filenames in exact_duplicates.items():
            print(f"  Hash {hash_val[:16]}... ({len(filenames)} files):")
            for fname in filenames:
                print(f"    - {fname}")
        print()
    else:
        print("✓ No exact duplicates found\n")
    
    # Check for perceptual hash duplicates
    print(f"Checking for visually similar images (threshold ≤ {threshold} bits)...")
    
    similar_pairs = []
    
    for i, img1 in enumerate(images):
        for j, img2 in enumerate(images[i+1:], i+1):
            phash1 = img1.get("perceptual_hash", "")
            phash2 = img2.get("perceptual_hash", "")
            
            if not phash1 or not phash2:
                continue
            
            distance = hamming_distance(phash1, phash2)
            
            if distance <= threshold:
                similar_pairs.append({
                    "file1": img1["filename"],
                    "file2": img2["filename"],
                    "distance": distance,
                    "phash1": phash1,
                    "phash2": phash2,
                    "size1": f"{img1['width']}x{img1['height']}",
                    "size2": f"{img2['width']}x{img2['height']}"
                })
    
    if similar_pairs:
        print(f"\n🟡 Found {len(similar_pairs)} pairs of visually similar images:")
        similar_pairs.sort(key=lambda x: x["distance"])
        
        for pair in similar_pairs:
            print(f"\n  Distance: {pair['distance']}/64 bits")
            print(f"    {pair['file1']} ({pair['size1']})")
            print(f"    {pair['file2']} ({pair['size2']})")
            print(f"    pHash1: {pair['phash1']}")
            print(f"    pHash2: {pair['phash2']}")
    else:
        print(f"✓ No visually similar images found (threshold ≤ {threshold} bits)")
    
    print("\n" + "=" * 70)
    print("Summary:")
    print(f"  Exact duplicates: {len(exact_duplicates)} groups")
    print(f"  Similar pairs: {len(similar_pairs)} pairs")
    print("=" * 70)
    
    return exact_duplicates, similar_pairs


def main():
    """Main entry point."""
    if not METADATA_FILE.exists():
        print(f"❌ Error: Metadata file not found: {METADATA_FILE}")
        print("Run 'poetry run python tools/regenerate_generic_metadata.py' first.")
        return
    
    find_duplicates(METADATA_FILE, threshold=15)


if __name__ == "__main__":
    main()
