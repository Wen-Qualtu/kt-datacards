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
        
        # Weapons: Middle region (x < 60%, 15% < y < 50%)
        weapons = _extract_weapons_from_blocks(blocks, page_width, page_height,
                                                page_height * 0.15, page_height * 0.50)
        
        # Unique Actions: Lower region (y > 50%, abilities section)
        unique_actions = _extract_unique_actions_from_blocks(blocks, page_width, page_height,
                                                              page_height * 0.50)
        
        doc.close()
        
        # Build operative profile
        operative = {
            "name": name,
            "source_file": pdf_path.name,
            **stats
        }
        
        if weapons:
            operative["weapons"] = weapons
        
        if unique_actions:
            operative["unique_actions"] = unique_actions
        
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
    - Header block: "NAME ATK HIT DMG WR"
    - Individual blocks for each weapon with structured data
    - Blocks are short (< 100 chars) and within specific Y coordinates
    """
    weapons = []
    
    # Filter blocks in weapons region
    weapon_blocks = []
    for block in blocks:
        if block.get("type") != 0:  # Skip non-text blocks
            continue
        
        bbox = block["bbox"]
        # Check if block is in weapons region (left side, middle height)
        if (bbox[0] < page_width * 0.6 and 
            bbox[1] >= region_y1 and 
            bbox[3] <= region_y2):
            
            # Extract text from block
            block_text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    block_text += span.get("text", "")
                block_text += "\n"
            
            block_text = block_text.strip()
            weapon_blocks.append(block_text)
    
    if not weapon_blocks:
        return None
    
    # First block should be header - skip it
    header_found = False
    for i, block_text in enumerate(weapon_blocks):
        # Check if this is the header
        if "NAME" in block_text and "ATK" in block_text:
            header_found = True
            continue
        
        if not header_found:
            continue
        
        # Stop at ability text (longer paragraphs)
        if len(block_text) > 100:
            break
        
        # Parse weapon block
        weapon = _parse_weapon_block(block_text)
        if weapon:
            weapons.append(weapon)
    
    return weapons if weapons else None


def _parse_weapon_block(block_text: str) -> Optional[Dict[str, Any]]:
    """Parse a single weapon profile block.
    
    Expected format (one item per line):
    Slugga
    4
    4+
    3/4
    Range 8"
    
    Or simpler:
    Slugga
    4
    4+
    3/4
    -
    """
    lines = [line.strip() for line in block_text.split('\n') if line.strip()]
    
    if len(lines) < 4:
        return None
    
    weapon = {}
    
    # Line 0: Weapon name
    name = lines[0]
    # Skip if it's a table header or stat label
    if name in ['NAME', 'ATK', 'HIT', 'DMG', 'WR', 'APL', 'WOUNDS', 'SAVE', 'MOVE']:
        return None
    weapon["name"] = name
    
    # Line 1: Attacks (should be a number)
    if lines[1].isdigit():
        weapon["attacks"] = lines[1]
    else:
        return None  # Invalid weapon
    
    # Line 2: Hit (X+ format)
    if re.match(r'^\d\+$', lines[2]):
        weapon["hit"] = lines[2]
    
    # Line 3: Damage (X/Y or just X)
    if re.match(r'^\d+(/\d+)?$', lines[3]):
        weapon["damage"] = lines[3]
    
    # Line 4+: Special rules (if present and not just "-")
    if len(lines) > 4:
        special_rules = ' '.join(lines[4:]).strip()
        if special_rules and special_rules != '-':
            weapon["special_rules"] = special_rules
    
    # Only return complete weapon (must have name and attacks minimum)
    if "name" in weapon and "attacks" in weapon:
        return weapon
    
    return None


def _extract_unique_actions_from_blocks(blocks: List[Dict], page_width: float, page_height: float,
                                         region_y1: float) -> Optional[List[Dict[str, str]]]:
    """Extract Unique Actions from ability blocks.
    
    Unique Actions format:
    - Name in bold (sometimes with cost like "(1AP)")  
    - May have bullet point prefix
    - Followed by colon and description
    - Example: "• Manifest Psychic Power (1AP): Description text..."
    - Or: "Special Ability: Description..."
    """
    unique_actions = []
    
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
    # Pattern: Bold text (possibly with "(XAP)") followed by ":" and description
    i = 0
    while i < len(ability_text):
        text, is_bold = ability_text[i]
        
        # Look for bold text with optional action cost
        if is_bold:
            # Check if this line or next has a colon (UA format)
            has_colon = ':' in text
            
            if has_colon:
                # Split at colon
                parts = text.split(':', 1)
                ua_name = parts[0].strip()
                ua_desc = parts[1].strip() if len(parts) > 1 else ""
                
                # Continue reading description from subsequent lines
                j = i + 1
                while j < len(ability_text):
                    next_text, next_bold = ability_text[j]
                    
                    # Stop if we hit another bold line (next UA)
                    if next_bold and ':' in next_text:
                        break
                    
                    # Stop if we hit keyword footer (all caps with commas)
                    if ',' in next_text and next_text.isupper():
                        break
                    
                    # Add to description
                    ua_desc += " " + next_text
                    j += 1
                
                # Clean up name
                # Remove bullet points and special characters
                ua_name = ua_name.lstrip('•■◆▪-– ')
                
                # Skip common headers that aren't UAs
                if ua_name and ua_name.upper() not in ['NAME', 'ATK', 'HIT', 'DMG', 'WR', 
                                                         'UNIQUE ACTIONS', 'ABILITIES', 'NOTES']:
                    unique_actions.append({
                        "name": ua_name,
                        "description": ua_desc.strip()
                    })
                
                i = j
                continue
        
        i += 1
    
    return unique_actions if unique_actions else None


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
    
    # Extract operatives
    operatives = []
    for pdf_file in pdf_files:
        operative = extract_statlines_from_pdf(pdf_file)
        # Only include operatives with valid name and wounds
        # (operatives without wounds are ACTIONS-only back sides)
        if operative.get("name") and operative.get("wounds") is not None:
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
