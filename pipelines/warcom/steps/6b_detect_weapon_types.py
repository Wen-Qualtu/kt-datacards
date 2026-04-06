"""
Step 6b: Detect Weapon Types from Datacard Icons

Detects weapon types (melee/ranged) by analyzing icons on datacards.
Uses visual detection to identify bullet icons (ranged) vs sword icons (melee).

Input:  layers/warcom/extracted/{team}/cards/*_landscape.pdf
        output/{team}/statlines/roster.json (for weapon names)
Output: config/weapon_types_detected.json

Strategy:
- Render weapon region and detect orange icons
- Bullet icons (ranged): 2-3 parts when split by shape
- Sword icons (melee): 1 part
- Match icons to weapons by Y position (top to bottom)
- Validate: icon count == weapon count

Usage:
    python pipelines/warcom/steps/6b_detect_weapon_types.py
    python pipelines/warcom/steps/6b_detect_weapon_types.py --teams kommandos blooded
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
import fitz

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def detect_weapon_icons(pdf_path: Path) -> List[Dict]:
    """Detect weapon icons from a datacard PDF.
    
    Returns list of icons with Y position and classification.
    """
    doc = fitz.open(pdf_path)
    page = doc[0]
    
    page_height = page.rect.height
    page_width = page.rect.width
    
    # Render at 3x zoom for better icon detection
    zoom = 3
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    
    # Convert to numpy array
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    
    # Convert to BGR for OpenCV
    if pix.n == 4:  # RGBA
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:  # RGB
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    
    # Weapon region in zoomed coordinates (15-80% of page height)
    weapon_y1 = int(page_height * 0.15 * zoom)
    weapon_y2 = int(page_height * 0.80 * zoom)
    icon_x2 = int(page_width * 0.10 * zoom)  # Icons in leftmost 10%
    
    # Extract weapon region
    weapon_strip = img[weapon_y1:weapon_y2, 0:icon_x2]
    
    # Convert to HSV for color-based detection
    hsv = cv2.cvtColor(weapon_strip, cv2.COLOR_BGR2HSV)
    
    # Orange color range for weapon icons (HSV ~9, 220, 241)
    lower_orange = np.array([5, 150, 180])
    upper_orange = np.array([15, 255, 255])
    
    # Create mask for orange pixels
    orange_mask = cv2.inRange(hsv, lower_orange, upper_orange)
    
    # Find contours (icon shapes)
    contours, _ = cv2.findContours(orange_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter and collect icon components
    icons = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        
        # Filter by size (icons are small, 30-1000 pixels at 3x zoom)
        if 30 < area < 1000 and 5 < w < 50 and 5 < h < 50:
            icons.append({
                "y": y + weapon_y1,
                "x": x,
                "width": w,
                "height": h,
                "area": area,
                "y_original": (y + weapon_y1) / zoom
            })
    
    # Merge icons at same Y position (within 5 pixels in original coords)
    merged_icons = []
    used = set()
    sorted_icons = sorted(icons, key=lambda x: x["y_original"])
    
    for i, icon in enumerate(sorted_icons):
        if i in used:
            continue
        
        # Find all icons within 5 pixels vertically
        group = [icon]
        for j in range(i+1, len(sorted_icons)):
            if abs(sorted_icons[j]["y_original"] - icon["y_original"]) < 5:
                group.append(sorted_icons[j])
                used.add(j)
        
        # Merge group
        avg_y = sum(ic["y_original"] for ic in group) / len(group)
        total_area = sum(ic["area"] for ic in group)
        parts = len(group)
        
        # Classify based on number of parts
        # Bullet icons (ranged): 2-3 parts
        # Sword icons (melee): 1 part
        weapon_type = "ranged" if parts >= 2 else "melee"
        
        merged_icons.append({
            "y": avg_y,
            "parts": parts,
            "total_area": total_area,
            "type": weapon_type
        })
    
    doc.close()
    return sorted(merged_icons, key=lambda x: x["y"])


def extract_weapon_names(json_path: Path) -> List[Dict]:
    """Extract weapon names from roster JSON."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    weapons_with_source = []
    for operative in data.get("operatives", []):
        for weapon in operative.get("weapons", []):
            weapons_with_source.append({
                "name": weapon.get("name"),
                "operative": operative.get("name"),
                "source_file": operative.get("source_file")
            })
    
    return weapons_with_source


def detect_weapon_types_for_team(team_name: str) -> Dict[str, str]:
    """Detect weapon types for all cards in a team.
    
    Returns dict mapping weapon names to types ('melee' or 'ranged').
    """
    cards_dir = Path(f"layers/warcom/extracted/{team_name}/cards")
    roster_path = Path(f"output/{team_name}/statlines/roster.json")
    
    if not cards_dir.exists():
        logger.warning(f"No cards directory for {team_name}")
        return {}
    
    if not roster_path.exists():
        logger.warning(f"No roster.json for {team_name}")
        return {}
    
    # Get all weapons from roster
    all_weapons = extract_weapon_names(roster_path)
    
    # Group weapons by source file
    weapons_by_file = {}
    for weapon in all_weapons:
        source_file = weapon["source_file"]
        if source_file not in weapons_by_file:
            weapons_by_file[source_file] = []
        weapons_by_file[source_file].append(weapon)
    
    # Detect icons for each card
    weapon_types = {}
    success_count = 0
    failure_count = 0
    
    for source_file, weapons in weapons_by_file.items():
        pdf_path = cards_dir / source_file
        
        if not pdf_path.exists():
            logger.warning(f"Card not found: {pdf_path}")
            continue
        
        try:
            icons = detect_weapon_icons(pdf_path)
            
            if not icons:
                logger.warning(f"{source_file}: No icons detected")
                failure_count += len(weapons)
                continue
            
            # Strategy: Match icons to weapons by Y-position order
            # - Icons are already sorted by Y position from detect_weapon_icons()
            # - Weapons are in roster order (should match Y position)
            # - If icons > weapons: extra icons from abilities, use first N icons
            # - If icons < weapons: missing icons, log error
            
            if len(icons) < len(weapons):
                logger.warning(
                    f"{source_file}: Not enough icons "
                    f"({len(icons)} icons vs {len(weapons)} weapons)"
                )
                logger.warning(f"  Weapons: {[w['name'] for w in weapons]}")
                failure_count += len(weapons)
                continue
            
            # Take first N icons (skip extra icons from abilities)
            icons_to_use = icons[:len(weapons)]
            
            if len(icons) > len(weapons):
                logger.info(
                    f"{source_file}: Using first {len(weapons)} of {len(icons)} icons "
                    f"(extra icons likely from abilities)"
                )
            
            # Match icons to weapons by order
            for weapon, icon in zip(weapons, icons_to_use):
                weapon_types[weapon["name"]] = icon["type"]
            
            success_count += len(weapons)
            
        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {e}")
            failure_count += len(weapons)
    
    logger.info(
        f"  {team_name}: {success_count} weapons classified, "
        f"{failure_count} failed"
    )
    
    return weapon_types


def main():
    parser = argparse.ArgumentParser(
        description='Detect weapon types from datacard icons'
    )
    parser.add_argument(
        '--teams',
        nargs='*',
        help='Specific teams to process (default: all teams)'
    )
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("Weapon Type Detection (Icon-Based)")
    logger.info("="*60)
    
    # Find all teams
    output_dir = Path("output")
    if args.teams:
        team_dirs = [output_dir / team for team in args.teams]
    else:
        team_dirs = sorted([d for d in output_dir.iterdir() if d.is_dir()])
    
    logger.info(f"Teams to process: {len(team_dirs)}")
    logger.info("")
    
    all_weapon_types = {}
    
    for team_dir in team_dirs:
        team_name = team_dir.name
        weapon_types = detect_weapon_types_for_team(team_name)
        all_weapon_types.update(weapon_types)
    
    # Save results
    output_path = Path("config/weapon_types_detected.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_weapon_types, f, indent=2, ensure_ascii=False, sort_keys=True)
    
    logger.info("")
    logger.info("="*60)
    logger.info(f"Total weapons classified: {len(all_weapon_types)}")
    ranged_count = sum(1 for t in all_weapon_types.values() if t == "ranged")
    melee_count = sum(1 for t in all_weapon_types.values() if t == "melee")
    logger.info(f"  Ranged: {ranged_count}")
    logger.info(f"  Melee: {melee_count}")
    logger.info(f"Saved to: {output_path}")
    logger.info("="*60)


if __name__ == '__main__':
    main()
