"""
Step 7: Extract Statlines from Datacards

Extracts operative statistics and weapon profiles from datacard PDFs to generate
BattleScribe-compatible roster.json files for TTS integration.

Input:  layers/warcom/extracted/{team}/cards/*.pdf (landscape datacards only)
Output: output/{team}/statlines/roster.json

Usage:
    python pipelines/warcom/steps/7_extract_statlines.py
    python pipelines/warcom/steps/7_extract_statlines.py --teams battleclade kommandos
    python pipelines/warcom/steps/7_extract_statlines.py --force
"""

import argparse
import json
import logging
import re
import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF file."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        logger.error("Failed to extract text from %s: %s", pdf_path.name, e)
        return ""


def is_landscape(pdf_path: Path) -> bool:
    """Check if PDF is landscape orientation."""
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        rect = page.rect
        doc.close()
        return rect.width > rect.height
    except Exception:
        return False


def extract_operative_name(text: str) -> str:
    """Extract operative name from card text."""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Common non-name patterns to exclude
    exclude_patterns = [
        r'^APL$', r'^MOVE$', r'^SAVE$', r'^WOUNDS$',
        r'^NAME$', r'^ATK$', r'^HIT$', r'^DMG$', r'^WR$',
        r'^WEAPONS$', r'^ABILITIES$', r'^UNIQUE ACTIONS$',
        r'^\d+$', r'^\d+"$', r'^\d+\+$',
        r'RULES? CONTINUE',
        r'^HIT DMG$', r'^WEAPON$'
    ]
    
    for line in lines:
        # Skip short lines
        if len(line) < 3:
            continue
        
        # Skip lines matching exclusion patterns
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in exclude_patterns):
            continue
        
        # Operative names are typically in UPPERCASE and longer
        if line.isupper() and len(line) >= 5:
            # Clean up the name
            name = ' '.join(line.split())
            return name
    
    return "Unknown Operative"


def extract_stats(text: str) -> Dict[str, Any]:
    """Extract operative stats from card text."""
    stats = {
        "apl": None,
        "movement": None,
        "save": None,
        "wounds": None
    }
    
    # Extract APL (usually 2 or 3)
    apl_match = re.search(r'APL\s*(\d+)', text, re.IGNORECASE)
    if apl_match:
        stats["apl"] = int(apl_match.group(1))
    
    # Extract Movement (e.g., 6", 7")
    move_match = re.search(r'MOVE\s*(\d+)"?', text, re.IGNORECASE)
    if move_match:
        stats["movement"] = move_match.group(1) + '″'  # Use proper inch symbol
    
    # Extract Save (e.g., 3+, 4+)
    save_match = re.search(r'SAVE\s*(\d\+)', text, re.IGNORECASE)
    if save_match:
        stats["save"] = save_match.group(1)
    
    # Extract Wounds (e.g., 8, 12, 21)
    wounds_match = re.search(r'WOUNDS\s*(\d+)', text, re.IGNORECASE)
    if wounds_match:
        stats["wounds"] = int(wounds_match.group(1))
    
    return stats


def extract_weapons(text: str) -> List[Dict[str, str]]:
    """Extract weapon profiles from card text."""
    weapons = []
    
    # Find weapon table section (after WEAPONS header, before ABILITIES/etc)
    weapon_section_match = re.search(
        r'WEAPONS.*?(?=ABILITIES|UNIQUE ACTIONS|RULES CONTINUE|$)',
        text,
        re.IGNORECASE | re.DOTALL
    )
    
    if not weapon_section_match:
        return weapons
    
    weapon_section = weapon_section_match.group(0)
    lines = [line.strip() for line in weapon_section.split('\n') if line.strip()]
    
    # Skip header lines
    skip_patterns = [
        r'^WEAPONS?$', r'^NAME$', r'^ATK$', r'^HIT$', r'^DMG$', r'^WR$',
        r'^HIT DMG WR$', r'^NAME ATK HIT DMG WR$'
    ]
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Skip header patterns
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
            i += 1
            continue
        
        # Check if this looks like a weapon name (not just numbers/symbols)
        if re.match(r'^[A-Za-z]', line):
            # Try to extract weapon profile from this line and next few lines
            weapon = {"name": line}
            
            # Look for ATK (number)
            for j in range(i + 1, min(i + 5, len(lines))):
                if re.match(r'^\d+$', lines[j]):
                    weapon["attacks"] = lines[j]
                    break
            
            # Look for HIT (e.g., 2+, 3+)
            for j in range(i + 1, min(i + 5, len(lines))):
                if re.match(r'^\d\+$', lines[j]):
                    weapon["hit"] = lines[j]
                    break
            
            # Look for DMG (e.g., 3, 4/5)
            for j in range(i + 1, min(i + 5, len(lines))):
                if re.match(r'^\d+(/\d+)?$', lines[j]):
                    weapon["damage"] = lines[j]
                    break
            
            # Everything else might be special rules
            special_rules = []
            for j in range(i + 1, min(i + 8, len(lines))):
                test_line = lines[j]
                # Skip if it's already captured or looks like a stat
                if test_line in [weapon.get("attacks"), weapon.get("hit"), weapon.get("damage")]:
                    continue
                if re.match(r'^(\d+|^\d\+|\d+/\d+)$', test_line):
                    continue
                # If it's text, might be special rules
                if re.match(r'^[A-Za-z]', test_line):
                    special_rules.append(test_line)
            
            if special_rules:
                weapon["special_rules"] = ", ".join(special_rules[:3])  # Limit to first 3
            
            weapons.append(weapon)
        
        i += 1
    
    return weapons


def extract_statlines_from_team(team_dir: Path, output_dir: Path, force: bool = False) -> Optional[Dict]:
    """Extract statlines from all datacards for a team."""
    team_name = team_dir.name
    cards_dir = team_dir / "cards"
    
    if not cards_dir.exists():
        logger.warning("No cards directory found for %s", team_name)
        return None
    
    # Find all PDF files
    pdf_files = list(cards_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning("No PDF files found for %s", team_name)
        return None
    
    # Filter landscape PDFs (datacards)
    datacard_pdfs = [pdf for pdf in pdf_files if is_landscape(pdf)]
    
    if not datacard_pdfs:
        logger.warning("No landscape datacards found for %s", team_name)
        return None
    
    logger.info("Processing %s: %d datacards", team_name, len(datacard_pdfs))
    
    # Extract from each datacard
    operatives = []
    for pdf_path in datacard_pdfs:
        text = extract_text_from_pdf(pdf_path)
        if not text:
            continue
        
        name = extract_operative_name(text)
        stats = extract_stats(text)
        weapons = extract_weapons(text)
        
        operative = {
            "name": name,
            "source_file": pdf_path.name,
            **stats
        }
        
        if weapons:
            operative["weapons"] = weapons
        
        operatives.append(operative)
    
    if not operatives:
        logger.warning("No operatives extracted for %s", team_name)
        return None
    
    # Create output structure
    roster = {
        "team": team_name,
        "generated": datetime.now(timezone.utc).isoformat(),
        "operatives": operatives
    }
    
    # Save to output directory
    statlines_dir = output_dir / team_name / "statlines"
    statlines_dir.mkdir(parents=True, exist_ok=True)
    
    roster_file = statlines_dir / "roster.json"
    with open(roster_file, 'w', encoding='utf-8') as f:
        json.dump(roster, f, indent=2, ensure_ascii=False)
    
    logger.info("✓ %s: Extracted %d operatives", team_name, len(operatives))
    return roster


def run(
    extracted_dir: Path,
    output_dir: Path,
    teams: Optional[List[str]] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Run statline extraction for all teams.
    
    Args:
        extracted_dir: Directory containing extracted cards
        output_dir: Directory for output files
        teams: Optional list of specific teams to process
        force: Force regeneration even if unchanged
    
    Returns:
        Dictionary with processing results
    """
    logger.info("=" * 70)
    logger.info("Step 7: Extract Statlines from Datacards")
    logger.info("=" * 70)
    logger.info("Extracted dir: %s", extracted_dir)
    logger.info("Output dir: %s", output_dir)
    
    # Find all team directories
    if teams:
        team_dirs = [extracted_dir / team for team in teams if (extracted_dir / team).exists()]
    else:
        team_dirs = [d for d in extracted_dir.iterdir() if d.is_dir()]
    
    if not team_dirs:
        logger.warning("No teams found to process")
        return {"success": False, "teams_processed": 0}
    
    logger.info("Teams to process: %d", len(team_dirs))
    logger.info("=" * 70)
    
    # Process each team
    processed = 0
    failed = 0
    
    for team_dir in sorted(team_dirs):
        try:
            result = extract_statlines_from_team(team_dir, output_dir, force)
            if result:
                processed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error("Error processing %s: %s", team_dir.name, e)
            failed += 1
    
    # Summary
    logger.info("=" * 70)
    logger.info("Extraction Complete")
    logger.info("=" * 70)
    logger.info("Teams processed: %d", processed)
    logger.info("Teams failed: %d", failed)
    logger.info("Output: %s", output_dir)
    
    return {
        "success": True,
        "teams_processed": processed,
        "teams_failed": failed
    }


def main():
    parser = argparse.ArgumentParser(
        description='Extract statlines from datacards'
    )
    parser.add_argument(
        '--extracted',
        type=Path,
        default=Path('layers/warcom/extracted'),
        help='Directory containing extracted cards (default: layers/warcom/extracted)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('output'),
        help='Output directory (default: output)'
    )
    parser.add_argument(
        '--teams',
        nargs='+',
        help='Specific teams to process (default: all)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force regeneration even if unchanged'
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(levelname)s: %(message)s'
    )
    
    # Run extraction
    run(
        extracted_dir=args.extracted,
        output_dir=args.output,
        teams=args.teams,
        force=args.force
    )


if __name__ == '__main__':
    main()
