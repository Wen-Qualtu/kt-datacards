"""Content analysis — shared, runs once on the integration output.

layers/integration/{team}/{team}-*.pdf (+ {team}/manifest.json)
   ->  layers/integration/{team}/content/{team}-content.json

Extracts comprehensive data from all card types into one per-team content manifest.
For datacards: proven structured extraction (APL, movement, save, wounds, weapons,
abilities, keywords). For other cards: name + text (with option/selection parsing).

Source-agnostic: reads the per-team integration PDFs and the source-agnostic manifest
emitted by integrate_classified, so it does not depend on which track ran.

Data Structure:
{
  "team": "battleclade",
  "generated_at": "2024-01-01T00:00:00Z",
  "datacards": [
    {
      "name": "BATTLECLADE TECHNOARCHEOLOGIST",
      "apl": 3, "movement": "6″", "save": "3+", "wounds": 9, "base_size": 40,
      "weapons": [{...}], "passive_abilities": [{...}],
      "unique_actions": [{...}], "keywords": [...]
    }
  ],
  "equipment": [{"name": "...", "text": "..."}],
  "faction_rules": [{"name": "...", "text": "..."}],
  ...
}
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional
import re

import fitz  # PyMuPDF

from ..utils import naming, paths
from ..utils.state import StateManager, StateIndex


# ===================================================================
# LOGGING SETUP
# ===================================================================

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Proven Datacard Extraction Functions
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


def _strip_trailing_statline(text: str, operative_name: str | None) -> str:
    """Remove trailing operative header/statline artifacts that leak from the
    front card's header block into an ability or action description.

    Two observed leak shapes (always at the very end of the description):
      * name + statline header, e.g.
        "...campaign or tournament. ASSAULT INTERCESSOR SERGEANT 3 APL WOUNDS SAVE MOVE 6\" 3+ 15"
      * bare operative name, e.g.
        "...within control range of an enemy operative. ELIMINATOR SNIPER"

    The leaked segment is always ALL CAPS (name + header labels + numeric stats),
    so the pre-header run is restricted to [A-Z0-9\\s] to avoid eating legitimate
    mixed-case description text.
    """
    if not text:
        return text
    # Trailing statline header (APL WOUNDS SAVE MOVE), optionally preceded by the
    # caps operative name and its APL digit, through end of string.
    text = re.sub(
        r"\s*[A-Z0-9][A-Z0-9\s]*?\bAPL\b\s+WOUNDS\s+SAVE\s+MOVE\b.*$",
        "",
        text,
        flags=re.DOTALL,
    ).strip()
    # Trailing bare operative name.
    if operative_name and operative_name.strip():
        esc = re.escape(operative_name.strip())
        text = re.sub(rf"\s*{esc}\s*$", "", text, flags=re.IGNORECASE).strip()
    return text


def _extract_stats_from_combined_text(text: str) -> tuple[str | None, dict]:
    """Extract name and stats from combined text like 'NAME26"5+9'.
    
    Returns:
        tuple: (name, stats_dict)
    """
    stats = {"apl": None, "movement": None, "save": None, "wounds": None}
    
    # Try to match: NAME + APL (1 digit) + movement (1-2 digits) + inch + save + plus + wounds
    # Pattern: text ending with: APL + movement + inch mark + save + plus + wounds
    # Example: "SPECTRE VETERAN SERGEANT26"5+9" = name + 2(APL) + 6(move) + " + 5(save) + + + 9(wounds)
    match = re.search(r'^(.+?)(\d)(\d+)[″"\'](\d+)\+(\d+)$', text)
    if match:
        name = match.group(1).strip()
        apl = int(match.group(2))
        movement = match.group(3) + "″"
        save = match.group(4) + "+"
        wounds = int(match.group(5))
        
        stats["apl"] = apl
        stats["movement"] = movement
        stats["save"] = save
        stats["wounds"] = wounds
        
        return name, stats
    
    # Try simpler pattern: NAME + APL at end (e.g., "SPECTRE GUIDE2")
    if text and text[-1].isdigit():
        stats["apl"] = int(text[-1])
        name = text[:-1].strip()
        return name, stats
    
    # No embedded stats found
    name = text.rstrip('0123456789').strip()
    return name if len(name) >= 3 else None, stats


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
            if text.isupper() and 3 <= len(text) <= 100:
                name, _ = _extract_stats_from_combined_text(text)
                if name and len(name) >= 3:
                    return name
    return None


def _extract_stats_from_blocks(blocks: list, page_width: float, page_height: float) -> dict:
    """Extract APL, movement, save, wounds from stat regions."""
    stats = {"apl": None, "movement": None, "save": None, "wounds": None}

    # First, try to extract stats from the combined name block (Spectre Squad format)
    # Look for text like "NAME26"5+9" in top-left corner
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
            
            if text.isupper() and 3 <= len(text) <= 100:
                _, extracted_stats = _extract_stats_from_combined_text(text)
                # If we found stats in the combined text, use them
                if extracted_stats.get("wounds") is not None:
                    return extracted_stats
                # Otherwise, keep any APL we found for later
                if extracted_stats.get("apl") is not None:
                    stats["apl"] = extracted_stats["apl"]
                break

    # Fallback: Standard format - extract APL from top-left if not already found
    if stats["apl"] is None:
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

    # Extract movement, save, wounds from top-right stats area
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
    used_movement = False
    used_save = False
    for num_str in all_numbers:
        # Skip the first occurrence of the movement value
        if stats.get("movement") and num_str == stats["movement"].rstrip("″\"'") and not used_movement:
            used_movement = True
            continue
        # Skip the first occurrence of the save value
        if stats.get("save") and num_str == stats["save"].rstrip("+") and not used_save:
            used_save = True
            continue
        # First remaining number is wounds
        # NOTE: APL is extracted from the top-left region and is NOT in stats_text,
        # so we do not skip numbers equal to APL here (this caused false-skip when wounds == APL).
        stats["wounds"] = int(num_str)
        break

    # Fallback for cards whose stat header merges into the top-left name block
    # (seen on some MOUNTED operatives, e.g. "DRAGON MASTER LEYSTALKER43+24" =
    # NAME + APL(4) + SAVE(3) + "+" + WOUNDS(24)). Only runs when the standard
    # region scan failed to find wounds, so it never affects working cards. The
    # movement value is not merged and is still read from the region above.
    if stats["wounds"] is None:
        for block in blocks:
            if block.get("type") != 0:
                continue
            bbox = block["bbox"]
            if bbox[0] < page_width * 0.6 and bbox[1] < 15:
                text = "".join(
                    span.get("text", "")
                    for line in block.get("lines", [])
                    for span in line.get("spans", [])
                ).strip()
                m = re.search(r"(\d)(\d)\+(\d{1,2})$", text)
                if m:
                    stats["apl"] = int(m.group(1))
                    stats["save"] = m.group(2) + "+"
                    stats["wounds"] = int(m.group(3))
                break

    return stats


def _extract_base_size_from_blocks(blocks: list, page_width: float, page_height: float) -> int | float | str | None:
    """Extract the model base size (mm) from the black circle in the bottom-right corner.

    The datacard prints the base size as white text inside a black circle at the far
    bottom-right of the front page. Round bases are a single diameter (e.g. 25, 32,
    40); oval bases are two dimensions (e.g. "75x42" for the 75mm x 42mm mounted
    bases) and are returned verbatim as an "AxB" string.
    """
    candidates = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        x0, y0, x1, y1 = block["bbox"]
        # Base-size circle sits in the far bottom-right corner of the card.
        if x0 > page_width * 0.88 and y0 > page_height * 0.82:
            text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")
            text = text.strip()
            # Oval base, e.g. "75x42" / "75 x 42" / "75×42".
            oval = re.fullmatch(r"(\d+)\s*[xX×]\s*(\d+)", text)
            if oval:
                a, b = int(oval.group(1)), int(oval.group(2))
                # Guard against stray numbers; real base sizes fall in this range.
                if 15 <= a <= 200 and 15 <= b <= 200:
                    candidates.append((y0, x0, f"{a}x{b}"))
                continue
            match = re.fullmatch(r"(\d+(?:\.\d+)?)", text)
            if not match:
                continue
            value = float(match.group(1))
            # Guard against stray numbers; real base sizes fall in this range.
            if 15 <= value <= 200:
                candidates.append((y0, x0, value))
    if not candidates:
        return None
    # Prefer the lowest, right-most candidate (the base circle).
    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
    value = candidates[0][2]
    if isinstance(value, str):
        return value
    return int(value) if value == int(value) else value


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
    # Some (usually melee) weapons render the ATK value on the SAME line as the
    # name, e.g. "Dominator maul & assault shield 4". The per-line stat detection
    # below only recognises a STANDALONE attacks digit, so without this split the
    # weapon has no ATK and is dropped entirely. Peel a trailing 1-2 digit number
    # (a valid ATK, 1-20) off the name line into its own token so it parses.
    if lines:
        m = re.match(r'^(.*\S)\s+(\d{1,2})$', lines[0])
        if m and 1 <= int(m.group(2)) <= 20:
            lines = [m.group(1).strip(), m.group(2)] + lines[1:]
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
    # Set upper bound to exclude keyword bar (y < 75% of page height)
    region_y2 = page_height * 0.75
    
    ability_text = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block["bbox"]
        # Only extract from middle region (between header and keyword bar)
        if region_y1 <= bbox[1] < region_y2:
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

    # DEBUG: Log ability_text for Kurnathi
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block["bbox"]
        if region_y1 <= bbox[1] < region_y2:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if "KURNATHI" in text.upper() or "Blademaster" in text:
                        logger.info(f"DEBUG: Found text in region: Y={bbox[1]}, text={text[:50]}")
                        logger.info(f"  ability_text length: {len(ability_text)}")
                        break

    rules = []
    i = 0
    
    while i < len(ability_text):
        text, is_bold = ability_text[i]
        
        # Check for ALL CAPS ability name followed by cost (even if not marked bold)
        if not is_bold and text.isupper() and len(text) > 3 and i + 1 < len(ability_text):
            nt, nb = ability_text[i + 1]
            if nt.endswith('AP') and len(nt) <= 5 and nt[0].isdigit():
                ua_name = text.lstrip('•■●▪-– ').rstrip('\x08\x07')
                cost = nt
                ua_desc = ""
                j = i + 2
                while j < len(ability_text):
                    dt, db = ability_text[j]
                    if dt.isupper() and len(dt) > 3 and j + 1 < len(ability_text):
                        next_t, _ = ability_text[j + 1]
                        if next_t.endswith('AP') and len(next_t) <= 5:
                            break
                    if ',' in dt and dt.isupper() and len(dt) > 10:
                        break
                    if dt.isdigit() and len(dt) <= 3:
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
        
        if is_bold:
            if ':' in text:
                parts = text.split(':', 1)
                ua_name = parts[0].strip().lstrip('•■●▪-– ')
                ua_desc = parts[1].strip() if len(parts) > 1 else ""
                j = i + 1
                while j < len(ability_text):
                    nt, nb = ability_text[j]
                    if nb and (':' in nt or (nt.endswith('AP') and len(nt) <= 5)):
                        break
                    if nb and j + 1 < len(ability_text):
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


def _extract_operative_from_page(page: fitz.Page, page_idx: int, pdf_name: str, known_name: str | None = None) -> dict | None:
    """Extract operative stats from a single front-side datacard page.
    
    Args:
        page: PDF page object
        page_idx: Page index
        pdf_name: PDF filename
        known_name: Pre-extracted operative name from structure.json (preferred over PDF extraction)
    """
    pw = page.rect.width
    ph = page.rect.height
    blocks = page.get_text("dict").get("blocks", [])

    # Use known_name if provided (from structure.json), otherwise extract from PDF
    if known_name:
        name = known_name
    else:
        name = _extract_name_from_blocks(blocks, pw, ph)
    
    stats = _extract_stats_from_blocks(blocks, pw, ph)
    base_size = _extract_base_size_from_blocks(blocks, pw, ph)
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
        "base_size": base_size,
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


# ===================================================================
# PATHS
# ===================================================================

# Per-team state lives at paths.pipeline_state_file(team); the StateManager /
# StateIndex helpers are shared with the downstream steps (pipeline.utils.state).


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


# ══════════════════════════════════════════════════════════════════════════════
# Operative-selection parser (PDF-native, drawing-aware * footnote detection)
# ══════════════════════════════════════════════════════════════════════════════
# Extracts per-operative weapon-loadout selection groups from the operative-selection
# card PDF automatically for any team. The "*" footnote marker is a vector drawing
# (small star), not a text char, so star detection uses page.get_drawings().

# Rules-prose markers: a wrapped weapon option never contains these nor ends with '.'
_SEL_CONT_STOP = (
    "includes", "must", "up to", "different", "other side", "faction rule",
    "instead", "you can", "e.g", " list", "this card", "cannot", "can only",
    "each operative", "kill team", "option)", "selected", "chosen",
    "weapon rule", "count", "selection", "piercing", "excluding",
)


def _sel_norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 ]", "", (s or "").upper())).strip()


def _sel_is_bold(span: dict) -> bool:
    return bool(span.get("flags", 0) & 16) or any(
        k in span.get("font", "") for k in ("Bold", "-Bd", "Heavy", "Demi"))


def _sel_is_prose(line: str) -> bool:
    low = line.strip().lower()
    if not low:
        return True
    if low.endswith("."):
        return True
    return any(k in low for k in _SEL_CONT_STOP)


def _sel_split_options(seg: str) -> List[str]:
    """Split "A, B or C" -> [A, B, C]; keep "X; Y" combos whole; preserve casing."""
    seg = seg.strip().rstrip(",")
    if ";" in seg:
        return [seg.strip()]
    seg = seg.replace(" or ", "|OR|")
    out = []
    for part in seg.split("|OR|"):
        for pp in part.split(","):
            pp = pp.strip()
            if len(pp) > 1:
                out.append(pp)
    return out


def _sel_star_positions(page) -> List[tuple]:
    """(x0, y_center) for each small star glyph (the * footnote/markers)."""
    stars = []
    for dr in page.get_drawings():
        r = dr["rect"]
        w, h = r.width, r.height
        if 3.5 <= w <= 8 and 3.5 <= h <= 9 and len(dr.get("items", [])) >= 12:
            stars.append((r.x0, (r.y0 + r.y1) / 2))
    return stars


def _sel_extract_rows(pdfs: List[Path]) -> List[dict]:
    """Ordered rows across every operative-selection page.
    Each row: dict(text, bold_name, name_x1, ycen, has_star, is_bullet)."""
    rows: List[dict] = []
    for p in pdfs:
        if not p.exists():
            continue
        try:
            doc = fitz.open(p)
        except Exception as e:
            logger.warning(f"Failed to open {p}: {e}")
            continue
        for page in doc:
            stars = _sel_star_positions(page)
            d = page.get_text("dict")
            lines = []
            for b in d.get("blocks", []):
                for ln in b.get("lines", []):
                    spans = ln.get("spans", [])
                    if not spans:
                        continue
                    text = "".join(s.get("text", "") for s in spans)
                    bold_parts = [s.get("text", "") for s in spans
                                  if _sel_is_bold(s) and s.get("text", "").strip()]
                    bold_name = " ".join(t.strip() for t in bold_parts).strip()
                    # strip leaked leading symbols/arrows/numbers (e.g. "↘ 1 ")
                    bold_name = re.sub(r"^[^A-Za-z\u00c0-\u024f]+", "", bold_name).strip()
                    # strip trailing superscript footnote digits ("GUNNER 1,2" -> "GUNNER")
                    bold_name = re.sub(r"[\s,0-9]+$", "", bold_name).strip()
                    name_x1 = None
                    for s in spans:
                        if _sel_is_bold(s) and s.get("text", "").strip():
                            name_x1 = s["bbox"][2]
                    y0 = ln["bbox"][1]
                    y1 = ln["bbox"][3]
                    lines.append((text, bold_name, name_x1, (y0 + y1) / 2))
            for text, bold_name, name_x1, ycen in lines:
                has_star = False
                if name_x1 is not None:
                    for sx, sy in stars:
                        if abs(sy - ycen) < 5 and (name_x1 - 4) <= sx <= (name_x1 + 14):
                            has_star = True
                            break
                stript = text.strip()
                rows.append(dict(text=stript, bold_name=bold_name, name_x1=name_x1,
                                 ycen=ycen, has_star=has_star, is_bullet=stript.startswith("•")))
        doc.close()
    return _sel_merge_continuations(rows)


def _sel_merge_continuations(rows: List[dict]) -> List[dict]:
    """Stitch an operative-name row with following wrapped fragments so a split
    header ('• MILITANT with' / 'one of the' / 'following options:') or a split
    loadout ('• GUNNER with' / 'flamer and' / 'bayonet1') lands on one row.
    Narrow-column PDFs wrap these across many short lines."""
    def _complete_hdr(low: str) -> bool:
        return "following" in low and ("option" in low or low.rstrip().endswith(":"))

    out = []
    i = 0
    while i < len(rows):
        r = dict(rows[i])
        low = r["text"].lower()
        if r["bold_name"] and not _complete_hdr(low):
            while i + 1 < len(rows):
                nxt = rows[i + 1]
                if nxt["bold_name"] or nxt["is_bullet"] or nxt["text"].startswith(("\u25cb", "\u25ef")):
                    break
                if _sel_is_prose(nxt["text"]):
                    break
                r["text"] = (r["text"] + " " + nxt["text"]).strip()
                low = r["text"].lower()
                i += 1
                if _complete_hdr(low):
                    break
        out.append(r)
        i += 1
    return out


def _sel_parse(rows: List[dict]) -> Dict[str, List]:
    """Walk rows -> {card_operative_name: [[option, ...], ...]} resolving * footnote."""
    selection: Dict[str, object] = {}
    starred: List[str] = []
    variants: Dict[str, List[str]] = {}
    footnote_raw: List[str] = []
    in_footnote = False
    cur = None
    cur_groups: List[List[str]] = []
    each_mode = False

    def flatten(groups):
        out = []
        for g in groups:
            opts = []
            for raw in g:
                opts.extend(_sel_split_options(raw))
            if opts:
                out.append(opts)
        return out

    def finalize():
        nonlocal cur, cur_groups
        if cur is not None:
            newsel = flatten(cur_groups)
            old = selection.get(cur)
            if old and isinstance(old, list) and newsel:
                if len(old) == 1 and len(newsel) == 1:
                    old[0].extend(newsel[0])
                else:
                    old.extend(newsel)
            else:
                selection[cur] = newsel
        cur = None
        cur_groups = []

    for r in rows:
        t = r["text"]
        low = t.lower()
        # Footnote header: standalone "* With one of the following options:" (no bold name)
        if not r["bold_name"] and not r["is_bullet"] and "with one of the following option" in low:
            finalize()
            in_footnote = True
            footnote_raw = []
            continue
        if in_footnote:
            if r["is_bullet"] and not r["bold_name"]:
                opt = t.lstrip("•").strip()
                if opt:
                    footnote_raw.append(opt)
                continue
            if not r["bold_name"] and not r["is_bullet"] and t.startswith(("\u25cb", "\u25ef")):
                footnote_raw.append(re.sub(r"^[\u25cb\u25ef]\s*", "", t).strip())
                continue
            if not r["bold_name"] and not r["is_bullet"] and footnote_raw and not _sel_is_prose(t):
                if t and (t[0].islower() or t[0] in ",;"):
                    footnote_raw[-1] += " " + t
                    continue
            in_footnote = False

        # Operative WITH inline options (leader or list)
        if r["bold_name"] and ("one of the following" in low or "one option from" in low
                               or "with one option" in low or "with the following" in low):
            finalize()
            cur = r["bold_name"]
            cur_groups = []
            each_mode = (("each of the following" in low) or ("one option from each" in low)
                         or ("with the following" in low and "one of the following" not in low))
            continue
        # Loadout variant: "• NAME with <loadout>" (not an options header) -> one option
        if (r["is_bullet"] and r["bold_name"] and " with " in low
                and not any(k in low for k in ("following", "one of the", "one option from"))):
            finalize()
            name = r["bold_name"]
            m = re.search(r"\bwith\s+(.*)$", t, re.IGNORECASE)
            loadout = m.group(1).strip() if m else ""
            if loadout:
                variants.setdefault(name, []).append(loadout)
            continue
        # Plain list operative: bulleted bold name, no "with"
        if r["is_bullet"] and r["bold_name"] and " with " not in low:
            finalize()
            name = r["bold_name"]
            if r["has_star"]:
                starred.append(name)
                selection[name] = "STAR"
            else:
                selection[name] = []
            continue
        # Option markers / lines while collecting for cur
        if cur is not None:
            if ("one option from each" in low) or ("or one option from each" in low):
                each_mode = True  # mid-operative switch
                continue
            if "or the following option" in low:
                if not each_mode:
                    cur_groups.append([])
                continue
            opt = None
            if t.startswith(("\u25cb", "\u25ef")):
                opt = re.sub(r"^[\u25cb\u25ef]\s*", "", t).strip()
            elif r["is_bullet"] and not r["bold_name"]:
                opt = t.lstrip("•").strip()
            if opt is not None:
                if not opt or any(s in low for s in _SEL_CONT_STOP) or _sel_is_prose(t):
                    continue
                if each_mode:
                    cur_groups.append([opt])
                else:
                    if not cur_groups:
                        cur_groups.append([])
                    cur_groups[-1].append(opt)
                continue
            if not r["bold_name"] and cur_groups and cur_groups[-1] and not _sel_is_prose(t):
                prev = cur_groups[-1][-1].rstrip()
                incomplete = prev.endswith((";", ",", "&", " or", " and", "-"))
                if t and (incomplete or t[0].islower() or t[0] in ",;"):
                    cur_groups[-1][-1] += " " + t
                    continue
    finalize()

    footnote_group = None
    if footnote_raw:
        opts = []
        for raw in footnote_raw:
            opts.extend(_sel_split_options(raw))
        footnote_group = opts
    for name in starred:
        selection[name] = [footnote_group] if footnote_group else []
    for name, loadouts in variants.items():
        if not selection.get(name):
            selection[name] = [loadouts]
    return selection


def _sel_map_to_datacards(selection: Dict[str, List], datacard_names: List[str]) -> Dict[str, List]:
    """Map card operative names to datacard names by shared-word scoring, one-to-one."""
    if not datacard_names:
        return dict(selection)
    stop = {"OF", "THE", "AND", "A", "AN", "WITH"}
    dc = [(set(_sel_norm(n).split()) - stop, _sel_norm(n), n) for n in datacard_names]
    used = set()
    out: Dict[str, List] = {}
    for card_name in sorted(selection, key=lambda s: len(_sel_norm(s).split()), reverse=True):
        groups = selection[card_name]
        cw = set(_sel_norm(card_name).split()) - stop
        cn = _sel_norm(card_name)
        best = None
        best_score = None
        for dwords, dnorm, dorig in dc:
            if dorig in used:
                continue
            if dnorm == cn:
                score = (100, 0)
            else:
                shared = len(cw & dwords)
                if shared == 0:
                    continue
                score = (shared, -abs(len(dwords) - len(cw)))
            if best_score is None or score > best_score:
                best_score = score
                best = dorig
        if best is not None:
            used.add(best)
            out[best] = groups
        else:
            out[card_name] = groups
    return out


# ===================================================================
# DATA EXTRACTION
# ===================================================================

class TeamDataExtractor:
    """Extract comprehensive team data from the shared integration layer."""

    def __init__(self, team: str):
        self.team = team
        self.manifest_path = paths.integration_manifest_file(team)
        self.output_path = paths.content_file(team)
        # Populated when datacards are extracted; used to key operative-selection
        # entries by datacard name (datacards run first in extract()).
        self._datacard_names: List[str] = []

    def _entity_integration_pdfs(self, entity: Dict, entity_type: str) -> List[Path]:
        """Resolve an entity's integration PDF paths, mirroring integrate_classified
        exactly (same type mapping + `-{card_number}` suffix for multi-card entities).
        Each PDF holds the front on page 0 and the optional back on page 1."""
        card_type = naming.STRUCTURE_KEY_TO_TYPE.get(entity_type, entity_type)
        name = entity.get("name") or "unknown"
        cards = entity.get("cards", [])
        multi = len(cards) > 1
        pdfs: List[Path] = []
        for card in cards:
            base = naming.classified_name(self.team, card_type, name)
            if multi:
                base = f"{base}-{card['card_number']}"
            pdfs.append(paths.integration_team_dir(self.team) / f"{base}.pdf")
        return pdfs

    @staticmethod
    def _pdf_page_texts(pdf_path: Path) -> List[str]:
        """Cleaned text for every page of an integration PDF (front, then back)."""
        try:
            doc = fitz.open(pdf_path)
            texts = [clean_text(p.get_text()) for p in doc]
            doc.close()
            return texts
        except Exception as e:
            logger.warning(f"Failed to read {pdf_path}: {e}")
            return []

    def extract(self) -> Optional[Dict]:
        """
        Extract all team data from the shared integration manifest + PDFs.

        Returns:
            Team data dict or None if the manifest is not found.
        """
        if not self.manifest_path.exists():
            logger.warning(f"Manifest not found for {self.team}: {self.manifest_path}")
            return None

        # Load the source-agnostic manifest (same shape as the structure manifest).
        try:
            with open(self.manifest_path, 'r', encoding='utf-8') as f:
                structure = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load manifest for {self.team}: {e}")
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
                if key == "datacards":
                    # Stash datacard operative names so operatives_selection (later in
                    # this loop) can map card names -> datacard names.
                    self._datacard_names = [d.get("name", "") for d in extracted_data if d.get("name")]
        
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
            entity: Entity dict from the manifest
            entity_type: Type of entity (datacards, equipment, etc.)
            
        Returns:
            Extracted entity data
        """
        name = entity.get("name", "UNKNOWN")
        cards = entity.get("cards", [])
        
        if not cards:
            return None

        pdfs = self._entity_integration_pdfs(entity, entity_type)

        # Special handling for datacards - use proven extraction
        if entity_type == "datacards":
            return self._extract_datacard(entity, pdfs)
        
        # Special handling for operatives_selection - parse loadout options
        if entity_type == "operatives_selection":
            return self._extract_operatives_selection(entity, pdfs)
        
        # Special handling for faction_rules - parse multi-component rules
        if entity_type == "faction_rules":
            return self._extract_faction_rule(entity, pdfs)
        
        # Simple text extraction for other card types
        return self._extract_simple_text(name, pdfs)
    
    def _extract_datacard(self, entity: Dict, pdfs: List[Path]) -> Optional[Dict]:
        """
        Extract structured datacard data using proven extraction logic.
        
        Args:
            entity: Entity dict from the manifest
            pdfs: Integration PDFs for this operative (page 0 = front, page 1 = back)
            
        Returns:
            Structured operative data with stats, weapons, abilities, keywords
        """
        # The first integration PDF is the stats card; its page 0 is the stat front.
        # Remaining pages (page 1 of the stats PDF + any "OWN CARDS" overflow PDFs)
        # carry back-side ability/action content.
        if not pdfs or not pdfs[0].exists():
            logger.warning(f"  Front page not found for {entity.get('name')}")
            return None

        front_path = pdfs[0]
        try:
            doc = fitz.open(front_path)
            # Use the cleaned name from the manifest.
            operative = _extract_operative_from_page(
                doc[0], 0, front_path.name, known_name=entity.get('name'))
            n_front_pages = doc.page_count
            doc.close()
        except Exception as e:
            logger.warning(f"  Failed to extract datacard for {entity.get('name')}: {e}")
            return None

        if not operative:
            logger.debug(f"  Failed to extract datacard data for {entity.get('name')}")
            return None

        # Collect back pages: remaining pages of the stats PDF, then every page of
        # each overflow PDF (their fronts are back-side action content).
        back_specs = [(front_path, i) for i in range(1, n_front_pages)]
        for extra in pdfs[1:]:
            if not extra.exists():
                continue
            try:
                d = fitz.open(extra)
                cnt = d.page_count
                d.close()
            except Exception:
                continue
            back_specs.extend((extra, i) for i in range(cnt))

        for pdf_path, page_idx in back_specs:
            try:
                doc = fitz.open(pdf_path)
                back_rules = _extract_backpage_rules(doc[page_idx])
                doc.close()
            except Exception as e:
                logger.debug(f"  Failed to extract back page rules: {e}")
                continue

            if back_rules:
                # Split any abilities with embedded actions
                back_rules = _split_embedded_actions(back_rules)

                # Merge back page rules with front page rules
                passive = [r for r in back_rules if '(' not in r["name"] or 'AP)' not in r["name"]]
                actions = [r for r in back_rules if '(' in r["name"] and 'AP)' in r["name"]]

                if passive:
                    operative["passive_abilities"] = operative.get("passive_abilities", []) + passive
                if actions:
                    operative["unique_actions"] = operative.get("unique_actions", []) + actions

        # Strip trailing operative header/statline artifacts that can leak into
        # ability/action descriptions during extraction (e.g. a "Chapter Veteran"
        # description ending with "... ASSAULT INTERCESSOR SERGEANT 3 APL WOUNDS SAVE MOVE 6\" 3+ 15").
        op_name = operative.get("name")
        for key in ("passive_abilities", "unique_actions"):
            for rule in operative.get(key, []) or []:
                rule["description"] = _strip_trailing_statline(rule.get("description", ""), op_name)

        # Remove source_file and source_page (internal metadata)
        operative.pop("source_file", None)
        operative.pop("source_page", None)

        return operative
    
    def _extract_faction_rule(self, entity: Dict, pdfs: List[Path]) -> Optional[Dict]:
        """
        Extract faction rule with optional component/option parsing.
        
        For rules with multiple cards, extracts the main description and then
        parses individual components/options from subsequent cards.
        
        Args:
            entity: Entity dict from the manifest
            pdfs: Integration PDFs for this rule
            
        Returns:
            Dict with name, text, and optional 'options' array for multi-component rules
        """
        # First get all text using simple extraction
        simple_data = self._extract_simple_text(entity.get("name", "UNKNOWN"), pdfs)
        if not simple_data:
            return None
        
        name = simple_data.get("name")
        full_text = simple_data.get("text", "")
        
        # Check if this is a multi-component rule
        # Markers: "OPTIONS ARE PRESENTED ON", "CONTINUES ON OTHER SIDE"
        # Also check if rule has multiple cards (likely has components)
        has_multi_cards = len(pdfs) > 1
        has_options_marker = any(marker in full_text for marker in ["OPTIONS ARE PRESENTED ON", "options are presented on", "CONTINUES ON OTHER SIDE", "continues on other side"])
        
        # Multi-card rules are likely multi-component rules (unless very short)
        if has_options_marker or (has_multi_cards and len(full_text) > 300):
            # This is a multi-component rule - parse it
            return self._parse_multi_component_rule(name, full_text)
        
        # Simple rule - return as-is
        return simple_data
    
    def _parse_multi_component_rule(self, name: str, full_text: str) -> Dict:
        """
        Parse a faction rule with multiple components/options.
        
        Args:
            name: Rule name
            full_text: Full concatenated text
            
        Returns:
            Dict with name, text (intro), and options array
        """
        # Split by separator to get individual card texts
        card_texts = full_text.split("\n\n---\n\n")

        # Normalized rule name for same-rule detection below. The entity name may be
        # a slug ("chapter-tactics") while the card repeats the display title
        # ("CHAPTER TACTICS"); comparing raw strings would treat the same rule's
        # option cards as a NEW rule and drop every option.
        name_norm = re.sub(r'[^a-z0-9]+', '', (name or '').lower())

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
                        # If next line is all caps and names a DIFFERENT rule (compared
                        # on a normalized form, so slug vs display casing still matches).
                        if (next_line.isupper() and len(next_line) > 3
                                and re.sub(r'[^a-z0-9]+', '', next_line.lower()) != name_norm):
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
            # A numbered-option line (e.g. "4. STEALTHY") is the first option,
            # never a card header — stop skipping before consuming it.
            if re.match(r'^\d+\.\s+', line):
                break
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
    
    def _extract_operatives_selection(self, entity: Dict, pdfs: List[Path]) -> Optional[Dict]:
        """
        Extract operative loadout selection options from the operatives-selection card.

        Uses a PDF-native, drawing-aware parser (the "*" footnote marker is a vector
        star, not a text char) and maps the card's operative names to the team's
        datacard names so `selection` is keyed consistently with the datacards.

        Args:
            entity: Entity dict from the manifest
            pdfs: Integration PDFs for this entity

        Returns:
            Dict with name, text, and selection (structured loadout options)
        """
        # Keep the raw text for reference / downstream text consumers.
        simple_data = self._extract_simple_text(entity.get("name", "UNKNOWN"), pdfs)
        if not simple_data:
            return None

        text = simple_data.get("text", "")

        # Structured loadout selection, parsed straight from the PDF geometry.
        rows = _sel_extract_rows(pdfs)
        raw_selection = _sel_parse(rows)
        selection = _sel_map_to_datacards(raw_selection, getattr(self, "_datacard_names", []))

        return {
            "name": simple_data.get("name"),
            "text": text,
            "selection": selection,
        }
    
    def _extract_simple_text(self, name: str, pdfs: List[Path]) -> Optional[Dict]:
        """
        Extract simple text content from an entity's integration PDFs.
        
        Args:
            name: Entity name
            pdfs: Integration PDFs (each: page 0 = front, page 1 = back)
            
        Returns:
            Dict with name and text
        """
        # Extract text from every page (front then back) of each card, keeping the
        # per-page separator so multi-component parsing can split cards back out.
        all_text = []
        for pdf in pdfs:
            if not pdf.exists():
                continue
            for text in self._pdf_page_texts(pdf):
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

        Writes byte-stably: if the previous file's content (excluding the
        volatile `generated_at` top-level timestamp) matches what we're about
        to write, the prior file's bytes AND mtime are restored. This stops
        downstream cache busters from spuriously bumping when nothing
        meaningful changed.

        Args:
            team_data: Team data dict

        Returns:
            True if saved successfully
        """
        # Create output directory
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            prior_bytes = None
            prior_mtime = None
            if self.output_path.exists():
                try:
                    prior_bytes = self.output_path.read_bytes()
                    prior_mtime = self.output_path.stat().st_mtime
                except OSError:
                    prior_bytes = None

            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(team_data, f, indent=2, ensure_ascii=False)

            if prior_bytes is not None:
                try:
                    import copy as _copy
                    prior_obj = json.loads(prior_bytes.decode('utf-8-sig'))
                    prior_snap = _copy.deepcopy(prior_obj)
                    new_snap = _copy.deepcopy(team_data)
                    for snap in (prior_snap, new_snap):
                        if isinstance(snap, dict) and 'generated_at' in snap:
                            snap['generated_at'] = ''
                    if json.dumps(prior_snap, sort_keys=True) == json.dumps(new_snap, sort_keys=True):
                        # Content unchanged — restore prior bytes + mtime.
                        self.output_path.write_bytes(prior_bytes)
                        import os
                        os.utime(self.output_path, (prior_mtime, prior_mtime))
                except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                    pass  # fall through and keep freshly-written file

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
    """All teams that have an integration manifest."""
    if not paths.INTEGRATION.exists():
        return []
    return sorted(
        d.name for d in paths.INTEGRATION.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    )


def _inputs_for(team: str) -> list:
    """Source files this step consumes: the manifest, the classified PDFs, and
    the shared team config (parsing rules depend on it)."""
    team_dir = paths.integration_team_dir(team)
    inputs = [paths.integration_manifest_file(team), paths.TEAM_CONFIG]
    inputs.extend(sorted(team_dir.glob("*.pdf")))
    return inputs


def run(teams=None, source=None, force=False):
    """Orchestrator entry point. Shared step — `source` is accepted for a uniform
    step signature but ignored (input is the source-agnostic integration layer)."""
    if teams is None:
        teams = get_all_teams()
    if not teams:
        logger.error("No teams found to process (run integrate_classified first)")
        return {"processed": 0, "skipped": 0, "failed": 0}

    logger.info(f"content_analysis: {len(teams)} team(s)")

    processed = skipped = failed = 0
    for team in teams:
        try:
            state = StateManager(team)
            inputs = _inputs_for(team)
            if state.can_skip("content_analysis", inputs, force):
                logger.info(f"  {team}: unchanged, skip")
                skipped += 1
                continue

            # Inputs changed (or --force): regenerate unconditionally.
            if process_team(team, force=True):
                out_file = paths.content_file(team)
                if out_file.exists():
                    processed += 1
                    # Per-team state: rewritten wholly for this team each run.
                    state.record_output("content_analysis", "content.json", out_file)
                    state.record_inputs("content_analysis", inputs)
                    state.mark_complete("content_analysis")
                    state.save()
                else:
                    skipped += 1
            else:
                failed += 1
        except KeyboardInterrupt:
            logger.warning("Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error processing {team}: {e}")
            failed += 1

    # Refresh the global index from all per-team state files (stale-key free).
    StateIndex().rebuild_and_save()

    logger.info(
        f"content_analysis done: processed={processed} skipped={skipped} failed={failed}"
    )
    return {"processed": processed, "skipped": skipped, "failed": failed}
