"""
Extract operative statlines from datacards PDFs (kt-app pipeline).

Reads processed/{team}/{team}-datacards.pdf (multi-page PDF, one page per card)
and extracts statlines (APL, Movement, Save, Wounds), weapons, keywords, and 
rules/abilities using coordinate-based region extraction from PyMuPDF.

Front pages (starting with "NAME" header) contain operative stats.
Back pages contain additional rules/abilities.

Output: output_v2/{faction}/{team}/statlines/roster.json

Based on the warcom pipeline's 6_extract_statlines.py, adapted for the 
multi-page datacards PDFs produced by the kt-app export.

Usage:
    python script/extract_statlines.py
    python script/extract_statlines.py --teams kasrkin,blooded
    python script/extract_statlines.py --force
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone

import fitz  # PyMuPDF
import yaml

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "processed"
OUTPUT_DIR = ROOT / "output"
OUTPUT_V2_DIR = ROOT / "output_v2"
TEAM_CONFIG_PATH = ROOT / "config" / "team-config.yaml"

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ── Team config helpers ──

def _load_team_config() -> dict:
    """Load team-config.yaml"""
    with open(TEAM_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _clean_extracted_text(text: str) -> str:
    """Clean up extracted text by fixing bullet characters and whitespace."""
    # Replace bullet characters
    text = text.replace("\u0007", "• ")
    text = text.replace("\x95", "- ")
    text = text.replace("•", "• ")  # Ensure space after bullet
    
    # Collapse multiple spaces
    text = re.sub(r" +", " ", text)
    
    # Clean up spacing around bullets
    text = re.sub(r"•\s+•", "• ", text)  # Remove duplicate bullets
    
    return text.strip()


def _get_team_faction(team: str) -> str:
    """Get faction for a team from team-config.yaml"""
    config = _load_team_config()
    team_data = config.get("teams", {}).get(team, {})
    return team_data.get("faction", "xenos")  # default to xenos if not found


# ── Coordinate-based extraction helpers ──

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

    # APL from name block (top-left, y < 15)
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

    # APL fallback: stats box region (x > 65%, y < 25%)
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

    # Collect stats box text (top-right)
    stats_text = ""
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block["bbox"]
        if bbox[0] > page_width * 0.65 and bbox[3] < page_height * 0.25:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    stats_text += span.get("text", "") + "|"

    # Movement: digit + " or ″
    move_match = re.search(r'(\d+)[″"\']', stats_text)
    if move_match:
        stats["movement"] = move_match.group(1) + "″"

    # Save: digit followed by +
    save_match = re.search(r'(\d+)\|?\+', stats_text)
    if save_match:
        stats["save"] = save_match.group(1) + "+"

    # Wounds: remaining number that isn't APL/movement/save
    # Use flags to skip each stat value only once (handles duplicate values like save=5, wounds=5)
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
    # Filter out control-character-only lines (e.g. \x07 BEL markers)
    lines = [ln for ln in lines if re.sub(r'[\x00-\x1f]+', '', ln).strip() or '\t' in ln]
    # Expand tab-joined name+attacks lines (e.g. "HYLas rotary cannon (sweeping)\t 4")
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
            
            # Fix: Clean control characters from weapon name and special_rules
            # Remove control characters (U+0000 to U+001F) from weapon name
            clean_name = re.sub(r'[\x00-\x1f]+', '', weapon["name"]).strip()
            
            # If cleaned name is empty or very short, extract real name from special_rules
            if not clean_name or len(clean_name) <= 1 or weapon["name"] in ['—', '-']:
                if sr:
                    # Clean control characters first
                    sr = re.sub(r'[\x00-\x1f]+', '', sr).strip()
                    
                    # Extract weapon name from the text before special rule keywords
                    match = re.match(r'^(.+?)\s+(Range\s|Piercing\s|Saturate|Torrent|Ceaseless|Lethal|Balanced|Brutal|Rending|Hot|Massive|Stun|Indirect|Silent|MW\s|AP\s|Unwieldy|Heavy|Relentless)', sr)
                    if match:
                        # Found a keyword - text before it is the weapon name
                        clean_name = match.group(1).strip()
                        # Everything from the keyword onwards is special rules
                        sr = sr[len(match.group(1)):].strip()
                    else:
                        # No keyword - check if ends with " - " or just "-"
                        if sr.endswith(' -') or sr == '-':
                            clean_name = sr.rstrip(' -').strip()
                            sr = None
                        else:
                            # Entire text is the weapon name
                            clean_name = sr
                            sr = None
            
            weapon["name"] = clean_name if clean_name else weapon["name"]
            
            # Clean control characters from special_rules too
            if sr:
                sr = re.sub(r'[\x00-\x1f]+', '', sr).strip()
            
            if sr and sr not in ['-', '']:
                weapon["special_rules"] = sr
            return weapon

    # Fallback: single-line with multiple spaces
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
                
                # Fix: Clean control characters and extract proper weapon name
                clean_name = re.sub(r'[\x00-\x1f]+', '', weapon["name"]).strip()
                
                if not clean_name or len(clean_name) <= 1 or weapon["name"] in ['—', '-']:
                    if sr:
                        # Clean control characters first
                        sr = re.sub(r'[\x00-\x1f]+', '', sr).strip()
                        
                        # Extract weapon name from the text before special rule keywords
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
                
                # Clean control characters from special_rules
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


# ── Page classification ──

def _is_front_page(page: fitz.Page) -> bool:
    """Check if a page is a front-side datacard (has the NAME weapon header row)."""
    blocks = page.get_text("dict").get("blocks", [])
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block["bbox"]
        if bbox[1] < 50:  # Header is typically in top quarter
            text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")
            # Header can be "NAME ATK HIT DMG WR" or "NAME A HIT D WR"
            if "NAME" in text and "HIT" in text and "WR" in text:
                return True
    return False


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


def _find_operative_for_backpage(page: fitz.Page) -> str | None:
    """Try to identify which operative this back page belongs to by looking at text."""
    text = page.get_text().strip()
    # Back pages often have the operative name in a stat block
    name_match = re.search(r"([A-Z][\w\s''-]+?)\n\s*\d+\s*\nAPL\nWOUNDS", text)
    if name_match:
        return name_match.group(1).strip()
    return None


# ── Operative selection parsing ──

def _find_asterisked_names(doc: fitz.Document) -> list[str]:
    """Find operative names marked with an asterisk (*) vector drawing.

    Asterisks are rendered as 19-segment vector paths with orange fill
    (~#f15c22). They appear next to bullet-entry operative names and
    reference a shared footnote. The footnote marker itself sits at the
    left margin (x < 15) — those are skipped.

    Scans all pages; page boundaries don't matter.
    """
    asterisked: list[str] = []

    for page in doc:
        # Collect asterisk rects on this page (skip margin footnote markers)
        asterisk_rects = []
        for d in page.get_drawings():
            fill = d.get("fill")
            if fill and len(d.get("items", [])) == 19:
                r, g, b = fill
                if r > 0.8 and g < 0.5 and b < 0.3 and d["rect"].x0 > 15:
                    asterisk_rects.append(d["rect"])

        if not asterisk_rects:
            continue

        # Match asterisk Y-positions to bullet-entry operative names
        for block in page.get_text("dict")["blocks"]:
            if "lines" not in block:
                continue
            for ln in block["lines"]:
                spans = ln["spans"]
                line_text = "".join(s["text"] for s in spans)
                if not line_text.strip().startswith("\u2022"):
                    continue

                # Extract operative name from bold spans
                name_parts = [s["text"] for s in spans if "Bold" in s.get("font", "")]
                if not name_parts:
                    continue

                op_name = "".join(name_parts).strip()
                # Skip bullets with inline options (e.g. "GUNNER with one of...")
                if "with" in line_text.lower() and "option" in line_text.lower():
                    continue

                line_bbox = ln["bbox"]
                for arect in asterisk_rects:
                    if arect.y0 < line_bbox[3] and arect.y1 > line_bbox[1]:
                        asterisked.append(op_name)
                        break

    return asterisked


def _parse_operative_selection(team: str, roster_names: list[str]) -> dict:
    """Parse operative selection PDF to extract weapon loadout options.

    Combines text from all pages of the operative-selection PDF, detects
    operatives with explicit inline options (e.g. "GUNNER with one of the
    following options:") and operatives marked with an asterisk footnote
    referencing a shared "* With one of ..." loadout block.

    Format: list[list[str]] — outer list = independent choice groups,
    inner list = alternatives within that group.
      - [] — no options (all weapons available)
      - [["opt1", "opt2"]] — pick 1 from a single group
      - [["ranged1", "ranged2"], ["melee1", "melee2"]] — pick 1 from each group
    """
    pdf_path = PROCESSED_DIR / team / f"{team}-operative-selection.pdf"
    if not pdf_path.exists():
        return {}

    doc = fitz.open(pdf_path)

    # Find operatives marked with asterisk vectors across all pages
    footnote_names = _find_asterisked_names(doc)

    # Combine text from all pages into one stream
    full_text = "\n".join(page.get_text() for page in doc)
    doc.close()

    # Normalize: join continuation lines into single logical lines
    raw_lines = full_text.split("\n")
    lines: list[str] = []
    skip_continuation = False
    in_footnote_block = False
    footnote_groups: list[list[str]] = []
    for raw in raw_lines:
        stripped = raw.strip().replace("\x07", "")
        if not stripped:
            skip_continuation = False
            if in_footnote_block and footnote_groups and footnote_groups[-1]:
                in_footnote_block = False
            continue
        if stripped[0] == "\u2198" or stripped.startswith(
            ("\u2022", "\u25cb", "\u25cf", "\u25ba")
        ):
            # If in footnote block, capture bullet options
            if in_footnote_block and stripped.startswith("\u2022"):
                option = re.sub(r"^[\u2022\s\x07]+", "", stripped).strip()
                if option and footnote_groups:
                    footnote_groups[-1].append(option)
                continue
            lines.append(stripped)
            skip_continuation = False
        elif footnote_names and stripped.startswith("With one of the following options:"):
            # Standalone footnote — capture its options
            in_footnote_block = True
            footnote_groups.append([])
        elif any(stripped.startswith(kw) for kw in (
            "CONTINUES", "Other than", "Some ", "Your kill", "You cannot",
            "You can ", "your kill", "you cannot", "RULE CONTIN",
        )):
            skip_continuation = True
            in_footnote_block = False
        elif re.match(r"^Or\s+(the\s+following|one\s+option)", stripped, re.I):
            lines.append(stripped)
            skip_continuation = False
        elif skip_continuation:
            continue
        elif in_footnote_block:
            continue
        elif lines:
            lines[-1] += " " + stripped

    # ── Parse lines ──
    raw_selection: dict[str, list[list[str]]] = {}
    fixed_loadouts: dict[str, list[str]] = {}  # OP name → list of "with ..." loadout strings
    current_op: str | None = None
    in_leader_options = False
    expect_from_each = False

    def _start_new_group(op: str, value: str | None = None) -> None:
        groups = raw_selection.setdefault(op, [])
        groups.append([value] if value else [])

    def _add_to_current_group(op: str, value: str) -> None:
        groups = raw_selection.setdefault(op, [])
        if not groups:
            groups.append([])
        groups[-1].append(value)

    for line in lines:
        # ── "Or" alternate sets ──
        if re.match(r"^Or\s+the\s+following\s+option", line, re.I):
            if current_op is not None:
                raw_selection.setdefault(current_op, []).append(["__OR__"])
                _start_new_group(current_op)
                expect_from_each = False
            continue
        if re.match(r"^Or\s+one\s+option\s+from\s+each", line, re.I):
            if current_op is not None:
                raw_selection.setdefault(current_op, []).append(["__OR__"])
                expect_from_each = True
            continue

        # ── Section headers (↘) ──
        if line.startswith("\u2198"):
            in_leader_options = False
            expect_from_each = False

            if re.search(r"operatives?\s+(selected\s+from|from\s+the\s+list)", line, re.I):
                current_op = None
                continue

            m = re.match(r"\u2198\s*\d+\s+.+?\s{2,}([\w][\w\s'\u2019-]*?)\s+operative", line)
            if not m:
                # Fallback for wrapped headers where double-space is lost
                m = re.match(r"\u2198\s*\d+\s+.*?([\w][\w\u2019-]+(?:-[\w]+)*)\s+operative", line)
            if m:
                current_op = m.group(1).strip()
                if "one option from each" in line:
                    raw_selection.setdefault(current_op, [])
                    in_leader_options = True
                    expect_from_each = True
                elif "one of the following options" in line:
                    raw_selection.setdefault(current_op, [[]])
                    in_leader_options = True
                    expect_from_each = False
                elif re.search(r"with\s+.+\s+and\s+one\s+of\s+the\s+following", line, re.I):
                    raw_selection.setdefault(current_op, [[]])
                    in_leader_options = True
                    expect_from_each = False
                elif re.search(r"with\s+the\s+following", line, re.I):
                    raw_selection.setdefault(current_op, [[]])
                    in_leader_options = True
                    expect_from_each = False
                else:
                    raw_selection.setdefault(current_op, [])
                    current_op = None
            continue

        # ── Bullet entries (•) ──
        if line.startswith(("\u2022", "\u25cf")):
            content = re.sub(r"^[\u2022\u25cf]\s*", "", line).strip()

            # Leader options
            if in_leader_options and current_op is not None:
                if expect_from_each:
                    # Each bullet defines a group; split comma/or alternatives
                    alts = re.split(r',\s+|\s+or\s+', content)
                    alts = [a.strip() for a in alts if a.strip()]
                    groups = raw_selection.setdefault(current_op, [])
                    groups.append(alts)
                else:
                    _add_to_current_group(current_op, content)
                continue

            in_leader_options = False
            expect_from_each = False

            # "OP with one option from each of the following:"
            m = re.match(
                r"([\w][\w\s'\u2019-]*?)\s+with\s+one\s+option\s+from\s+each", content
            )
            if m:
                current_op = m.group(1).strip()
                raw_selection.setdefault(current_op, [])
                expect_from_each = True
                continue

            # "OP with one of the following options:"
            m = re.match(
                r"([\w][\w\s'\u2019-]*?)\s+with\s+one\s+of\s+the\s+following\s+options:", content
            )
            if m:
                current_op = m.group(1).strip()
                raw_selection.setdefault(current_op, [[]])
                continue

            # "OP with X and one of the following options:"
            m = re.match(
                r"([\w][\w\s'\u2019-]*?)\s+with\s+.+?\s+and\s+one\s+of\s+the\s+following\s+options:",
                content,
            )
            if m:
                current_op = m.group(1).strip()
                raw_selection.setdefault(current_op, [[]])
                continue

            # Plain operative name or fixed loadout — no explicit options
            if " with " in content:
                op_name = content.split(" with ")[0].strip()
                loadout = content.split(" with ", 1)[1].strip()
                if op_name and op_name[0].isupper():
                    fixed_loadouts.setdefault(op_name, []).append(loadout)
                    raw_selection.setdefault(op_name, [])
            else:
                op_name = content.strip()
                if op_name and op_name[0].isupper():
                    raw_selection.setdefault(op_name, [])
            current_op = None
            continue

        # ── Sub-options (○) ──
        if line.startswith("\u25cb"):
            content = line.lstrip("\u25cb \t")
            if current_op is not None:
                if expect_from_each:
                    # Each sub-option defines a group; split comma/or alternatives
                    alts = re.split(r',\s+|\s+or\s+', content)
                    alts = [a.strip() for a in alts if a.strip()]
                    groups = raw_selection.setdefault(current_op, [])
                    groups.append(alts)
                else:
                    _add_to_current_group(current_op, content)
            continue

    # ── Clean up empty groups and compute exclusive sets ──
    exclusive_sets_map: dict[str, list[list[int]]] = {}
    for op_name in list(raw_selection.keys()):
        clean_groups: list[list[str]] = []
        sets: list[list[int]] = [[]]
        idx = 0
        for g in raw_selection[op_name]:
            if g == ["__OR__"]:
                sets.append([])
            elif g:
                clean_groups.append(g)
                sets[-1].append(idx)
                idx += 1
        raw_selection[op_name] = clean_groups
        # Only record exclusive_sets when there are 2+ non-empty sets
        if len(sets) > 1 and all(s for s in sets):
            exclusive_sets_map[op_name] = sets

    # ── Merge duplicate fixed-loadout operatives into selection groups ──
    for op_name, loadouts in fixed_loadouts.items():
        if len(loadouts) > 1 and not raw_selection.get(op_name):
            raw_selection[op_name] = [loadouts]

    # ── Apply footnote asterisk selections ──
    if footnote_names and footnote_groups:
        for fn_name in footnote_names:
            fn_upper = fn_name.upper()
            # Find matching key in raw_selection
            matched_key = None
            for key in raw_selection:
                if key.upper() == fn_upper:
                    matched_key = key
                    break
            if matched_key is None:
                for key in raw_selection:
                    if fn_upper in key.upper() or key.upper() in fn_upper:
                        matched_key = key
                        break
            if matched_key is not None and not raw_selection[matched_key]:
                raw_selection[matched_key] = [g[:] for g in footnote_groups]
                log.debug("  Applied footnote options to '%s': %s", matched_key, footnote_groups)
            elif matched_key is None:
                # Add as new entry
                raw_selection[fn_name] = [g[:] for g in footnote_groups]
                log.debug("  Added footnote operative '%s': %s", fn_name, footnote_groups)

    # Match short names to full roster names
    selection: dict[str, list[list[str]]] = {}
    exclusive_sets_out: dict[str, list[list[int]]] = {}
    for short_name, groups in raw_selection.items():
        short_upper = short_name.upper()
        matched = None

        # 1. Exact match
        for rname in roster_names:
            if rname.upper() == short_upper:
                matched = rname
                break

        # 2. Suffix match — prefer shortest roster name (most specific)
        if matched is None:
            best, best_len = None, float("inf")
            for rname in roster_names:
                ru = rname.upper()
                if ru.endswith(" " + short_upper) and len(rname) < best_len:
                    best, best_len = rname, len(rname)
            matched = best

        # 3. Fuzzy: all words present in roster name
        if matched is None:
            for rname in roster_names:
                if all(w in rname.upper() for w in short_upper.split()):
                    matched = rname
                    break

        if matched:
            if matched in selection:
                selection[matched].extend(groups)
            else:
                selection[matched] = groups
            if short_name in exclusive_sets_map:
                exclusive_sets_out[matched] = exclusive_sets_map[short_name]
        else:
            log.debug("  Selection operative '%s' not matched to roster", short_name)

    return selection, exclusive_sets_out


# ── Faction rule extraction ──

def _extract_faction_rules(team: str) -> dict | None:
    """Extract faction rule options from {team}-faction-rules.pdf if the team has a faction_rule config.

    Supports two PDF formats:
    1. Numbered entries: '1. AGGRESSIVE\\n<description text>...' (e.g. Angels of Death)
    2. Per-page entries: Each option on its own page with title-case name (e.g. Legionaries)

    Uses config option names to locate text in the PDF.
    Returns dict with rule name and options list, or None.
    """
    
    def _clean_faction_rule_text(text: str, team: str, rule_name: str) -> str:
        """Clean up extracted faction rule text by removing headers and fixing encoding."""
        # Replace bullet characters
        text = text.replace("\u0007", "• ")
        text = text.replace("\x95", "- ")
        text = text.replace("•", "• ")  # Ensure space after bullet
        
        # Collapse multiple spaces/newlines
        text = re.sub(r"\s+", " ", text)
        
        # Remove repeated headers (case-insensitive patterns)
        # Common patterns: "TEAM NAME FACTION RULE", "RULE NAME", "FACTION RULE"
        team_upper = team.replace("-", " ").upper()
        rule_upper = rule_name.upper()
        
        # Remove all occurrences of these headers
        patterns_to_remove = [
            rf"\b{re.escape(team_upper)}\s+FACTION\s+RULE\b",
            rf"\b{re.escape(rule_upper)}\b",
            r"\bFACTION\s+RULE\b",
            rf"\b{re.escape(team_upper)}\b",  # Just team name
        ]
        
        for pattern in patterns_to_remove:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        
        # Stop at common continuation markers (start of next section)
        # These usually indicate we've gone too far
        stop_markers = [
            r"MUTATION",  # Chaos Cult specific
            r"ASTARTES",  # Angels of Death specific  
            r"ANGEL\s+OF\s+DEATH",  # AoD team name variant
            r"These genetically modified",  # AoD continuation
            r"Through arcane ritual",  # Chaos Cult continuation
        ]
        
        for marker in stop_markers:
            match = re.search(marker, text, re.IGNORECASE)
            if match:
                text = text[:match.start()]
                break
        
        # Also strip trailing team references
        # Sometimes they appear at the very end without being caught by stop markers
        trailing_patterns = [
            r"\s*ANGEL\s+OF\s+DEATH\s*$",
            r"\s*ASTARTES\s*$",
            rf"\s*{re.escape(team_upper)}\s*$",
        ]
        
        for pattern in trailing_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        
        # Final cleanup
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        
        return text
    
    def _clean_faction_rule_name(name: str) -> str:
        """Clean up extracted faction rule name by removing extra text."""
        # If name contains newline, take only first line
        if "\n" in name:
            name = name.split("\n")[0]
        
        # Remove any leading/trailing whitespace
        name = name.strip()
        
        return name
    
    config = _load_team_config()
    team_data = config.get("teams", {}).get(team, {})
    faction_rule_cfg = team_data.get("faction_rule")
    if not faction_rule_cfg:
        return None

    pdf_path = PROCESSED_DIR / team / f"{team}-faction-rules.pdf"
    if not pdf_path.exists():
        log.debug("%s: no faction-rules PDF, skipping faction rule extraction", team)
        return None

    doc = fitz.open(pdf_path)
    all_text = ""
    for page in doc:
        all_text += page.get_text() + "\n"
    doc.close()

    # Build lookup of config option names for matching
    cfg_options = faction_rule_cfg.get("options", [])
    cfg_names = {opt["name"].upper(): opt["name"] for opt in cfg_options}
    rule_name = faction_rule_cfg["name"]

    # Strategy 1: Try numbered entries first (e.g. "1. AGGRESSIVE\n..." or "1. Deformed Wings\n...")
    # Match title case or ALL CAPS names
    pattern = r"(\d+)\.\s+([A-Z][\w\s]+)\n(.*?)(?=\n\d+\.\s+[A-Z]|\nCONTINUES|\Z)"
    matches = re.findall(pattern, all_text, re.DOTALL)

    options = []
    if matches:
        for _num, raw_name, raw_text in matches:
            name_upper = raw_name.strip()
            name = cfg_names.get(name_upper, name_upper.title())
            name = _clean_faction_rule_name(name)
            text = _clean_faction_rule_text(raw_text.strip(), team, rule_name)
            options.append({"name": name, "text": text})
    else:
        # Strategy 2: Search for each config option name in the faction rule pages
        # PDF format: "LEGIONARY\nFACTION RULE\n...\n<NAME>\n<Sub-rule>\n<Description>\n"
        for opt in cfg_options:
            opt_name = opt["name"]
            # Match option name (case-insensitive) on its own line, then capture
            # the sub-rule name and description until next page header or EOF
            name_pattern = r"(?im)^" + re.escape(opt_name) + r"\n(.*?)(?=\nLEGIONARY\n|\Z)"
            m = re.search(name_pattern, all_text, re.DOTALL)
            if m:
                text = _clean_faction_rule_text(m.group(1).strip(), team, rule_name)
                options.append({"name": opt_name, "text": text})

    if not options:
        log.warning("%s: no faction rule options found in PDF", team)
        return None

    log.info("  %-35s %d faction rule options extracted", team, len(options))

    return {
        "name": faction_rule_cfg["name"],
        "select": faction_rule_cfg.get("select", 2),
        "options": options,
    }


# ── Per-team extraction ──

def extract_team(team: str, force: bool = False) -> dict | None:
    """Extract statlines from a team's datacards PDF.
    
    Returns roster dict or None if nothing to do.
    """
    pdf_path = PROCESSED_DIR / team / f"{team}-datacards.pdf"
    faction = _get_team_faction(team)
    output_path = OUTPUT_V2_DIR / faction / team / "statlines" / "roster.json"

    if not pdf_path.exists():
        log.debug("%s: no datacards PDF, skipping", team)
        return None

    # Skip if output is newer than input (unless forced)
    if output_path.exists() and not force:
        if output_path.stat().st_mtime > pdf_path.stat().st_mtime:
            log.debug("%s: roster.json up to date, skipping", team)
            return None

    doc = fitz.open(pdf_path)
    page_count = len(doc)

    # Phase 1: Extract front pages (operatives)
    operatives = []
    front_indices = []
    for i in range(page_count):
        page = doc[i]
        if _is_front_page(page):
            op = _extract_operative_from_page(page, i, pdf_path.name)
            if op:
                operatives.append(op)
                front_indices.append(i)

    # Phase 2: Process back pages — merge rules into the preceding operative
    for i in range(page_count):
        if i in front_indices:
            continue
        page = doc[i]
        rules = _extract_backpage_rules(page)
        if not rules:
            continue

        # Find the preceding front page's operative
        prev_front_idx = None
        for fi in reversed(front_indices):
            if fi < i:
                prev_front_idx = fi
                break
        if prev_front_idx is None:
            continue

        # Find the operative that came from that front page
        op_idx = front_indices.index(prev_front_idx)
        if op_idx < len(operatives):
            op = operatives[op_idx]
            back_pas = [r for r in rules if '(' not in r["name"] or 'AP)' not in r["name"]]
            back_act = [r for r in rules if '(' in r["name"] and 'AP)' in r["name"]]
            if "passive_abilities" not in op:
                op["passive_abilities"] = []
            if "unique_actions" not in op:
                op["unique_actions"] = []
            op["passive_abilities"].extend(back_pas)
            op["unique_actions"].extend(back_act)

    doc.close()

    if not operatives:
        log.warning("%s: no operatives extracted from %d pages", team, page_count)
        return None

    # Phase 3: Parse operative selection card for weapon loadout options
    roster_names = [op["name"] for op in operatives]
    selection, exclusive_sets = _parse_operative_selection(team, roster_names)

    # Phase 4: Extract faction rule options from faction-rules PDF (if configured)
    faction_rule = _extract_faction_rules(team)

    roster = {
        "team": team,
        "generated": datetime.now(timezone.utc).isoformat(),
        "selection": selection,
        "exclusive_sets": exclusive_sets,
        "operative_count": len(operatives),
        "operatives": operatives,
    }
    if faction_rule:
        roster["faction_rule"] = faction_rule

    roster_json = json.dumps(roster, indent=2, ensure_ascii=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(roster_json, encoding="utf-8")

    # Compat copy to output/{team}/statlines/ for embed_datacard_stats.py
    compat_path = OUTPUT_DIR / team / "statlines" / "roster.json"
    compat_path.parent.mkdir(parents=True, exist_ok=True)
    compat_path.write_text(roster_json, encoding="utf-8")

    sel_count = sum(1 for v in selection.values() if v)
    log.info("  %-35s %2d operatives  (%d with loadout options)", team, len(operatives), sel_count)
    return roster


# ── Team discovery ──

def discover_teams() -> list[str]:
    """Find all teams with a datacards PDF in processed/."""
    teams = []
    if not PROCESSED_DIR.exists():
        return teams
    for d in sorted(PROCESSED_DIR.iterdir()):
        if d.is_dir() and (d / f"{d.name}-datacards.pdf").exists():
            teams.append(d.name)
    return teams


# ── CLI ──

def main():
    parser = argparse.ArgumentParser(description="Extract statlines from datacards PDFs")
    parser.add_argument("--teams", help="Comma-separated team list (default: all)")
    parser.add_argument("--force", action="store_true", help="Regenerate even if up to date")
    args = parser.parse_args()

    if args.teams:
        teams = [t.strip() for t in args.teams.split(",")]
    else:
        teams = discover_teams()

    log.info("Extracting statlines for %d teams", len(teams))

    extracted = 0
    total_ops = 0
    for team in teams:
        result = extract_team(team, force=args.force)
        if result:
            extracted += 1
            total_ops += result["operative_count"]

    log.info("")
    log.info("Done: %d teams, %d operatives", extracted, total_ops)


if __name__ == "__main__":
    main()
