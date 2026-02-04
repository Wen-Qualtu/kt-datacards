#!/usr/bin/env python3
"""Normalize custom token images to 512x512 (except special larger tokens)."""

import cv2
import numpy as np
from pathlib import Path

# Tokens that should be larger (28mm battlefield size)
LARGE_TOKENS = {
    'vespid-stingwings/skytorch.png': 716,  # 28mm = 1.4x
    'novitiates/novitiates-faith-points.png': 716,  # If this is also 28mm
}

TARGET_SIZE = 512

def resize_token(image_path: Path, target_size: int):
    """Resize token to target size while maintaining transparency and centering."""
    # Read with alpha channel
    img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"  ERROR: Could not read {image_path}")
        return False
    
    h, w = img.shape[:2]
    
    # If already correct size, skip
    if w == target_size and h == target_size:
        print(f"  SKIP: {image_path.parent.parent.name}/{image_path.name} already {w}x{h}")
        return True
    
    # Create transparent canvas
    if img.shape[2] == 4:  # Has alpha
        canvas = np.zeros((target_size, target_size, 4), dtype=np.uint8)
    else:  # No alpha, add it
        canvas = np.zeros((target_size, target_size, 4), dtype=np.uint8)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    
    # Calculate scaling to fit within target while maintaining aspect ratio
    scale = min(target_size / w, target_size / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    # Resize image
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    
    # Center on canvas
    x_offset = (target_size - new_w) // 2
    y_offset = (target_size - new_h) // 2
    canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
    
    # Save
    cv2.imwrite(str(image_path), canvas)
    print(f"  RESIZE: {image_path.parent.parent.name}/{image_path.name} {w}x{h} → {target_size}x{target_size}")
    return True


# Find all custom tokens
custom_tokens = list(Path('config/teams').rglob('custom-tokens/*.png'))
print(f"Found {len(custom_tokens)} custom tokens\n")

resized_count = 0
skipped_count = 0
large_count = 0

for token_path in sorted(custom_tokens):
    if token_path.name.startswith('_'):
        continue
    
    # Check if this should be a large token
    relative_path = f"{token_path.parent.parent.name}/{token_path.name}"
    
    if relative_path in LARGE_TOKENS:
        target = LARGE_TOKENS[relative_path]
        print(f"  LARGE: {relative_path} (target={target}x{target})")
        large_count += 1
        
        # Resize to exact large size if needed
        img = cv2.imread(str(token_path), cv2.IMREAD_UNCHANGED)
        h, w = img.shape[:2]
        if w != target or h != target:
            resized = cv2.resize(img, (target, target), interpolation=cv2.INTER_LANCZOS4)
            cv2.imwrite(str(token_path), resized)
            print(f"    Adjusted {w}x{h} → {target}x{target}")
        continue
    
    # Standard token - normalize to 512x512
    img = cv2.imread(str(token_path), cv2.IMREAD_UNCHANGED)
    h, w = img.shape[:2]
    
    if w == TARGET_SIZE and h == TARGET_SIZE:
        skipped_count += 1
        continue
    
    if resize_token(token_path, TARGET_SIZE):
        resized_count += 1

print(f"\n{'='*60}")
print(f"Summary:")
print(f"  Resized: {resized_count}")
print(f"  Skipped (already correct): {skipped_count}")
print(f"  Large tokens (special): {large_count}")
print(f"{'='*60}")
