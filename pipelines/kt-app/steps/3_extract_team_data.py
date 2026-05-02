"""
Step 3: Extract Team Data

Extracts comprehensive data from all card types to create a complete team data file.
This data is intended for external use and future features like in-game popups.

For datacards: Uses proven structured extraction (APL, movement, save, wounds, weapons, abilities, keywords)
For other cards: Extracts name and text content

Input:  layers/kt-app/classified/{team}/structure.json
Output: output_v3/{team}/data/team_data.json

Data Structure:
{
  "team": "battleclade",
  "generated_at": "2024-01-01T00:00:00Z",
  "datacards": [
    {
      "name": "BATTLECLADE TECHNOARCHEOLOGIST",
      "apl": 3,
      "movement": "6″",
      "save": "3+",
      "wounds": 9,
      "weapons": [{...}],
      "passive_abilities": [{...}],
      "unique_actions": [{...}],
      "keywords": [...]
    }
  ],
  "equipment": [{"name": "...", "text": "..."}],
  "faction_rules": [{"name": "...", "text": "..."}],
  ...
}

Usage:
    python pipelines/kt-app/steps/3_extract_team_data.py
    python pipelines/kt-app/steps/3_extract_team_data.py --teams kasrkin,blooded
    python pipelines/kt-app/steps/3_extract_team_data.py --force
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional
import re

import fitz  # PyMuPDF


# ===================================================================
# LOGGING SETUP
# ===================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Proven Datacard Extraction Functions (from script/extract_statlines.py)
# ══════════════════════════════════════════════════════════════════════════════

def _clean_extracted_text(text: str) -> str:
    """Clean up extracted text by fixing bullet characters, markdown formatting, and whitespace."""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = text.replace("\u0007", "\n• ")
    text = text.replace("\x95", "\n- ")
    text = re.sub(r"([^\n])\s*•\s+", r"\1\n• ", text)
    text = re.sub(r"•\s+•\s+", "• ", text)
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"\n\n+", "\n", text)
    return text.strip()


def _split_embedded_actions(rules: list[dict]) -> list[dict]:
    """Split abilities that contain embedded actions."""
    if not rules:
        return rules
    
    result = []
    for rule in rules:
        name = rule["name"]
        desc = rule["description"]
        match = re.search(r'([A-Z\s]{4,}?)[\x08\x07]?\s*(\d+[/\d]*AP)\s*(.+)$', desc, re.DOTALL)
        
        if match:
            action_name_raw = match.group(1).strip()
            cost = match.group(2).strip()
            action_desc = match.group(3).strip()
            
            if action_name_raw.isupper() and (len(action_name_raw) > 5 or ' ' in action_name_raw):
                ability_text = desc[:match.start()].strip()
                
                if ability_text and len(ability_text) > 10:
                    result.append({"name": name, "description": _clean_extracted_text(ability_text)})
                    action_name = f"{action_name_raw} ({cost})"
                    result.append({"name": action_name, "description": _clean_extracted_text(action_desc)})
                    continue
        
        result.append(rule)
    
    return result


def _extract_name_from_blocks(blocks: list, page_width: float, page_height: float) -> str | None:
    """Extract operative name from blocks in top-left corner (x < 60%, y < 15px)."""
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
            if ',' in text or text.upper() in ['NAME', 'ATK', 'HIT', 'DMG', 'WR', 'NOTES:', 'NOTES']:
                continue
            if 'ACTIONS' in text.upper():
                continue
            if text.isupper() and 3 <= len(text) <= 50:
                name = text.rstrip('0123456789').strip()
                if len(name) >= 3:
                    return name
    return None


def _extract_stats_from_blocks(blocks: list, page_width: float, page_height: float) -> dict:
    """Extract APL, movement, save, wounds from stat regions."""
    stats = {"apl": None, "movement": None, "save": None, "wounds": None}

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
            if text and text[-1].isdigit():
                stats["apl"] = int(text[-1])
                break

    if stats["apl"] is None:
        for block in blocks:
            if block.get("type") != 0:
                continue
            bbox = block["bbox"]
            if bbox[0] > page_width * 0.65 and bbox[1] < page_height * 0.25:
                text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text += span.get("text", "")
                text = text.strip()
                if text.isdigit() and len(text) == 1:
                    stats["apl"] = int(text)
                    break

    stats_text = ""
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block["bbox"]
        if bbox[0] > page_width * 0.65 and bbox[3] < page_height * 0.25:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    stats_text += span.get("text", "") + "|"

    move_match = re.search(r'(\d+)[″"\']', stats_text)
    if move_match:
        stats["movement"] = move_match.group(1) + "″"

    save_match = re.search(r'(\d+)\|?\+', stats_text)
    if save_match:
        stats["save"] = save_match.group(1) + "+"

    all_numbers = re.findall(r'\d+', stats_text)
    used_apl = False
    used_movement = False
    used_save = False
    for num_str in all_numbers:
        num = int(num_str)
        if stats.get("apl") and num == stats["apl"] and not used_apl:
            used_apl = True
            continue
        if stats.get("movement") and num_str == stats["movement"].rstrip("″\"'") and not used_movement:
            used_movement = True
            continue
        if stats.get("save") and num_str == stats["save"].rstrip("+") and not used_save:
            used_save = True
            continue
        stats["wounds"] = num
        break

    return stats


def _extract_weapons_from_blocks(blocks: list, page_width: float, page_height: float,
                                  y1: float, y2: float) -> list[dict] | None:
    """Extract weapons from the weapon table region (left side, middle height)."""
    weapon_blocks = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block["bbox"]
        if bbox[0] < page_width * 0.6 and bbox[1] >= y1 and bbox[1] <= y2:
            block_text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    block_text += span.get("text", "")
                block_text += "\n"
            block_text = block_text.strip()
            if block_text:
                weapon_blocks.append(block_text)

    if not weapon_blocks:
        return None

    weapons = []
    for block_text in weapon_blocks:
        if "NAME" in block_text and "ATK" in block_text and len(block_text) < 50:
            continue
        if any(kw in block_text for kw in ['ACTIONS', 'PLOYS', 'RULES', 'EQUIPMENT']):
            continue
        if len(block_text) > 500:
            continue
        weapon = _parse_weapon_block(block_text)
        if weapon:
            weapons.append(weapon)
    return weapons if weapons else None


def _parse_weapon_block(block_text: str) -> dict | None:
    """Parse a single weapon from a text block."""
    text = block_text.strip()
    if any(h in text for h in ['NAME', 'ATK', 'HIT', 'DMG', 'WR', 'APL', 'WOUNDS', 'SAVE', 'MOVE']):
        return None
    if len(text) > 400:
        return None

    lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
    lines = [ln for ln in lines if re.sub(r'[\x00-\x1f]+', '', ln).strip() or '\t' in ln]
    expanded = []
    for ln in lines:
        if '\t' in ln:
            parts = ln.rsplit('\t', 1)
            name_part = parts[0].strip()
            atk_part = parts[1].strip()
            if atk_part.isdigit() and 1 <= int(atk_part) <= 20 and name_part:
                expanded.append(name_part)
                expanded.append(atk_part)
                continue
        expanded.append(ln)
    lines = expanded
    if len(lines) >= 4:
        weapon = {"name": lines[0]}
        attacks = hit = damage = None
        special_rules = []
        for ln in lines[1:]:
            if ln.isdigit() and 1 <= int(ln) <= 20 and attacks is None:
                attacks = ln
            elif re.match(r'^\d\+$', ln) and hit is None:
                hit = ln
            elif re.match(r'^\d+(/\d+)?$', ln) and damage is None:
                damage = ln
            else:
                special_rules.append(ln)
        if attacks and hit and damage:
            weapon["attacks"] = attacks
            weapon["hit"] = hit
            weapon["damage"] = damage
            sr = ' '.join(special_rules).strip()
            
            clean_name = re.sub(r'[\x00-\x1f]+', '', weapon["name"]).strip()
            if not clean_name or len(clean_name) <= 1 or weapon["name"] in ['—', '-']:
                if sr:
                    sr = re.sub(r'[\x00-\x1f]+', '', sr).strip()
                    match = re.match(r'^(.+?)\s+(Range\s|Piercing\s|Saturate|Torrent|Ceaseless|Lethal|Balanced|Brutal|Rending|Hot|Massive|Stun|Indirect|Silent|MW\s|AP\s|Unwieldy|Heavy|Relentless)', sr)
                    if match:
                        clean_name = match.group(1).strip()
                        sr = sr[len(match.group(1)):].strip()
                    else:
                        if sr.endswith(' -') or sr == '-':
                            clean_name = sr.rstrip(' -').strip()
                            sr = None
                        else:
                            clean_name = sr
                            sr = None
            
            weapon["name"] = clean_name if clean_name else weapon["name"]
            if sr:
                sr = re.sub(r'[\x00-\x1f]+', '', sr).strip()
            if sr and sr not in ['-', '']:
                weapon["special_rules"] = sr
            return weapon

    parts = re.split(r'\s{2,}', text)
    if len(parts) >= 4:
        weapon = {"name": parts[0].strip()}
        attacks = hit = damage = None
        for i, part in enumerate(parts[1:], 1):
            part = part.strip()
            if part.isdigit() and 1 <= int(part) <= 20 and attacks is None:
                attacks = part
            elif re.match(r'^\d\+$', part) and hit is None:
                hit = part
            elif re.match(r'^\d+(/\d+)?$', part) and damage is None:
                damage = part
            else:
                sr = ' '.join(parts[i:]).strip()
                clean_name = re.sub(r'[\x00-\x1f]+', '', weapon["name"]).strip()
                
                if not clean_name or len(clean_name) <= 1 or weapon["name"] in ['—', '-']:
                    if sr:
                        sr = re.sub(r'[\x00-\x1f]+', '', sr).strip()
                        match = re.match(r'^(.+?)\s+(Range\s|Piercing\s|Saturate|Torrent|Ceaseless|Lethal|Balanced|Brutal|Rending|Hot|Massive|Stun|Indirect|Silent|MW\s|AP\s|Unwieldy|Heavy|Relentless)', sr)
                        if match:
                            clean_name = match.group(1).strip()
                            sr = sr[len(match.group(1)):].strip()
                        else:
                            if sr.endswith(' -') or sr == '-':
                                clean_name = sr.rstrip(' -').strip()
                                sr = None
                            else:
                                clean_name = sr
                                sr = None
                
                weapon["name"] = clean_name if clean_name else weapon["name"]
                if sr:
                    sr = re.sub(r'[\x00-\x1f]+', '', sr).strip()
                if sr and sr not in ['-', '']:
                    weapon["special_rules"] = sr
                break
        if attacks and hit and damage:
            weapon["attacks"] = attacks
            weapon["hit"] = hit
            weapon["damage"] = damage
            return weapon
    return None


def _extract_keywords_from_blocks(blocks: list, page_width: float, page_height: float) -> list[str] | None:
    """Extract keywords from the black bar at bottom (y > 75%)."""
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block["bbox"]
        if bbox[1] > page_height * 0.75:
            text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")
            text = text.strip()
            if text.isupper() and ',' in text and 10 <= len(text) <= 200:
                keywords = [kw.strip() for kw in text.split(',') if kw.strip() and kw.strip() not in ['AND', 'OR']]
                if keywords:
                    return keywords
    return None


def _extract_rules_from_blocks(blocks: list, page_width: float, page_height: float,
                                region_y1: float) -> list[dict] | None:
    """Extract rules and unique actions from ability blocks below the header."""
    ability_text = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block["bbox"]
        if bbox[1] >= region_y1:
            for line in block.get("lines", []):
                line_text = ""
                is_bold = False
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    font = span.get("font", "")
                    if any(ind in font for ind in ["Bold", "-Bd", "Heavy"]) or span.get("flags", 0) & 16:
                        is_bold = True
                    line_text += text
                line_text = line_text.strip()
                if line_text:
                    ability_text.append((line_text, is_bold))

    if not ability_text:
        return None

    rules = []
    i = 0
    while i < len(ability_text):
        text, is_bold = ability_text[i]
        
        if is_bold and text.upper() not in ['ABILITIES', 'UNIQUE ACTIONS', 'NOTES:', 'NOTES', 'WEAPONS']:
            if ':' in text:
                parts = text.split(':', 1)
                ability_name = parts[0].strip()
                ability_desc = parts[1].strip() if len(parts) > 1 else ""
                j = i + 1
                while j < len(ability_text):
                    nt, nb = ability_text[j]
                    if nb:
                        break
                    ability_desc += " " + nt
                    j += 1
                if ability_name and ability_name.upper() not in ['NAME', 'ATK', 'HIT', 'DMG', 'WR',
                                                                 'APL', 'WOUNDS', 'SAVE', 'MOVE',
                                                                 'UNIQUE ACTIONS', 'ABILITIES', 'NOTES']:
                    rules.append({"name": ability_name, "description": _clean_extracted_text(ability_desc.strip())})
                i = j
                continue
            else:
                ua_name = text
                ua_desc = ""
                j = i + 1
                while j < len(ability_text):
                    nt, nb = ability_text[j]
                    if j + 1 < len(ability_text):
                        pt, pb = ability_text[j + 1]
                        if pb and pt.endswith('AP') and len(pt) <= 5:
                            break
                    if ',' in nt and nt.isupper() and len(nt) > 10:
                        break
                    ua_desc += " " + nt
                    j += 1
                if ua_name and ua_name.upper() not in ['NAME', 'ATK', 'HIT', 'DMG', 'WR',
                                                         'APL', 'WOUNDS', 'SAVE', 'MOVE',
                                                         'UNIQUE ACTIONS', 'ABILITIES', 'NOTES']:
                    rules.append({"name": ua_name, "description": _clean_extracted_text(ua_desc.strip())})
                i = j
                continue
        elif i + 1 < len(ability_text):
            nt, nb = ability_text[i + 1]
            if nb and nt.endswith('AP') and len(nt) <= 5:
                ua_name = text.lstrip('•■●▪-– ')
                cost = nt
                ua_desc = ""
                j = i + 2
                while j < len(ability_text):
                    dt, db = ability_text[j]
                    if ',' in dt and dt.isupper() and len(dt) > 10:
                        break
                    if dt.isdigit() and len(dt) <= 3:
                        break
                    if db and j + 1 < len(ability_text):
                        pt2, pb2 = ability_text[j + 1]
                        if pb2 and pt2.endswith('AP') and len(pt2) <= 5:
                            break
                    ua_desc += " " + dt
                    j += 1
                if ua_name and ua_name.upper() not in ['NAME', 'ATK', 'HIT', 'DMG', 'WR',
                                                         'APL', 'WOUNDS', 'SAVE', 'MOVE',
                                                         'UNIQUE ACTIONS', 'ABILITIES', 'NOTES']:
                    full_name = f"{ua_name} ({cost})" if cost != "0AP" else ua_name
                    rules.append({"name": full_name, "description": _clean_extracted_text(ua_desc.strip())})
                i = j
                continue
        i += 1
    return rules if rules else None


def _extract_operative_from_page(page: fitz.Page, page_idx: int, pdf_name: str) -> dict | None:
    """Extract operative stats from a single front-side datacard page."""
    pw = page.rect.width
    ph = page.rect.height
    blocks = page.get_text("dict").get("blocks", [])

    name = _extract_name_from_blocks(blocks, pw, ph)
    stats = _extract_stats_from_blocks(blocks, pw, ph)
    weapons = _extract_weapons_from_blocks(blocks, pw, ph, ph * 0.15, ph * 0.80)
    rules = _extract_rules_from_blocks(blocks, pw, ph, ph * 0.15)
    keywords = _extract_keywords_from_blocks(blocks, pw, ph)

    if not name or stats.get("wounds") is None:
        return None

    operative = {
        "name": name,
        "source_file": pdf_name,
        "source_page": page_idx,
        **stats,
    }
    if weapons:
        operative["weapons"] = weapons
    if rules:
        rules = _split_embedded_actions(rules)
        operative["passive_abilities"] = [r for r in rules if '(' not in r["name"] or 'AP)' not in r["name"]]
        operative["unique_actions"] = [r for r in rules if '(' in r["name"] and 'AP)' in r["name"]]
    if keywords:
        operative["keywords"] = keywords
    return operative


def _extract_backpage_rules(page: fitz.Page) -> list[dict] | None:
    """Extract rules/abilities from a back-side page."""
    pw = page.rect.width
    ph = page.rect.height
    blocks = page.get_text("dict").get("blocks", [])
    return _extract_rules_from_blocks(blocks, pw, ph, 0)


# ══════════════════════════════════════════════════════════════════════════════
# End of Datacard Extraction Functions
# ══════════════════════════════════════════════════════════════════════════════


logger = logging.getLogger(__name__)


# ===================================================================
# PATHS
# ===================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CLASSIFIED_DIR = PROJECT_ROOT / "layers" / "kt-app" / "classified"
OUTPUT_DIR = PROJECT_ROOT / "output_v3"


# ===================================================================
# TEXT EXTRACTION AND CLEANING
# ===================================================================

def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract all text from a PDF page.
    
    Args:
        pdf_path: Path to single-page PDF
        
    Returns:
        Extracted text content, cleaned
    """
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            return ""
        
        page = doc[0]
        text = page.get_text()
        doc.close()
        
        return clean_text(text)
    except Exception as e:
        logger.warning(f"Failed to extract text from {pdf_path}: {e}")
        return ""


def clean_text(text: str) -> str:
    """
    Clean up extracted text by fixing special characters and whitespace.
    
    Args:
        text: Raw extracted text
        
    Returns:
        Cleaned text
    """
    # Replace bullet characters with newline + bullet
    text = text.replace("\u0007", "\n• ")
    text = text.replace("\x95", "\n- ")
    text = text.replace("\x08", "")  # Remove backspace chars
    
    # Add newlines before existing bullets that don't have them
    text = re.sub(r"([^\n])\s*•\s+", r"\1\n• ", text)
    
    # Remove duplicate bullets
    text = re.sub(r"•\s+•\s+", "• ", text)
    
    # Collapse multiple spaces (but preserve newlines)
    text = re.sub(r"  +", " ", text)
    
    # Clean up multiple consecutive newlines
    text = re.sub(r"\n\n+", "\n\n", text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


# ===================================================================
# DATA EXTRACTION
# ===================================================================

class TeamDataExtractor:
    """Extract comprehensive team data from classified structure."""
    
    def __init__(self, team: str):
        self.team = team
        self.structure_path = CLASSIFIED_DIR / team / "structure.json"
        self.output_path = OUTPUT_DIR / team / "data" / "team_data.json"
    
    def extract(self) -> Optional[Dict]:
        """
        Extract all team data from structure.json.
        
        Returns:
            Team data dict or None if structure not found
        """
        if not self.structure_path.exists():
            logger.warning(f"Structure not found for {self.team}: {self.structure_path}")
            return None
        
        # Load structure
        try:
            with open(self.structure_path, 'r', encoding='utf-8') as f:
                structure = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load structure for {self.team}: {e}")
            return None
        
        # Initialize team data
        team_data = {
            "team": self.team,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Card types to extract (excluding token_guide - that's handled separately)
        card_types = [
            ("datacards", "datacards"),
            ("equipment", "equipment"),
            ("faction_rules", "faction_rules"),
            ("firefight_ploys", "firefight_ploys"),
            ("operatives_selection", "operatives_selection"),
            ("strategy_ploys", "strategy_ploys")
        ]
        
        total_extracted = 0
        for key, display_name in card_types:
            entities = structure.get(key, [])
            if not entities:
                continue
            
            extracted_data = []
            for entity in entities:
                entity_data = self._extract_entity_data(entity, key)
                if entity_data:
                    extracted_data.append(entity_data)
                    total_extracted += 1
            
            if extracted_data:
                team_data[key] = extracted_data
        
        if total_extracted > 0:
            logger.info(f"  Extracted data from {total_extracted} cards")
            return team_data
        else:
            logger.warning(f"  No data extracted for {self.team}")
            return None
    
    def _extract_entity_data(self, entity: Dict, entity_type: str) -> Optional[Dict]:
        """
        Extract data from a single entity (card group).
        
        For datacards: Uses proven structured extraction (stats, weapons, abilities, keywords)
        For operatives_selection: Extracts loadout selection options
        For other cards: Extracts name and text content
        
        Args:
            entity: Entity dict from structure.json
            entity_type: Type of entity (datacards, equipment, etc.)
            
        Returns:
            Extracted entity data
        """
        name = entity.get("name", "UNKNOWN")
        cards = entity.get("cards", [])
        
        if not cards:
            return None
        
        # Special handling for datacards - use proven extraction
        if entity_type == "datacards":
            return self._extract_datacard(entity, cards)
        
        # Special handling for operatives_selection - parse loadout options
        if entity_type == "operatives_selection":
            return self._extract_operatives_selection(entity, cards)
        
        # Special handling for faction_rules - parse multi-component rules
        if entity_type == "faction_rules":
            return self._extract_faction_rule(entity, cards)
        
        # Simple text extraction for other card types
        return self._extract_simple_text(name, cards)
    
    def _extract_datacard(self, entity: Dict, cards: List[Dict]) -> Optional[Dict]:
        """
        Extract structured datacard data using proven extraction logic.
        
        Args:
            entity: Entity dict from structure.json
            cards: Cards array from entity
            
        Returns:
            Structured operative data with stats, weapons, abilities, keywords
        """
        # Find front page
        front_card = None
        back_card = None
        
        for card in cards:
            if "front" in card:
                front_card = card
            if "back" in card:
                back_card = card
        
        if not front_card or "front" not in front_card:
            logger.debug(f"  No front page found for {entity.get('name')}")
            return None
        
        front_path = PROJECT_ROOT / front_card["front"]
        if not front_path.exists():
            logger.warning(f"  Front page not found: {front_path}")
            return None
        
        try:
            # Extract from front page using proven extraction
            doc = fitz.open(front_path)
            page = doc[0]
            
            operative = _extract_operative_from_page(page, 0, front_path.name)
            doc.close()
            
            if not operative:
                logger.debug(f"  Failed to extract datacard data for {entity.get('name')}")
                return None
            
            # Extract additional rules from back page if present
            if back_card and "back" in back_card:
                back_path = PROJECT_ROOT / back_card["back"]
                if back_path.exists():
                    try:
                        doc = fitz.open(back_path)
                        page = doc[0]
                        back_rules = _extract_backpage_rules(page)
                        doc.close()
                        
                        if back_rules:
                            # Split any abilities with embedded actions
                            back_rules = _split_embedded_actions(back_rules)
                            
                            # Merge back page rules with front page rules
                            passive = [r for r in back_rules if '(' not in r["name"] or 'AP)' not in r["name"]]
                            actions = [r for r in back_rules if '(' in r["name"] and 'AP)' in r["name"]]
                            
                            if passive:
                                existing_passive = operative.get("passive_abilities", [])
                                operative["passive_abilities"] = existing_passive + passive
                            
                            if actions:
                                existing_actions = operative.get("unique_actions", [])
                                operative["unique_actions"] = existing_actions + actions
                    except Exception as e:
                        logger.debug(f"  Failed to extract back page rules: {e}")
            
            # Remove source_file and source_page (internal metadata)
            operative.pop("source_file", None)
            operative.pop("source_page", None)
            
            return operative
            
        except Exception as e:
            logger.warning(f"  Failed to extract datacard for {entity.get('name')}: {e}")
            return None
    
    def _extract_faction_rule(self, entity: Dict, cards: List[Dict]) -> Optional[Dict]:
        """
        Extract faction rule with optional component/option parsing.
        
        For rules with multiple cards, extracts the main description and then
        parses individual components/options from subsequent cards.
        
        Args:
            entity: Entity dict from structure.json
            cards: Cards array from entity
            
        Returns:
            Dict with name, text, and optional 'options' array for multi-component rules
        """
        # First get all text using simple extraction
        simple_data = self._extract_simple_text(entity.get("name", "UNKNOWN"), cards)
        if not simple_data:
            return None
        
        name = simple_data.get("name")
        full_text = simple_data.get("text", "")
        
        # Check if this is a multi-component rule
        # Markers: "OPTIONS ARE PRESENTED ON", "CONTINUES ON OTHER SIDE"
        # Also check if rule has multiple cards (likely has components)
        has_multi_cards = len(cards) > 1
        has_options_marker = any(marker in full_text for marker in ["OPTIONS ARE PRESENTED ON", "options are presented on", "CONTINUES ON OTHER SIDE", "continues on other side"])
        
        # Multi-card rules are likely multi-component rules (unless very short)
        if has_options_marker or (has_multi_cards and len(full_text) > 300):
            # This is a multi-component rule - parse it
            return self._parse_multi_component_rule(name, full_text, cards)
        
        # Simple rule - return as-is
        return simple_data
    
    def _parse_multi_component_rule(self, name: str, full_text: str, cards: List[Dict]) -> Dict:
        """
        Parse a faction rule with multiple components/options.
        
        Args:
            name: Rule name
            full_text: Full concatenated text
            cards: Cards array from entity
            
        Returns:
            Dict with name, text (intro), and options array
        """
        # Split by separator to get individual card texts
        card_texts = full_text.split("\n\n---\n\n")
        
        # First card contains the main rule text
        main_text = card_texts[0] if card_texts else ""
        
        # Extract main text (stop at marker and remove it)
        # Handle various marker formats that indicate options on another card
        marker_patterns = [
            r'CHAPTER TACTIC[\s\n]+OPTIONS ARE PRESENTED ON[\s\n]+THEIR OWN CARD',
            r'OPTIONS ARE PRESENTED ON[\s\n]+THEIR OWN CARD',
            r'OPTIONS ARE PRESENTED ON[\s\n]+SEPARATE CARDS?',
            r'RULES ARE PRESENTED ON[\s\n]+THEIR OWN CARD',
        ]
        
        for pattern in marker_patterns:
            match = re.search(pattern, main_text, re.IGNORECASE)
            if match:
                # Take everything before the marker
                main_text = main_text[:match.start()].strip()
                break
        
        # Parse remaining cards for components/options
        options = []
        for idx, card_text in enumerate(card_texts[1:], 1):
            # Check if this card starts a new FACTION RULE (not a continuation of current rule)
            # Format: "TEAM NAME\nFACTION RULE\nRULE NAME"
            lines = [ln.strip() for ln in card_text.split('\n') if ln.strip()]
            is_new_rule = False
            if len(lines) >= 3:
                # Check for pattern: [..., "FACTION RULE", "RULE NAME"]
                for i, line in enumerate(lines[:5]):  # Check first 5 lines
                    if 'FACTION RULE' in line.upper() and i + 1 < len(lines):
                        next_line = lines[i + 1]
                        # If next line is all caps and different from current rule name
                        if next_line.isupper() and next_line != name and len(next_line) > 3:
                            is_new_rule = True
                            break
            
            if is_new_rule:
                # This is a different faction rule, stop parsing options
                break
            
            # Parse numbered or named options from this card
            parsed_options = self._parse_rule_options_from_text(card_text)
            options.extend(parsed_options)
        
        return {
            "name": name,
            "text": main_text,
            "options": options
        }
    
    def _parse_rule_options_from_text(self, text: str) -> List[Dict]:
        """
        Parse individual rule options/components from text.
        
        Handles formats like:
        - "1. OPTION NAME\nDescription text..."
        - "OPTION NAME\nDescription text..."
        
        Args:
            text: Text containing rule options
            
        Returns:
            List of dicts with name and text for each option
        """
        options = []
        
        # Split into lines
        lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
        
        # Skip header lines (faction name, rule type, etc.)
        start_idx = 0
        rule_name_from_header = None
        for i, line in enumerate(lines):
            # Skip lines that look like headers
            if any(header in line.upper() for header in ['FACTION RULE', 'CONTINUES ON OTHER SIDE', 'KILL TEAM']):
                start_idx = i + 1
                continue
            # Capture the rule name if it appears as a header (we'll skip it when parsing options)
            if i < 3 and line.isupper() and 5 < len(line) < 60 and not any(kw in line for kw in ['FACTION', 'RULE', 'CONTINUES']):
                rule_name_from_header = line
                start_idx = i + 1
                continue
            # Found first option, stop skipping
            if line and (line[0].isdigit() or (line.isupper() and len(line) < 60)):
                break
        
        lines = lines[start_idx:]
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Stop if we hit a new FACTION RULE section (indicates end of options)
            if 'FACTION RULE' in line.upper():
                # Check next line to see if it's a different rule name
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if next_line.isupper() and rule_name_from_header and next_line != rule_name_from_header:
                        # This is a new faction rule, stop parsing options
                        break
            
            # Skip repeated header that matches the main rule name
            if rule_name_from_header and line == rule_name_from_header:
                i += 1
                continue
            
            # Check for numbered option: "1. OPTION NAME"
            numbered_match = re.match(r'^(\d+)\.\s+(.+)$', line)
            if numbered_match:
                option_name = numbered_match.group(2).strip()
                option_text = []
                i += 1
                
                # Collect description lines until next option or end
                while i < len(lines):
                    next_line = lines[i]
                    
                    # Stop at FACTION RULE section
                    if 'FACTION RULE' in next_line.upper():
                        break
                    
                    # Check if this is the next numbered option
                    if re.match(r'^\d+\.\s+', next_line):
                        break
                    
                    # Skip repeated header
                    if rule_name_from_header and next_line == rule_name_from_header:
                        i += 1
                        continue
                    
                    # Check if this looks like a new section header
                    if next_line.isupper() and len(next_line) < 60 and any(kw in next_line for kw in ['CONTINUES', 'FACTION', 'RULE']):
                        break
                    
                    option_text.append(next_line)
                    i += 1
                
                if option_text:
                    options.append({
                        "name": option_name,
                        "text": ' '.join(option_text).strip()
                    })
                continue
            
            # Check for non-numbered option (all caps OR title case, short)
            # Skip lines with keywords that indicate headers
            is_option_candidate = (
                3 < len(line) < 60 
                and (line.isupper() or line[0].isupper())
                and not any(kw in line.upper() for kw in ['CONTINUES', 'FACTION RULE', 'SIDE'])
            )
            
            if is_option_candidate:
                # Skip if this is the repeated header
                if rule_name_from_header and line == rule_name_from_header:
                    i += 1
                    continue
                
                option_name = line
                option_text = []
                i += 1
                
                # Special case: check if option name is embedded in FIRST word(s) of description
                # Only apply if option_name looks incomplete (single word, all caps)
                # This handles formats like "SKILL AT ARMS Light 'Em Up Description..."
                # But NOT "Ice In Your Veins All Cadians are subjected..." (already complete name)
                needs_embedded_extraction = (
                    option_name.isupper() 
                    and len(option_name.split()) == 1 
                    and len(option_name) < 20
                )
                
                if needs_embedded_extraction and i < len(lines):
                    next_line = lines[i]
                    # If next line starts with title-case words, option name might be embedded
                    if next_line and next_line[0].isupper() and not next_line.isupper():
                        # Try to extract option name from start of line
                        words = next_line.split()
                        option_name_words = []
                        desc_words = []
                        
                        for j, word in enumerate(words):
                            # Capitalized words or special cases like "'Em"
                            if word and (word[0].isupper() or word.lower() in ["'em", "'s"]):
                                option_name_words.append(word)
                            else:
                                # Rest is description
                                desc_words = words[j:]
                                break
                        
                        # Only use embedded name if we found 2+ words
                        if len(option_name_words) >= 2:
                            option_name = ' '.join(option_name_words)
                            if desc_words:
                                option_text.append(' '.join(desc_words))
                            i += 1
                
                # Collect description lines until next option or end
                while i < len(lines):
                    next_line = lines[i]
                    
                    # Stop at FACTION RULE
                    if 'FACTION RULE' in next_line.upper():
                        break
                    
                    # Skip repeated header
                    if rule_name_from_header and next_line == rule_name_from_header:
                        i += 1
                        continue
                    
                    # Check if this is next option (all caps, short)
                    if next_line.isupper() and 3 < len(next_line) < 60:
                        break
                    
                    # Check for numbered option
                    if re.match(r'^\d+\.\s+', next_line):
                        break
                    
                    option_text.append(next_line)
                    i += 1
                
                # Only add if we got some description text
                if option_text:
                    options.append({
                        "name": option_name,
                        "text": ' '.join(option_text).strip()
                    })
                continue
            
            i += 1
        
        return options
    
    def _extract_operatives_selection(self, entity: Dict, cards: List[Dict]) -> Optional[Dict]:
        """
        Extract operative loadout selection options from operatives card.
        
        Args:
            entity: Entity dict from structure.json
            cards: Cards array from entity
            
        Returns:
            Dict with name, text, and selection (structured loadout options)
        """
        # First get the text using simple extraction
        simple_data = self._extract_simple_text(entity.get("name", "UNKNOWN"), cards)
        if not simple_data:
            return None
        
        text = simple_data.get("text", "")
        
        # Parse loadout selection from text
        selection = self._parse_selection_from_text(text)
        
        # Return with both text and structured selection
        return {
            "name": simple_data.get("name"),
            "text": text,
            "selection": selection
        }
    
    def _parse_selection_from_text(self, text: str) -> Dict[str, List]:
        """
        Parse operative loadout selection options from operatives card text.
        
        Format example:
            "ASSAULT INTERCESSOR SERGEANT with one option from each of the following:
                • Hand flamer or heavy bolt pistol
                • Chainsword, power fist, power weapon or thunder hammer
             Or the following option:
                • Plasma pistol; chainsword"
        
        Returns:
            Dict mapping operative names to list of option groups (arrays of weapon choices)
        """
        selection = {}
        
        # Pre-process: merge operative header lines that span multiple lines
        # E.g., "• OPERATIVE with \n one option from" → "• OPERATIVE with one option from"
        lines = text.split('\n')
        processed_lines = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # If line ends with "with" or "with auxiliary", merge with next line(s) until we get full phrase
            if line and (line.endswith(' with') or line.endswith(' auxiliary')) and i + 1 < len(lines):
                # Keep merging until we get a complete "with ... one of/one option" phrase
                while i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if not next_line:
                        i += 1
                        continue
                    line = line + ' ' + next_line
                    i += 1
                    # Stop if we've completed the phrase
                    if 'one of' in line.lower() or 'one option' in line.lower():
                        break
            
            if line:
                processed_lines.append(line)
            i += 1
        
        lines = processed_lines
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Look for operative name with loadout options
            # Pattern: "• OPERATIVE NAME with one option from"
            # or: "• OPERATIVE NAME with auxiliary ... and one of"
            # or: "• OPERATIVE NAME with one of the following"
            if ('with one option' in line.lower() or 
                ('with auxiliary' in line.lower() and 'one of' in line.lower()) or
                ('with one of the following' in line.lower())):
                # Extract operative name (everything between • and "with")
                match = re.match(r'^[•\s]*(.+?)\s+with\s+', line, re.IGNORECASE)
                if match:
                    operative_name = match.group(1).strip().upper()
                    option_groups = []
                    i += 1
                    
                    # Parse option groups marked by ◯ or "Or the following option"
                    current_group_lines = []
                    
                    while i < len(lines):
                        opt_line = lines[i].strip()
                        
                        # Check if we hit next operative (starts with • and looks like operative name with "with")
                        if opt_line.startswith('•') and ' with ' in opt_line.lower():
                            # Next operative found, stop here
                            break
                        
                        # Check for standalone operative names without options
                        if (opt_line.startswith('•') and 
                            opt_line[1:].strip().isupper() and
                            len(opt_line) < 60 and
                            any(kw in opt_line.upper() for kw in ['SERGEANT', 'CAPTAIN', 'WARRIOR', 'GUNNER', 'GRENADIER', 'SNIPER']) and
                            ' with ' not in opt_line.lower()):
                            # Next operative found, stop here
                            break
                        
                        # Option group marker (◯ or ○)
                        if opt_line.startswith('◯') or opt_line.startswith('○'):
                            # Save previous group if any
                            if current_group_lines:
                                group_text = ' '.join(current_group_lines)
                                parsed_group = self._parse_weapon_options(group_text)
                                if parsed_group:
                                    option_groups.append(parsed_group)
                                current_group_lines = []
                            i += 1
                            continue
                        
                        # Alternative option group marker: "Or the following option:"
                        if 'or the following option' in opt_line.lower():
                            # Save previous group if any
                            if current_group_lines:
                                group_text = ' '.join(current_group_lines)
                                parsed_group = self._parse_weapon_options(group_text)
                                if parsed_group:
                                    option_groups.append(parsed_group)
                                current_group_lines = []
                            i += 1
                            continue
                        
                        # Weapon option line (starts with •)
                        if opt_line.startswith('•'):
                            # Remove bullet
                            opt_text = opt_line[1:].strip()
                            
                            # Skip certain non-weapon lines
                            if any(skip in opt_text.lower() for skip in ['auxiliary grenade launcher and', 'selected from', 'you cannot', 'other than', 'some', 'your kill team']):
                                i += 1
                                continue
                            
                            # Add to current group
                            current_group_lines.append(opt_text)
                        # Non-bullet line might be continuation of weapon name
                        elif current_group_lines and not opt_line.startswith('◯') and not opt_line.startswith('○'):
                            # Only merge if it looks like a continuation (lowercase start or partial word)
                            if opt_line and opt_line[0].islower():
                                current_group_lines[-1] += ' ' + opt_line
                        
                        i += 1
                    
                    # Save last group if any
                    if current_group_lines:
                        group_text = ' '.join(current_group_lines)
                        parsed_group = self._parse_weapon_options(group_text)
                        if parsed_group:
                            option_groups.append(parsed_group)
                    
                    # Save to selection
                    selection[operative_name] = option_groups
                    continue
            
            # Check for operative with no loadout options (e.g., "• SPACE MARINE CAPTAIN")
            elif line.startswith('•'):
                # Remove bullet
                operative_line = line[1:].strip()
                # Check if it's just an operative name (all caps, no "with")
                if (operative_line.isupper() and 
                    len(operative_line) < 60 and
                    'with' not in operative_line.lower() and
                    any(keyword in operative_line for keyword in ['SERGEANT', 'CAPTAIN', 'WARRIOR', 'GUNNER', 'GRENADIER', 'SNIPER', 'LEADER'])):
                    
                    # This is an operative with no loadout options
                    selection[operative_line] = []
            
            i += 1
        
        return selection
    
    def _parse_weapon_options(self, options_text: str) -> List[str]:
        """
        Parse a weapon options string into a list of weapon names.
        
        Handles:
        - "A or B" → ["A", "B"]
        - "A, B or C" → ["A", "B", "C"]
        - "A; B" → ["A; B"] (exclusive combo, kept as single option)
        
        Args:
            options_text: Text containing weapon options
            
        Returns:
            List of weapon option strings
        """
        # Check if this is a semicolon combo (exclusive set)
        if ';' in options_text:
            # Keep as single option
            return [options_text.strip()]
        
        # Split by " or " and ", " but preserve multi-word weapon names
        # Replace " or " with a marker
        text = options_text.replace(' or ', '|||OR|||')
        
        # Now split by both comma and our marker
        parts = []
        for segment in text.split('|||OR|||'):
            # Split segment by comma if present
            if ',' in segment:
                # Be careful with commas - they might be within weapon names or separating them
                # Strategy: split by comma, then check if parts make sense
                comma_parts = [p.strip() for p in segment.split(',')]
                for part in comma_parts:
                    if part:
                        parts.append(part)
            else:
                if segment.strip():
                    parts.append(segment.strip())
        
        # Clean up and capitalize properly
        weapons = []
        for part in parts:
            part = part.strip()
            if part and len(part) > 1:
                # Capitalize first letter only
                weapons.append(part[0].upper() + part[1:])
        
        return weapons
    
    def _extract_simple_text(self, name: str, cards: List[Dict]) -> Optional[Dict]:
        """
        Extract simple text content from non-datacard pages.
        
        Args:
            name: Entity name
            cards: Cards array
            
        Returns:
            Dict with name and text
        """
        # Extract text from all pages (front and back)
        all_text = []
        for card in cards:
            # Front page
            if "front" in card:
                front_path = PROJECT_ROOT / card["front"]
                if front_path.exists():
                    text = extract_text_from_pdf(front_path)
                    if text:
                        all_text.append(text)
            
            # Back page
            if "back" in card:
                back_path = PROJECT_ROOT / card["back"]
                if back_path.exists():
                    text = extract_text_from_pdf(back_path)
                    if text:
                        all_text.append(text)
        
        # Combine all text with separator
        combined_text = "\n\n---\n\n".join(all_text) if all_text else ""
        
        if not combined_text:
            logger.debug(f"  No text extracted for {name}")
            return None
        
        return {
            "name": name,
            "text": combined_text
        }
    
    def save(self, team_data: Dict) -> bool:
        """
        Save team data to output file.
        
        Args:
            team_data: Team data dict
            
        Returns:
            True if saved successfully
        """
        # Create output directory
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(team_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"  Saved: {self.output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save team data for {self.team}: {e}")
            return False


# ===================================================================
# MAIN EXECUTION
# ===================================================================

def process_team(team: str, force: bool = False) -> bool:
    """
    Process a single team.
    
    Args:
        team: Team slug
        force: Force re-extraction even if output exists
        
    Returns:
        True if processed successfully
    """
    extractor = TeamDataExtractor(team)
    
    # Check if output already exists
    if not force and extractor.output_path.exists():
        logger.info(f"Skipping {team} (output exists, use --force to re-extract)")
        return True
    
    logger.info(f"Processing {team}")
    
    # Extract data
    team_data = extractor.extract()
    if not team_data:
        return False
    
    # Save output
    return extractor.save(team_data)


def get_all_teams() -> List[str]:
    """Get list of all teams with classified structures."""
    if not CLASSIFIED_DIR.exists():
        return []
    
    teams = []
    for team_dir in sorted(CLASSIFIED_DIR.iterdir()):
        if team_dir.is_dir():
            structure_file = team_dir / "structure.json"
            if structure_file.exists():
                teams.append(team_dir.name)
    
    return teams


def main():
    parser = argparse.ArgumentParser(
        description="Extract comprehensive team data from classified structures"
    )
    parser.add_argument(
        "--teams",
        help="Comma-separated list of team slugs to process"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-extraction even if output exists"
    )
    
    args = parser.parse_args()
    
    # Determine teams to process
    if args.teams:
        teams = [t.strip() for t in args.teams.split(",")]
    else:
        teams = get_all_teams()
    
    if not teams:
        logger.error("No teams found to process")
        return 1
    
    logger.info("=" * 70)
    logger.info(f"Step 3: Extract Team Data")
    logger.info("=" * 70)
    logger.info(f"Teams to process: {len(teams)}")
    logger.info("")
    
    # Process teams
    processed = 0
    skipped = 0
    failed = 0
    
    for team in teams:
        try:
            if process_team(team, force=args.force):
                processed += 1
            else:
                failed += 1
        except KeyboardInterrupt:
            logger.warning("\nInterrupted by user")
            return 1
        except Exception as e:
            logger.error(f"Error processing {team}: {e}")
            failed += 1
    
    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("Step 3 Complete!")
    logger.info(f"  Processed: {processed}")
    logger.info(f"  Failed: {failed}")
    logger.info("=" * 70)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
