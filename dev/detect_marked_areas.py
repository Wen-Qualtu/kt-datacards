"""
Detect manually marked areas on annotated images.
Looks for colored rectangles or annotations added by the user.
"""
import cv2
import numpy as np
from pathlib import Path


def detect_colored_rectangles(image_path: Path):
    """
    Detect colored rectangles/boxes drawn on an image.
    Returns bounding boxes of detected colored regions.
    """
    print(f"\nAnalyzing: {image_path.name}")
    
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"  ERROR: Could not load image")
        return []
    
    height, width = img.shape[:2]
    print(f"  Image size: {width}x{height}")
    
    # Convert to HSV for better color detection
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Detect colored regions (looking for bright/saturated colors)
    # This will find green, blue, red boxes added by user
    
    # Create mask for highly saturated colors (annotations)
    lower_sat = np.array([0, 100, 100])
    upper_sat = np.array([180, 255, 255])
    mask = cv2.inRange(hsv, lower_sat, upper_sat)
    
    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter for large rectangular contours
    boxes = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 1000:  # Skip small noise
            continue
        
        # Get bounding rectangle
        x, y, w, h = cv2.boundingRect(contour)
        
        # Calculate as percentage of page size
        x_pct = x / width
        y_pct = y / height
        w_pct = w / width
        h_pct = h / height
        x2_pct = (x + w) / width
        y2_pct = (y + h) / height
        
        # Detect color of the box
        box_color = img[y+5, x+5]  # Sample a pixel inside the box
        color_name = "unknown"
        if box_color[1] > box_color[0] and box_color[1] > box_color[2]:
            color_name = "GREEN"
        elif box_color[0] > box_color[1] and box_color[0] > box_color[2]:
            color_name = "BLUE"
        elif box_color[2] > box_color[0] and box_color[2] > box_color[1]:
            color_name = "RED"
        
        boxes.append({
            'x': x, 'y': y, 'w': w, 'h': h,
            'x_pct': x_pct, 'y_pct': y_pct,
            'w_pct': w_pct, 'h_pct': h_pct,
            'x2_pct': x2_pct, 'y2_pct': y2_pct,
            'area': area,
            'color': color_name
        })
    
    # Sort by area (largest first)
    boxes.sort(key=lambda b: b['area'], reverse=True)
    
    print(f"  Found {len(boxes)} marked areas:")
    for i, box in enumerate(boxes, 1):
        print(f"\n  Box {i} ({box['color']}):")
        print(f"    Pixels: ({box['x']}, {box['y']}) to ({box['x']+box['w']}, {box['y']+box['h']})")
        print(f"    Size: {box['w']}x{box['h']}")
        print(f"    Percentages:")
        print(f"      x1: {box['x_pct']:.4f} ({box['x_pct']*100:.2f}%)")
        print(f"      y1: {box['y_pct']:.4f} ({box['y_pct']*100:.2f}%)")
        print(f"      x2: {box['x2_pct']:.4f} ({box['x2_pct']*100:.2f}%)")
        print(f"      y2: {box['y2_pct']:.4f} ({box['y2_pct']*100:.2f}%)")
        print(f"      width: {box['w_pct']:.4f} ({box['w_pct']*100:.2f}%)")
        print(f"      height: {box['h_pct']:.4f} ({box['h_pct']*100:.2f}%)")
    
    return boxes


if __name__ == '__main__':
    # Analyze annotated images
    annotated_images = [
        Path('dev/angels-of-death_page1_clean.png'),
        Path('dev/angels-of-death_page12_clean.png'),
    ]
    
    print("=" * 60)
    print("Detecting Marked Areas")
    print("=" * 60)
    
    all_results = {}
    for img_path in annotated_images:
        if not img_path.exists():
            print(f"\nWARNING: {img_path} not found")
            continue
        
        boxes = detect_colored_rectangles(img_path)
        all_results[img_path.stem] = boxes
    
    print("\n" + "=" * 60)
    print("Summary - Extraction Coordinates")
    print("=" * 60)
    
    # Identify the marked areas
    if 'angels-of-death_page1_clean' in all_results:
        boxes = all_results['angels-of-death_page1_clean']
        print("\nPage 1 (Card Backside Icons):")
        
        # Portrait icon (green - detected as unknown or green)
        portrait = [b for b in boxes if b['color'] in ['GREEN', 'unknown'] and b['area'] > 10000]
        if portrait:
            b = portrait[0]
            print(f"  Portrait icon: x1={b['x_pct']:.4f}, y1={b['y_pct']:.4f}, x2={b['x2_pct']:.4f}, y2={b['y2_pct']:.4f}")
        
        # Landscape icon (blue - pick the one at top or largest blue box)
        landscape = [b for b in boxes if b['color'] == 'BLUE']
        if landscape:
            # Use the top-most blue box (smallest y1 value)
            landscape.sort(key=lambda x: x['y_pct'])
            b = landscape[0]
            print(f"  Landscape icon: x1={b['x_pct']:.4f}, y1={b['y_pct']:.4f}, x2={b['x2_pct']:.4f}, y2={b['y2_pct']:.4f}")
    
    if 'angels-of-death_page12_clean' in all_results:
        boxes = all_results['angels-of-death_page12_clean']
        print("\nPage 12 (Token Bag Icon):")
        
        # Token bag icon (large blue box)
        token = [b for b in boxes if b['area'] > 100000]
        if token:
            b = token[0]
            print(f"  Token bag icon: x1={b['x_pct']:.4f}, y1={b['y_pct']:.4f}, x2={b['x2_pct']:.4f}, y2={b['y2_pct']:.4f}")
    
    print("\n" + "=" * 60)
    print("Code-ready coordinates:")
    print("=" * 60)
    
    if 'angels-of-death_page1_clean' in all_results:
        boxes = all_results['angels-of-death_page1_clean']
        portrait = [b for b in boxes if b['color'] in ['GREEN', 'unknown'] and b['area'] > 10000]
        landscape = [b for b in boxes if b['color'] == 'BLUE']
        landscape.sort(key=lambda x: x['y_pct'])
        
        if portrait and landscape:
            p = portrait[0]
            l = landscape[0]
            print("\n# Page 1 - Card backside icons")
            print(f"portrait_x1_pct = {p['x_pct']:.4f}  # {p['x_pct']*100:.2f}%")
            print(f"portrait_y1_pct = {p['y_pct']:.4f}  # {p['y_pct']*100:.2f}%")
            print(f"portrait_x2_pct = {p['x2_pct']:.4f}  # {p['x2_pct']*100:.2f}%")
            print(f"portrait_y2_pct = {p['y2_pct']:.4f}  # {p['y2_pct']*100:.2f}%")
            print()
            print(f"landscape_x1_pct = {l['x_pct']:.4f}  # {l['x_pct']*100:.2f}%")
            print(f"landscape_y1_pct = {l['y_pct']:.4f}  # {l['y_pct']*100:.2f}%")
            print(f"landscape_x2_pct = {l['x2_pct']:.4f}  # {l['x2_pct']*100:.2f}%")
            print(f"landscape_y2_pct = {l['y2_pct']:.4f}  # {l['y2_pct']*100:.2f}%")
    
    if 'angels-of-death_page12_clean' in all_results:
        boxes = all_results['angels-of-death_page12_clean']
        token = [b for b in boxes if b['area'] > 100000]
        
        if token:
            t = token[0]
            print("\n# Token bag icon page")
            print(f"token_x1_pct = {t['x_pct']:.4f}  # {t['x_pct']*100:.2f}%")
            print(f"token_y1_pct = {t['y_pct']:.4f}  # {t['y_pct']*100:.2f}%")
            print(f"token_x2_pct = {t['x2_pct']:.4f}  # {t['x2_pct']*100:.2f}%")
            print(f"token_y2_pct = {t['y2_pct']:.4f}  # {t['y2_pct']*100:.2f}%")
