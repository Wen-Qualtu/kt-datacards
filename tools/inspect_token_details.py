import cv2
import numpy as np
import sys

token_path = "layers/warcom/extracted/battleclade/tokens-processed/omniscanner-token.png"
img = cv2.imread(token_path, cv2.IMREAD_UNCHANGED)

if img is None:
    print(f"ERROR: Could not load {token_path}")
    sys.exit(1)

print(f"Shape: {img.shape}")
print(f"Channels: {img.shape[2] if len(img.shape) > 2 else 1}")

if len(img.shape) > 2 and img.shape[2] == 4:
    # Has alpha channel
    bgr = img[:,:,:3]
    alpha = img[:,:,3]
    
    print(f"\nAlpha channel stats:")
    print(f"  Min: {alpha.min()}, Max: {alpha.max()}")
    print(f"  Transparent (0): {(alpha == 0).sum()}")
    print(f"  Opaque (255): {(alpha == 255).sum()}")
    print(f"  Total pixels: {alpha.size}")
    
    # Check if there are white pixels in the opaque areas
    opaque_mask = alpha == 255
    white_in_opaque = ((bgr[:,:,0] > 250) & (bgr[:,:,1] > 250) & (bgr[:,:,2] > 250) & opaque_mask).sum()
    print(f"\nWhite pixels (BGR > 250) in OPAQUE areas: {white_in_opaque}")
    
    # Check the background (transparent areas)
    transparent_mask = alpha == 0
    if transparent_mask.sum() > 0:
        print(f"\nTransparent area colors:")
        print(f"  Average BGR in transparent: {bgr[transparent_mask].mean(axis=0)}")
    
    # Show corners (should be transparent)
    print(f"\nCorner alpha values (should be 0 = transparent):")
    print(f"  Top-left: {alpha[0,0]}")
    print(f"  Top-right: {alpha[0,-1]}")
    print(f"  Bottom-left: {alpha[-1,0]}")
    print(f"  Bottom-right: {alpha[-1,-1]}")
else:
    print("No alpha channel - image is BGR only (fully opaque)")
    bgr = img if len(img.shape) > 2 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    
    # Count white pixels
    white_pixels = ((bgr[:,:,0] > 250) & (bgr[:,:,1] > 250) & (bgr[:,:,2] > 250)).sum()
    print(f"\nWhite pixels (BGR > 250): {white_pixels} / {bgr.shape[0] * bgr.shape[1]}")
