"""
Step 6: Extract Statlines from Datacards

Extracts operative characteristics (APL, Movement, Save, Wounds) and weapon profiles
from datacard PDFs using coordinate-based region extraction.

Uses card_index.json (from step 3) to determine which cards to process and how.
All logic about card relationships (front/back, multi-card operatives) is in the index.

Input:  metadata/{team}/card_index.json (card index from step 3)
        layers/warcom/extracted/{team}/cards/*.pdf (source PDFs)
Output: output/{team}/statlines/roster.json

Architecture:
- Reads card_index.json to get operative cards and layouts
- Uses coordinate-based region extraction (not text order)
- Handles standard cards, back cards, and special 2-column action layouts
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
        
        # Weapons: Middle region (x < 60%, 15% < y < 80%)
        # Extended to 80% to capture operatives with many weapons (e.g., Traitor Chieftain with 10 weapons)
        weapons = _extract_weapons_from_blocks(blocks, page_width, page_height,
                                                page_height * 0.15, page_height * 0.80)
        
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
        
        # Rules are split into passive_abilities and unique_actions in step 7
        # Store temporarily for processing
        if rules:
            operative["_rules_temp"] = rules
        
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
                    # Check if bold - look for various indicators:
                    # - "Bold" in font name
                    # - "Bd" in font name (short for Bold)
                    # - "Heavy" in font name  
                    # - Bold flag (16)
                    font = span.get("font", "")
                    if any(indicator in font for indicator in ["Bold", "-Bd", "Heavy"]) or span.get("flags", 0) & 16:
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
                    
                    # Stop if we hit another bold line (next ability/action)
                    if next_bold:
                        # Check for colon format ability
                        if ':' in next_text:
                            break
                        # Check for AP cost (this line or next line)
                        if next_text.endswith('AP') and len(next_text) <= 5:
                            break
                        # Check if this bold line is followed by XAP cost (Pattern 2 action)
                        if j + 1 < len(ability_text):
                            peek_text, peek_bold = ability_text[j + 1]
                            if peek_bold and peek_text.endswith('AP') and len(peek_text) <= 5:
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


def _extract_actions_from_2column_page(page: fitz.Page) -> List[Dict[str, str]]:
    """Extract actions from a 2-column layout page.
    
    No detection needed - just extract all actions found on the page.
    Index already identified this as an action card.
    
    Each action has format:
    - ALL-CAPS TITLE
    - XAP (on next line)
    - Description text
    """
    page_rect = page.rect
    page_width = page_rect.width
    page_height = page_rect.height
    
    logger.debug("  Extracting actions from 2-column page (%.0fx%.0f)", page_width, page_height)
    
    # 2-column layout: split at 40% of page width
    split_x = page_width * 0.40
    
    # Get all text blocks, skipping headers
    blocks_dict = page.get_text("dict")
    blocks = blocks_dict.get("blocks", [])
    
    # Separate blocks by column, skipping page header
    left_blocks = []
    right_blocks = []
    
    for block in blocks:
        if block.get("type") != 0:  # Skip non-text blocks
            continue
        
        bbox = block.get("bbox", [0, 0, 0, 0])
        
        # Skip page header at top (Y < 30)
        if bbox[1] < 30:
            continue
        
        block_x = bbox[0]
        if block_x < split_x:
            left_blocks.append(block)
        else:
            right_blocks.append(block)
    
    logger.debug("  Split into columns: left=%d blocks, right=%d blocks", len(left_blocks), len(right_blocks))
    
    # Try extracting from each column
    actions = []
    
    # Left column
    left_action = _parse_action_from_blocks(left_blocks, page_width, page_height)
    if left_action:
        actions.append(left_action)
    
    # Right column
    right_action = _parse_action_from_blocks(right_blocks, page_width, page_height)
    if right_action:
        actions.append(right_action)
    
    # If we didn't get actions from split columns, try merging all blocks
    # (handles single action spanning both columns)
    if not actions:
        logger.debug("  No actions from split columns, trying merged blocks")
        all_blocks = left_blocks + right_blocks
        merged_action = _parse_action_from_blocks(all_blocks, page_width, page_height)
        if merged_action:
            actions.append(merged_action)
    
    logger.debug("  Extracted %d actions from page", len(actions))
    return actions


def _parse_action_from_blocks(blocks: List[Dict], page_width: float, page_height: float) -> Optional[Dict[str, str]]:
    """Parse an action from a list of blocks (one column).
    
    Actions have format:
    - All-caps title (may be bold or non-bold)
    - "XAP" on the next line
    - Description text after that
    """
    if not blocks:
        return None
    
    logger.debug("    Parsing %d blocks for action", len(blocks))
    
    # Sort blocks by y position (top to bottom)
    sorted_blocks = sorted(blocks, key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])
    
    # Collect all text with line breaks preserved
    lines = []
    for block in sorted_blocks:
        for line in block.get("lines", []):
            line_text = ""
            for span in line.get("spans", []):
                line_text += span.get("text", "")
            if line_text.strip():
                lines.append(line_text.strip())
    
    if len(lines) < 3:  # Need at least: title, AP, and some description
        logger.debug("      Not enough lines (%d): %s", len(lines), lines[:5] if lines else [])
        return None
    
    logger.debug("      Checking %d lines for action title", len(lines))
    
    # Find title: look for all-caps line followed by "XAP" pattern
    action_name = None
    description_start = None
    
    for i in range(len(lines) - 1):
        line = lines[i].strip()
        next_line = lines[i + 1].strip()
        
        # Check if this is an all-caps title (1+ words, all uppercase, reasonable length)
        words = line.split()
        if len(words) >= 1 and line.isupper() and 3 <= len(line) <= 50:
            # Check if next line has AP cost
            if re.match(r'^\d+AP$', next_line, re.IGNORECASE):
                action_name = f"{line} ({next_line})"
                description_start = i + 2
                logger.debug("      Found action: '%s' at line %d", action_name, i)
                break
        elif len(words) >= 1 and line.isupper() and 3 <= len(line) <= 50:
            logger.debug("      Line %d is all-caps but next line is not XAP: '%s' -> '%s'", i, line[:40], next_line[:20] if next_line else "")
    
    if not action_name or description_start is None or description_start >= len(lines):
        logger.debug("      No valid action found (checked %d lines)", len(lines))
        return None
    
    # Collect remaining lines as description
    description = " ".join(lines[description_start:])
    description = re.sub(r'\s+', ' ', description).strip()
    
    if not description:
        logger.debug("      No description found")
        return None
    
    logger.debug("      Action extracted: '%s' (%d chars description)", action_name, len(description))
    
    return {
        "name": action_name,
        "description": description
    }


def extract_statlines_from_team(team_name: str, output_dir: Path, force: bool = False, 
                                 base_dir: Path = None) -> Optional[Dict]:
    """
    Extract statlines from all datacards for a team using the card index.
    
    Reads metadata/{team}/card_index.json to determine which cards to process and how.
    All logic about card relationships is in the index.
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    # Read card index from metadata directory
    index_path = base_dir / 'metadata' / team_name / 'card_index.json'
    if not index_path.exists():
        logger.error("  %s: card_index.json not found. Run step 3 first.", team_name)
        return None
    
    with open(index_path, 'r', encoding='utf-8') as f:
        index = json.load(f)
    
    if not index.get('operatives'):
        logger.warning("  %s: No operatives in index", team_name)
        return None
    
    # Check if regeneration needed
    output_path = output_dir / team_name / "statlines" / "roster.json"
    if output_path.exists() and not force:
        # Check if source files changed (use hashes from index)
        existing_data = json.loads(output_path.read_text(encoding='utf-8'))
        existing_hash = existing_data.get("_content_hash")
        
        # Compute hash from all card hashes in index
        hasher = hashlib.sha256()
        for operative_data in index['operatives']:
            for card in operative_data['cards']:
                hasher.update(card['content_hash'].encode('utf-8'))
        current_hash = hasher.hexdigest()
        
        if existing_hash == current_hash:
            logger.info("  %s: No changes detected, skipping", team_name)
            return None
    
    # Extract operatives from index
    operatives = []
    
    for operative_data in index['operatives']:
        operative_name = operative_data['name']
        cards = operative_data['cards']
        
        if not cards:
            logger.warning("    %s: No cards in index", operative_name)
            continue
        
        # Find front card
        front_card = next((c for c in cards if c['type'] == 'front'), None)
        if not front_card:
            logger.warning("    %s: No front card in index", operative_name)
            continue
        
        # Build absolute path to front card PDF
        front_pdf_path = base_dir / front_card['source_pdf']
        if not front_pdf_path.exists():
            logger.warning("    %s: Front card PDF not found: %s", operative_name, front_pdf_path)
            continue
        
        # Extract from front card
        operative = extract_statlines_from_pdf(front_pdf_path)
        
        # Only process if valid operative
        if not (operative.get("name") and operative.get("wounds") is not None):
            logger.warning("    %s: Failed to extract stats from front card", operative_name)
            continue
        
        # Process back card if it exists
        back_card = next((c for c in cards if c['type'] == 'back'), None)
        if back_card:
            back_pdf_path = base_dir / back_card['source_pdf']
            if back_pdf_path.exists():
                back_data = extract_statlines_from_pdf(back_pdf_path)
                if back_data and back_data.get("_rules_temp"):
                    if not operative.get("_rules_temp"):
                        operative["_rules_temp"] = []
                    operative["_rules_temp"].extend(back_data["_rules_temp"])
        
        # Process special action cards (2-column layout)
        action_cards = [c for c in cards if c['type'].startswith('actions_')]
        if action_cards:
            logger.info("    %s: Processing %d action cards", operative_name, len(action_cards))
            for action_card in action_cards:
                action_pdf_path = base_dir / action_card['source_pdf']
                if not action_pdf_path.exists():
                    logger.warning("      Action card not found: %s", action_pdf_path)
                    continue
                
                # Extract actions from 2-column layout
                try:
                    doc = fitz.open(action_pdf_path)
                    if len(doc) > 0:
                        page = doc[0]
                        actions = _extract_actions_from_2column_page(page)
                        if actions:
                            logger.info("      Extracted %d actions from %s", len(actions), action_card['type'])
                            if not operative.get("_rules_temp"):
                                operative["_rules_temp"] = []
                            operative["_rules_temp"].extend(actions)
                    doc.close()
                except Exception as e:
                    logger.error("      Error extracting actions from %s: %s", action_pdf_path.name, e)
        
        operatives.append(operative)
    
    if not operatives:
        logger.warning("  %s: No operatives extracted", team_name)
        return None
    
    # Compute content hash from index card hashes
    hasher = hashlib.sha256()
    for operative_data in index['operatives']:
        for card in operative_data['cards']:
            hasher.update(card['content_hash'].encode('utf-8'))
    content_hash = hasher.hexdigest()
    
    # Check if we need to update
    needs_update = force
    existing_timestamp = None
    
    if output_path.exists() and not force:
        try:
            old_roster = json.loads(output_path.read_text(encoding='utf-8'))
            old_hash = old_roster.get('_content_hash', '')
            
            if old_hash == content_hash:
                # No changes - keep existing file
                logger.info("  ⊘ %s: No changes (hash match), keeping existing roster", team_name)
                return {
                    "team": team_name,
                    "operative_count": len(operatives),
                    "output_file": str(output_path),
                    "status": "unchanged"
                }
            else:
                needs_update = True
                # Preserve existing timestamp if we're updating
                existing_timestamp = old_roster.get('last_modified')
        except (json.JSONDecodeError, KeyError, IOError) as e:
            logger.warning("  ⚠ Failed to read existing roster, will regenerate: %s", e)
            needs_update = True
    else:
        needs_update = True
    
    # Build roster
    roster = {
        "team": team_name,
        "last_modified": datetime.now(timezone.utc).isoformat(),
        "operative_count": len(operatives),
        "operatives": operatives,
        "_content_hash": content_hash
    }
    
    # Save roster only if needed
    if needs_update:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(roster, indent=2, ensure_ascii=False), encoding='utf-8')
        
        logger.info("  ✓ %s: %d operatives extracted (updated)", team_name, len(operatives))
        status = "updated"
    else:
        status = "unchanged"
    
    return {
        "team": team_name,
        "operative_count": len(operatives),
        "output_file": str(output_path),
        "status": status
    }


def run(output_dir: Path, teams: Optional[List[str]] = None, 
        force: bool = False, base_dir: Path = None) -> Dict[str, Any]:
    """
    Run statline extraction for teams using card index.
    
    Args:
        output_dir: Output directory for statlines
        teams: Optional list of team names to process (default: all teams with index)
        force: Force regeneration even if files unchanged
        base_dir: Base directory for resolving paths (default: current directory)
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    # Find teams to process (those with card_index.json in metadata/)
    if teams:
        team_names = teams
    else:
        # Find all teams with card_index.json in metadata
        metadata_dir = base_dir / 'metadata'
        if not metadata_dir.exists():
            logger.warning("No metadata directory found. Run step 3 first.")
            return {"processed": 0, "teams": []}
        
        team_names = []
        for team_dir in sorted(metadata_dir.iterdir()):
            if team_dir.is_dir() and (team_dir / 'card_index.json').exists():
                team_names.append(team_dir.name)
    
    if not team_names:
        logger.warning("No teams found with card_index.json. Run step 3 first.")
        return {"processed": 0, "teams": []}
    
    logger.info("=" * 60)
    logger.info("Step 6: Extract Statlines from Datacards")
    logger.info("=" * 60)
    logger.info("Teams to process: %d", len(team_names))
    logger.info("Force regeneration: %s", force)
    logger.info("")
    
    processed_teams = []
    total_operatives = 0
    
    for team_name in team_names:
        result = extract_statlines_from_team(team_name, output_dir, force, base_dir)
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
    parser = argparse.ArgumentParser(description='Extract statlines from datacards using card index')
    parser.add_argument('--teams', nargs='+', help='Specific teams to process (default: all)')
    parser.add_argument('--force', action='store_true', help='Force regeneration even if unchanged')
    parser.add_argument('--output', type=Path, help='Output directory (default: ./output)')
    parser.add_argument('--base-dir', type=Path, help='Base directory for resolving paths (default: current directory)')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Setup paths
    workspace_root = Path(__file__).parent.parent.parent.parent
    output_dir = args.output or workspace_root / 'output'
    base_dir = getattr(args, 'base_dir', None) or workspace_root
    
    # Run extraction
    result = run(output_dir, args.teams, args.force, base_dir)
    
    if result["processed"] == 0:
        logger.warning("No teams were processed")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
