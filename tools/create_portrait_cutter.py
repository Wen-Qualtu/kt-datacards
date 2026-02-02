"""
Create a portrait cutter template based on the landscape template.
"""
import cv2
import numpy as np
from pathlib import Path

def create_portrait_cutter(landscape_template_path: Path, portrait_card_path: Path, output_path: Path):
    """
    Create a portrait cutter template by analyzing the landscape template
    and applying similar corner rounding to portrait dimensions.
    """
    # Load landscape template
    landscape = cv2.imread(str(landscape_template_path), cv2.IMREAD_UNCHANGED)
    if landscape is None:
        print(f"Failed to load landscape template: {landscape_template_path}")
        return False
    
    # Load a portrait card to get dimensions
    portrait_card = cv2.imread(str(portrait_card_path), cv2.IMREAD_UNCHANGED)
    if portrait_card is None:
        print(f"Failed to load portrait card: {portrait_card_path}")
        return False
    
    print(f"Landscape template size: {landscape.shape[1]}x{landscape.shape[0]}")
    print(f"Portrait card size: {portrait_card.shape[1]}x{portrait_card.shape[0]}")
    
    # Get portrait dimensions
    portrait_height, portrait_width = portrait_card.shape[:2]
    
    # Create white image with alpha channel
    portrait_template = np.ones((portrait_height, portrait_width, 4), dtype=np.uint8) * 255
    
    # Analyze landscape corner rounding by checking transparency
    # Check top-left corner to find the rounded area
    landscape_alpha = landscape[:, :, 3]
    
    # Find the corner radius by checking where transparency starts
    # Scan diagonally from corner
    max_check = min(landscape.shape[0], landscape.shape[1]) // 4
    corner_radius = 0
    
    for i in range(max_check):
        # Check if pixel at (i, i) is transparent
        if landscape_alpha[i, i] == 0:
            corner_radius = i
        else:
            break
    
    if corner_radius == 0:
        # Alternative: find max distance from corner that's transparent
        for y in range(max_check):
            for x in range(max_check):
                if landscape_alpha[y, x] == 0:
                    corner_radius = max(corner_radius, int(np.sqrt(x*x + y*y)))
    
    print(f"Detected corner radius in landscape: ~{corner_radius} pixels")
    
    # Scale the radius proportionally if needed, or use same radius
    # For Kill Team cards, they should be same DPI, so use same radius
    radius = corner_radius if corner_radius > 0 else 50
    
    print(f"Using corner radius for portrait: {radius} pixels")
    
    # Create rounded corners by making corner areas transparent
    # We'll create a mask for each corner
    
    # Top-left corner
    for y in range(radius):
        for x in range(radius):
            # Calculate distance from corner
            dist = np.sqrt((radius - x) ** 2 + (radius - y) ** 2)
            if dist > radius:
                portrait_template[y, x, 3] = 0
    
    # Top-right corner
    for y in range(radius):
        for x in range(portrait_width - radius, portrait_width):
            dist = np.sqrt((x - (portrait_width - radius)) ** 2 + (radius - y) ** 2)
            if dist > radius:
                portrait_template[y, x, 3] = 0
    
    # Bottom-left corner
    for y in range(portrait_height - radius, portrait_height):
        for x in range(radius):
            dist = np.sqrt((radius - x) ** 2 + (y - (portrait_height - radius)) ** 2)
            if dist > radius:
                portrait_template[y, x, 3] = 0
    
    # Bottom-right corner
    for y in range(portrait_height - radius, portrait_height):
        for x in range(portrait_width - radius, portrait_width):
            dist = np.sqrt((x - (portrait_width - radius)) ** 2 + (y - (portrait_height - radius)) ** 2)
            if dist > radius:
                portrait_template[y, x, 3] = 0
    
    # Save
    cv2.imwrite(str(output_path), portrait_template)
    print(f"Created portrait cutter template: {output_path}")
    
    # Count transparent pixels
    transparent_count = np.sum(portrait_template[:, :, 3] == 0)
    print(f"  Transparent pixels: {transparent_count}")
    print(f"  White pixels: {portrait_height * portrait_width - transparent_count}")
    
    return True


if __name__ == '__main__':
    landscape_template = Path('config/pipelines/warcom/template-card-landscape-cutter.png')
    
    # Find a portrait card to use as reference
    portrait_card = Path('output/hand-of-the-archon/cards/equipment/hand-of-the-archon-chain-snare-front.png')
    
    output = Path('config/pipelines/warcom/template-card-portrait-cutter.png')
    
    if not landscape_template.exists():
        print(f"Error: Landscape template not found: {landscape_template}")
        exit(1)
    
    if not portrait_card.exists():
        # Try to find any portrait card
        from pathlib import Path
        output_dir = Path('output')
        portrait_cards = list(output_dir.glob('*/cards/equipment/*-front.png'))
        if portrait_cards:
            portrait_card = portrait_cards[0]
            print(f"Using portrait card: {portrait_card}")
        else:
            print("Error: No portrait cards found")
            exit(1)
    
    success = create_portrait_cutter(landscape_template, portrait_card, output)
    exit(0 if success else 1)
