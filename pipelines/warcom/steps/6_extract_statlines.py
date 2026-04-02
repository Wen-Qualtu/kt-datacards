"""
Step 6: Extract Statlines from Datacards

Extracts operative characteristics (APL, Movement, Save, Wounds) and weapon profiles
from classified datacard PDFs using coordinate-based region extraction.

Input:  layers/warcom/extracted/{team}/cards/*_landscape.pdf
Output: output/{team}/statlines/roster.json

Architecture:
- Uses coordinate-based region extraction (not text order)
- Top-left region: Operative name
- Top-right region: Stats box (APL, MOVE, SAVE, WOUNDS)
- Middle region: Weapons table
- Only processes landscape cards (datacards have stats)

Usage:
    python pipelines/warcom/steps/6_extract_statlines.py
    python pipelines/warcom/steps/6_extract_statlines.py --teams kommandos battleclade
    python pipelines/warcom/steps/6_extract_statlines.py --force
"""

import argparse
import json
import logging
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def extract_statlines_from_pdf(pdf_path: Path) -> Dict[str, Any]:
    """Extract complete stat profile from a datacard PDF using coordinate regions."""
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            doc.close()
            return _empty_operative(pdf_path.name, "No pages in PDF")
        
        page = doc[0]
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height
        
        # Get all text blocks with coordinates
        blocks_dict = page.get_text("dict")
        blocks = blocks_dict.get("blocks", [])
        
        # Extract from specific regions using block positions
        # Name: Top-left corner (x < 60%, y < 15)
        name = _extract_name_from_blocks(blocks, page_width, page_height)
        
        # Stats: Top-right corner (x > 65%, y < 25%)
        stats = _extract_stats_from_blocks(blocks, page_width, page_height)
        
        # Weapons: Middle region (x < 60%, 15% < y < 60%)
        weapons = _extract_weapons_from_blocks(blocks, page_width, page_height,
                                                page_height * 0.15, page_height * 0.60)
        
        # Rules: After stats box (y > 15%)
        # Rules/actions appear at 35-40% on front cards with weapons
        # Rules/actions appear at 15-20% on back cards without weapons (just stats at top)
        rules = _extract_rules_from_blocks(blocks, page_width, page_height,
                                           page_height * 0.15)
        
        # Keywords: Bottom black bar (y > 75%)
        keywords = _extract_keywords_from_blocks(blocks, page_width, page_height)
        
        doc.close()
        
        # Build operative profile
        operative = {
            "name": name,
            "source_file": pdf_path.name,
            **stats
        }
        
        if weapons:
            operative["weapons"] = weapons
        
        if rules:
            operative["rules"] = rules
        
        if keywords:
            operative["keywords"] = keywords
        
        return operative
        
    except Exception as e:
        logger.error("Error extracting from %s: %s", pdf_path.name, e)
        return _empty_operative(pdf_path.name, str(e))


def _empty_operative(source_file: str, error: str = "") -> Dict[str, Any]:
    """Return empty operative profile with error."""
    profile = {
        "name": None,
        "source_file": source_file,
        "apl": None,
        "movement": None,
        "save": None,
        "wounds": None
    }
    if error:
        profile["error"] = error
    return profile


def _extract_name_from_blocks(blocks: List[Dict], page_width: float, page_height: float) -> Optional[str]:
    """Extract operative name from blocks in top-left corner.
    
    Name is typically in a block at:
    - x < 60% of page width (left side)
    - y < 15 pixels from top (very top)
    - ALL CAPS text
    - Not a keyword line (no commas)
    - May have APL value attached as trailing digit
    """
    for block in blocks:
        if block.get("type") != 0:  # Skip non-text blocks
            continue
        
        bbox = block["bbox"]
        # Check if block is in top-left corner
        if bbox[0] < page_width * 0.6 and bbox[1] < 15:
            # Extract text from block
            text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")
            
            text= text.strip()
            
           # Skip if contains commas (keyword line) or is a header or notes
            if ',' in text or text.upper() in ['NAME', 'ATK', 'HIT', 'DMG', 'WR', 'NOTES:', 'NOTES']:
                continue
            
            # Skip if it's an "ACTIONS" card (ability reference cards, not operatives)
            if 'ACTIONS' in text.upper():
                continue
            
            # Check if all caps and reasonable length
            if text.isupper() and 3 <= len(text) <= 50:
                # Remove trailing digits  (these are APL values)
                name = text.rstrip('0123456789').strip()
                if len(name) >= 3:
                    return name
    
    return None


def _extract_stats_from_blocks(blocks: List[Dict], page_width: float, page_height: float) -> Dict[str, Any]:
    """Extract stats from blocks in top-right and top-left regions.
    
    Stats are split across blocks:
    - Top-left (name block): May have APL value attached to name
    - Top-right stats box: Labels and values (MOVE, SAVE, WOUNDS)
    """
    stats = {
        "apl": None,
        "movement": None,
        "save": None,
        "wounds": None
    }
    
    # Extract APL from name block (top-left, y < 15)
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block["bbox"]
        if bbox[0] < page_width * 0.6 and bbox[1] < 15:
            text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")
            text = text.strip()
            
            # Look for trailing digit (APL value attached to name)
            if text and text[-1].isdigit():
                stats["apl"] = int(text[-1])
                break
    
    # If APL not found in name, check stats box region (some cards like RATLING BOMBER)
    if stats["apl"] is None:
        for block in blocks:
            if block.get("type") != 0:
                continue
            bbox = block["bbox"]
            # Stats box region: x > 65%, y < 25%
            if bbox[0] > page_width * 0.65 and bbox[1] < page_height * 0.25:
                text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text += span.get("text", "")
                text = text.strip()
                
                # Look for single digit (APL is 2 or 3)
                if text.isdigit() and len(text) == 1:
                    stats["apl"] = int(text)
                    break
    
    # Collect text from stats box region (top-right)
    stats_text = ""
    for block in blocks:
        if block.get("type") != 0:
            continue
        
        bbox = block["bbox"]
        if bbox[0] > page_width * 0.65 and bbox[3] < page_height * 0.25:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    stats_text += text + "|"  # Use | as separator
    
    # Parse stats from collected text
    # Movement: digit + " or ″
    move_match = re.search(r'(\d+)[″"\']', stats_text)
    if move_match:
        movement_value = move_match.group(1)
        stats["movement"] = movement_value + "″"
    
    # Save: digit followed by + (may have | separator)
    save_match = re.search(r'(\d+)\|?\+', stats_text)
    if save_match:
        save_value = save_match.group(1)
        stats["save"] = save_value + "+"
    
    # Wounds: Find all numbers, exclude APL/movement/save values
    all_numbers = re.findall(r'\d+', stats_text)
    for num_str in all_numbers:
        num = int(num_str)
        # Skip if it's APL, movement, or save
        if (stats.get("apl") and num == stats["apl"]):
            continue
        if stats.get("movement") and num_str == stats["movement"].rstrip("″\"'"):
            continue
        if stats.get("save") and num_str == stats["save"].rstrip("+"):
            continue
        # This must be wounds
        stats["wounds"] = num
        break
    
    return stats


def _extract_weapons_from_blocks(blocks: List[Dict], page_width: float, page_height: float,
                                  region_y1: float, region_y2: float) -> Optional[List[Dict[str, Any]]]:
    """Extract weapons from blocks in the weapons table region.
    
    Weapon table structure:
    - Header block: "NAME ATK HIT DMG WR" (optional, may be missing)
    - Individual blocks for each weapon with structured data
    - Blocks are typically short and within specific Y coordinates
    """
    weapons = []
    
    # Filter blocks in weapons region
    weapon_blocks = []
    for block in blocks:
        if block.get("type") != 0:  # Skip non-text blocks
            continue
        
        bbox = block["bbox"]
        # Check if block START is in weapons region (left side, middle height)
        # Only check top of block (bbox[1]), not bottom, to be more inclusive
        if (bbox[0] < page_width * 0.6 and 
            bbox[1] >= region_y1 and 
            bbox[1] <= region_y2):
            
            # Extract text from block
            block_text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    block_text += span.get("text", "")
                block_text += "\n"
            
            block_text = block_text.strip()
            if block_text:  # Only add non-empty blocks
                weapon_blocks.append(block_text)
    
    if not weapon_blocks:
        return None
    
    # Process all blocks and try to parse each as a weapon
    for i, block_text in enumerate(weapon_blocks):
        # Skip header blocks
        if "NAME" in block_text and "ATK" in block_text and len(block_text) < 50:
            continue
        
        # Skip obvious ability blocks (have colons, long text, specific keywords)
        if any(keyword in block_text for keyword in ['ACTIONS', 'PLOYS', 'RULES', 'EQUIPMENT']):
            continue
        
        # Skip very long blocks (> 500 chars) - definitely not a single weapon
        if len(block_text) > 500:
            continue
        
        # Try to parse as weapon
        weapon = _parse_weapon_block(block_text)
        if weapon:
            weapons.append(weapon)
    
    return weapons if weapons else None


def _parse_weapon_block(block_text: str) -> Optional[Dict[str, Any]]:
    """Parse a single weapon profile block.
    
    Supports two formats:
    1. Multi-line (most common):
       Explosive arsenal
       5
       3+
       4/5
       Range 3", Blast 1"
    
    2. Single-line (rare):
       "Explosive arsenal  5  3+  4/5  Range 3""
    """
    # Clean up text
    text = block_text.strip()
    
    # Skip headers and labels
    if any(header in text for header in ['NAME', 'ATK', 'HIT', 'DMG', 'WR', 'APL', 'WOUNDS', 'SAVE', 'MOVE']):
        return None
    
    # Skip very long text blocks (likely abilities, not weapons)
    if len(text) > 400:
        return None
    
    # Try parsing as multi-line format first
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    if len(lines) >= 4:
        # Multi-line format
        weapon = {"name": lines[0]}
        
        # Find attacks, hit, and damage from remaining lines
        attacks = None
        hit = None
        damage = None
        special_rules = []
        
        for line in lines[1:]:
            # Attacks: single digit or small number (1-20)
            if line.isdigit() and 1 <= int(line) <= 20 and attacks is None:
                attacks = line
            # Hit: X+ format (e.g., "2+", "3+", "4+")
            elif re.match(r'^\d\+$', line.strip()) and hit is None:
                hit = line.strip()
            # Damage: X/Y format or single digit (e.g., "3/4", "4/5", "5")
            elif re.match(r'^\d+(/\d+)?$', line.strip()) and damage is None:
                damage = line.strip()
            # Everything else is special rules
            else:
                special_rules.append(line)
        
        # Validate minimum required fields
        if attacks and hit and damage:
            weapon["attacks"] = attacks
            weapon["hit"] = hit
            weapon["damage"] = damage
            
            # Add special rules if present
            special_text = ' '.join(special_rules).strip()
            if special_text and special_text != '-':
                weapon["special_rules"] = special_text
            
            return weapon
    
    # Try parsing as single-line format (fallback)
    # Split by multiple spaces to separate fields
    parts = re.split(r'\s{2,}', text)
    
    if len(parts) >= 4:
        weapon = {"name": parts[0].strip()}
        attacks = None
        hit = None
        damage = None
        
        for i, part in enumerate(parts[1:], 1):
            part = part.strip()
            
            # Attacks: single digit
            if part.isdigit() and 1 <= int(part) <= 20 and attacks is None:
                attacks = part
            # Hit: X+ format
            elif re.match(r'^\d\+$', part) and hit is None:
                hit = part
            # Damage: X/Y or X
            elif re.match(r'^\d+(/\d+)?$', part) and damage is None:
                damage = part
            # Everything else is special rules
            else:
                special_rules = ' '.join(parts[i:]).strip()
                if special_rules and special_rules != '-':
                    weapon["special_rules"] = special_rules
                break
        
        # Validate minimum required fields
        if attacks and hit and damage:
            weapon["attacks"] = attacks
            weapon["hit"] = hit
            weapon["damage"] = damage
            return weapon
    
    return None



def _extract_rules_from_blocks(blocks: List[Dict], page_width: float, page_height: float,
                                region_y1: float) -> Optional[List[Dict[str, str]]]:
    """Extract rules and unique actions from ability blocks.
    
    Rules and unique actions have two formats:
    1. Colon format: "Ability Name: Description text..."
    2. Warhammer format (no colon):
       - Bold line: "ACTION NAME"  
       - Bold line: "XAP" (cost)
       - Regular lines: Description text
    """
    rules = []
    
    # Collect all text blocks in abilities region (below weapons, y > 50%)
    ability_text = []
    for block in blocks:
        if block.get("type") != 0:  # Skip non-text blocks
            continue
        
        bbox = block["bbox"]
        # Check if block is in abilities region (below weapons)
        if bbox[1] >= region_y1:
            # Extract text from block, preserving bold formatting info
            for line in block.get("lines", []):
                line_text = ""
                is_bold = False
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    # Check if bold (font usually contains "Bold")
                    font = span.get("font", "")
                    if "Bold" in font or span.get("flags", 0) & 16:  # 16 = bold flag
                        is_bold = True
                    line_text += text
                
                line_text = line_text.strip()
                if line_text:
                    ability_text.append((line_text, is_bold))
    
    if not ability_text:
        return None
    
    # Parse unique actions
    i = 0
    while i < len(ability_text):
        text, is_bold = ability_text[i]
        
        # Look for bold text
        if is_bold:
            # Pattern 1: Bold text with colon (e.g., "Ability Name: Description")
            if ':' in text:
                # Split at colon
                parts = text.split(':', 1)
                ua_name = parts[0].strip()
                ua_desc = parts[1].strip() if len(parts) > 1 else ""
                
                # Continue reading description from subsequent lines
                j = i + 1
                while j < len(ability_text):
                    next_text, next_bold = ability_text[j]
                    
                    # Stop if we hit another bold line (next UA)
                    if next_bold and (':' in next_text or next_text.endswith('AP')):
                        break
                    
                    # Stop at keyword footer (all-caps comma-separated text)
                    if ',' in next_text and next_text.isupper() and len(next_text) > 10:
                        keyword_parts = [p.strip() for p in next_text.split(',')]
                        if len(keyword_parts) >= 2 and all(len(p) > 1 for p in keyword_parts):
                            break
                    
                    # Add to description
                    ua_desc += " " + next_text
                    j += 1
                
                # Clean up name
                ua_name = ua_name.lstrip('•■◆▪-– ')
                
                # Skip common headers that aren't UAs
                if ua_name and ua_name.upper() not in ['NAME', 'ATK', 'HIT', 'DMG', 'WR', 
                                                         'APL', 'WOUNDS', 'SAVE', 'MOVE',
                                                         'UNIQUE ACTIONS', 'ABILITIES', 'NOTES']:
                    rules.append({
                        "name": ua_name,
                        "description": ua_desc.strip()
                    })
                
                i = j
                continue
            
            # Pattern 2: Bold ACTION NAME, then check for XAP cost
            # e.g., "GET IT DUN!" (bold), "1AP" (bold), "SUPPORT. Select..." (bold or regular)
            elif i + 1 < len(ability_text):
                next_text, next_bold = ability_text[i + 1]
                
                # Check if next line is a cost (XAP format)
                is_cost = next_bold and next_text.endswith('AP') and len(next_text) <= 5
                
                if is_cost:
                    ua_name = text.lstrip('•■◆▪-– ')
                    cost = next_text
                    ua_desc = ""
                    
                    # Read description from subsequent lines
                    j = i + 2
                    while j < len(ability_text):
                        desc_text, desc_bold = ability_text[j]
                        
                        # Stop at keyword footer (all-caps comma-separated text)
                        # Keywords are always: ALL CAPS, multiple commas, reasonable length
                        if ',' in desc_text and desc_text.isupper() and len(desc_text) > 10:
                            # Check if it looks like keywords (2+ comma-separated words)
                            keyword_parts = [p.strip() for p in desc_text.split(',')]
                            if len(keyword_parts) >= 2 and all(len(p) > 1 for p in keyword_parts):
                                break
                        
                        # Stop at point values (typically just a number like "32")
                        if desc_text.isdigit() and len(desc_text) <= 3:
                            break
                        
                        # Stop at next action name (bold line followed by XAP cost)
                        if desc_bold and j + 1 < len(ability_text):
                            peek_text, peek_bold = ability_text[j + 1]
                            if peek_bold and peek_text.endswith('AP') and len(peek_text) <= 5:
                                break
                        
                        ua_desc += " " + desc_text
                        j += 1
                    
                    # Skip common headers
                    if ua_name and ua_name.upper() not in ['NAME', 'ATK', 'HIT', 'DMG', 'WR', 
                                                             'APL', 'WOUNDS', 'SAVE', 'MOVE',
                                                             'UNIQUE ACTIONS', 'ABILITIES', 'NOTES']:
                        # Combine name with cost
                        full_name = f"{ua_name} ({cost})" if cost != "0AP" else ua_name
                        rules.append({
                            "name": full_name,
                            "description": ua_desc.strip()
                        })
                    
                    i = j
                    continue
        
        i += 1
    
    return rules if rules else None


def _extract_keywords_from_blocks(blocks: List[Dict], page_width: float, page_height: float) -> Optional[List[str]]:
    """Extract keywords from the black bar at bottom of datacard.
    
    Keywords appear in a comma-separated list near the bottom of the card.
    Format: "TEAM NAME, FACTION, KEYWORD1, KEYWORD2"
    - All uppercase
    - Comma-separated
    - First keyword is the team name (appears in orange on card)
    - Located in bottom ~20% of page
    """
    for block in blocks:
        if block.get("type") != 0:  # Skip non-text blocks
            continue
        
        bbox = block["bbox"]
        
        # Look for text in bottom region (y > 75% of page height)
        if bbox[1] > page_height * 0.75:
            # Extract text from block
            text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")
            
            text = text.strip()
            
            # Keywords are:
            # - All caps
            # - Contain commas (distinguishes from operative name)
            # - Reasonable length
            if text.isupper() and ',' in text and 10 <= len(text) <= 200:
                # Split by comma and clean
                keywords = [kw.strip() for kw in text.split(',')]
                # Filter out empty strings and common non-keywords
                keywords = [kw for kw in keywords if kw and kw not in ['AND', 'OR']]
                
                if keywords:
                    return keywords
    
    return None


def extract_statlines_from_team(team_dir: Path, output_dir: Path, force: bool = False) -> Optional[Dict]:
    """Extract statlines from all datacards for a team."""
    team_name = team_dir.name
    cards_dir = team_dir / "cards"
    
    if not cards_dir.exists():
        logger.warning("No cards directory for %s", team_name)
        return None
    
    # Find all landscape PDFs (datacards are landscape)
    pdf_files = sorted(cards_dir.glob("*_landscape.pdf"))
    
    if not pdf_files:
        logger.warning("No landscape PDFs found for %s", team_name)
        return None
    
    # Check if regeneration needed
    output_path = output_dir / team_name / "statlines" / "roster.json"
    if output_path.exists() and not force:
        # Check if source files changed
        existing_data = json.loads(output_path.read_text(encoding='utf-8'))
        existing_hash = existing_data.get("_content_hash")
        
        # Compute hash of all source PDFs
        hasher = hashlib.sha256()
        for pdf_file in sorted(pdf_files):
            hasher.update(pdf_file.read_bytes())
        current_hash = hasher.hexdigest()
        
        if existing_hash == current_hash:
            logger.info("  %s: No changes detected, skipping", team_name)
            return None
    
    # Extract operatives, handling front/back pairs
    operatives = []
    skip_next = 0
    
    for idx, pdf_file in enumerate(pdf_files):
        # Skip if this was processed as a back side
        if skip_next > 0:
            skip_next -= 1
            continue
        
        # Extract from front card
        operative = extract_statlines_from_pdf(pdf_file)
        
        # Only process if valid operative
        if not (operative.get("name") and operative.get("wounds") is not None):
            continue
        
        # Check if card continues on back side
        doc = fitz.open(pdf_file)
        if len(doc) > 0:
            page = doc[0]
            text = page.get_text().lower()
            
            # Check for continue patterns
            has_continue = any(pattern in text for pattern in [
                "continue on other side",
                "continued on other side", 
                "continues on other side",
                "rules continue on other side"
            ])
            
            # If continues and there's a next PDF, process it as back side
            if has_continue and idx + 1 < len(pdf_files):
                back_pdf = pdf_files[idx + 1]
                back_data = extract_statlines_from_pdf(back_pdf)
                
                # Merge rules from back side (weapons are front-only)
                if back_data and back_data.get("rules"):
                    if not operative.get("rules"):
                        operative["rules"] = []
                    operative["rules"].extend(back_data["rules"])
                
                # Skip next PDF since we just processed it
                skip_next = 1
        
        doc.close()
        operatives.append(operative)
    
    if not operatives:
        logger.warning("  %s: No operatives extracted", team_name)
        return None
    
    # Compute content hash
    hasher = hashlib.sha256()
    for pdf_file in sorted(pdf_files):
        hasher.update(pdf_file.read_bytes())
    content_hash = hasher.hexdigest()
    
    # Build roster
    roster = {
        "team": team_name,
        "generated": datetime.now(timezone.utc).isoformat(),
        "operative_count": len(operatives),
        "operatives": operatives,
        "_content_hash": content_hash
    }
    
    # Save roster
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(roster, indent=2, ensure_ascii=False), encoding='utf-8')
    
    logger.info("  ✓ %s: %d operatives extracted", team_name, len(operatives))
    
    return {
        "team": team_name,
        "operative_count": len(operatives),
        "output_file": str(output_path)
    }


def run(extracted_dir: Path, output_dir: Path, teams: Optional[List[str]] = None, 
        force: bool = False) -> Dict[str, Any]:
    """Run statline extraction for teams."""
    
    # Find teams to process
    if teams:
        team_dirs = [extracted_dir / team for team in teams if (extracted_dir / team).exists()]
    else:
        team_dirs = sorted([d for d in extracted_dir.iterdir() if d.is_dir()])
    
    if not team_dirs:
        logger.warning("No teams found to process")
        return {"processed": 0, "teams": []}
    
    logger.info("=" * 60)
    logger.info("Step 6: Extract Statlines from Datacards")
    logger.info("=" * 60)
    logger.info("Teams to process: %d", len(team_dirs))
    logger.info("Force regeneration: %s", force)
    logger.info("")
    
    processed_teams = []
    total_operatives = 0
    
    for team_dir in team_dirs:
        result = extract_statlines_from_team(team_dir, output_dir, force)
        if result:
            processed_teams.append(result)
            total_operatives += result["operative_count"]
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("Extraction Complete")
    logger.info("=" * 60)
    logger.info("Teams processed: %d", len(processed_teams))
    logger.info("Total operatives: %d", total_operatives)
    
    return {
        "processed": len(processed_teams),
        "total_operatives": total_operatives,
        "teams": processed_teams
    }


def main():
    parser = argparse.ArgumentParser(description='Extract statlines from datacards')
    parser.add_argument('--teams', nargs='+', help='Specific teams to process (default: all)')
    parser.add_argument('--force', action='store_true', help='Force regeneration even if unchanged')
    parser.add_argument('--extracted', type=Path, help='Extracted cards directory')
    parser.add_argument('--output', type=Path, help='Output directory')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Setup paths
    workspace_root = Path(__file__).parent.parent.parent.parent
    extracted_dir = args.extracted or workspace_root / 'layers' / 'warcom' / 'extracted'
    output_dir = args.output or workspace_root / 'output'
    
    # Run extraction
    result = run(extracted_dir, output_dir, args.teams, args.force)
    
    if result["processed"] == 0:
        logger.warning("No teams were processed")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
