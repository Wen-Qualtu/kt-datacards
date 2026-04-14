"""
Extract operative statlines from datacards PDFs (kt-app pipeline).

Reads processed/{team}/{team}-datacards.pdf (multi-page PDF, one page per card)
and extracts statlines (APL, Movement, Save, Wounds), weapons, keywords, and 
rules/abilities using coordinate-based region extraction from PyMuPDF.

Front pages (starting with "NAME" header) contain operative stats.
Back pages contain additional rules/abilities.

Output: output/{team}/statlines/roster.json

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

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "processed"
OUTPUT_DIR = ROOT / "output"

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


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
    all_numbers = re.findall(r'\d+', stats_text)
    for num_str in all_numbers:
        num = int(num_str)
        if stats.get("apl") and num == stats["apl"]:
            continue
        if stats.get("movement") and num_str == stats["movement"].rstrip("″\"'"):
            continue
        if stats.get("save") and num_str == stats["save"].rstrip("+"):
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
            if sr and sr != '-':
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
                if sr and sr != '-':
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
                    rules.append({"name": ua_name, "description": ua_desc.strip()})
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
                        rules.append({"name": full_name, "description": ua_desc.strip()})
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


# ── Per-team extraction ──

def extract_team(team: str, force: bool = False) -> dict | None:
    """Extract statlines from a team's datacards PDF.
    
    Returns roster dict or None if nothing to do.
    """
    pdf_path = PROCESSED_DIR / team / f"{team}-datacards.pdf"
    output_path = OUTPUT_DIR / team / "statlines" / "roster.json"

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

    roster = {
        "team": team,
        "generated": datetime.now(timezone.utc).isoformat(),
        "operative_count": len(operatives),
        "operatives": operatives,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(roster, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("  %-35s %2d operatives", team, len(operatives))
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
