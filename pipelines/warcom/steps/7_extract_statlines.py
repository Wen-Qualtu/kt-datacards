"""
Step 7: Extract Statlines from Datacards

Extracts operative and weapon statistics from datacard PDFs to generate
BattleScribe-compatible roster JSON files for TTS integration.

Input:  layers/warcom/extracted/{team}/cards/*.pdf (landscape only)
Output: output/{team}/statlines/roster.json

Only processes landscape-oriented PDFs (datacards with stats).
Portrait cards (equipment, ploys, etc.) are skipped.

Uses change detection to only regenerate when card content changes.
"""

import argparse
import json
import hashlib
import logging
import re
import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ===================================================================
# DATA MODELS (BattleScribe-compatible format)
# ===================================================================

@dataclass
class WeaponProfile:
    """Weapon profile with combat stats"""
    name: str
    attacks: str  # e.g., "4", "5"
    skill: str    # e.g., "2+", "3+"
    damage: str   # e.g., "3/4", "2/3"
    special_rules: str = ""  # e.g., "Relentless", "Lethal 5+"
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "A": self.attacks,
            "BS/WS": self.skill,
            "D": self.damage,
            "SR": self.special_rules
        }


@dataclass
class OperativeProfile:
    """Operative profile with characteristics"""
    name: str
    movement: str  # e.g., "6″", "3□"
    apl: str       # e.g., "2", "3"
    group_activation: str = "1"
    defense: str = "3"
    save: str = ""     # e.g., "3+", "4+"
    wounds: str = ""   # e.g., "8", "12"
    weapons: List[WeaponProfile] = None
    
    def __post_init__(self):
        if self.weapons is None:
            self.weapons = []
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "M": self.movement,
            "APL": self.apl,
            "GA": self.group_activation,
            "DF": self.defense,
            "SV": self.save,
            "W": self.wounds,
            "weapons": [w.to_dict() for w in self.weapons]
        }


@dataclass
class TeamRoster:
    """Team roster containing all operative profiles"""
    team_name: str
    operatives: List[OperativeProfile]
    last_updated: str = ""
    
    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> dict:
        return {
            "team": self.team_name,
            "last_updated": self.last_updated,
            "operatives": [op.to_dict() for op in self.operatives]
        }


# ===================================================================
# CHANGE DETECTION (integrated with existing system)
# ===================================================================

class StatlineChangeDetector:
    """Detects changes in statline extractions using content hashing"""
    
    def __init__(self, metadata_file: Path):
        self.metadata_file = metadata_file
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load existing metadata from TTS metadata file"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_metadata(self):
        """Save metadata back to file"""
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
    
    def compute_hash(self, content: Any) -> str:
        """Compute SHA-256 hash of content"""
        if isinstance(content, dict):
            content_str = json.dumps(content, sort_keys=True, ensure_ascii=False)
        elif isinstance(content, str):
            content_str = content
        else:
            content_str = str(content)
        
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()
    
    def has_changed(self, team_name: str, roster_data: dict) -> Tuple[bool, Optional[str]]:
        """Check if roster data has changed since last generation"""
        current_hash = self.compute_hash(roster_data)
        
        # Navigate to statlines metadata
        if team_name not in self.metadata:
            return True, None
        
        team_meta = self.metadata[team_name]
        if "statlines" not in team_meta:
            return True, None
        
        statlines_meta = team_meta["statlines"]
        stored_hash = statlines_meta.get("content_hash")
        old_timestamp = statlines_meta.get("last_modified")
        
        return current_hash != stored_hash, old_timestamp
    
    def update_metadata(self, team_name: str, roster_data: dict) -> str:
        """Update metadata for team roster"""
        timestamp = datetime.now(timezone.utc).isoformat()
        content_hash = self.compute_hash(roster_data)
        
        # Ensure team entry exists
        if team_name not in self.metadata:
            self.metadata[team_name] = {}
        
        # Update statlines metadata
        self.metadata[team_name]["statlines"] = {
            "guid": "",
            "url": f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/{team_name}/statlines/roster.json",
            "component_type": "statlines",
            "content_hash": content_hash,
            "last_modified": timestamp
        }
        
        return timestamp


# ===================================================================
# PDF TEXT EXTRACTION
# ===================================================================

def is_landscape(pdf_path: Path) -> bool:
    """Check if PDF is landscape orientation (datacards only)"""
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            return False
        
        page = doc[0]
        width = page.rect.width
        height = page.rect.height
        doc.close()
        
        return width > height
    except Exception as e:
        logger.warning(f"Error checking orientation of {pdf_path.name}: {e}")
        return False


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract all text from PDF"""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        logger.error(f"Error extracting text from {pdf_path.name}: {e}")
        return ""


# ===================================================================
# STAT EXTRACTION (regex patterns)
# ===================================================================

def extract_operative_name(pdf_path: Path, text: str) -> str:
    """Extract operative name from card text"""
    # Operative name is usually in all caps near the bottom, before faction tags
    # Example: "SPACE MARINE CAPTAIN"
    # Pattern: Look for all-caps words before common faction tags
    
    lines = text.split('\n')
    
    # Table headers and stat labels to exclude
    excluded_keywords = [
        'IMPERIUM', 'CHAOS', 'XENOS', 'APL', 'WOUNDS', 'SAVE', 'MOVE',
        'NAME', 'ATK', 'HIT', 'DMG', 'WR', 'HIT DMG', 'BS/WS',
        'RULES', 'CONTINUE', 'OTHER', 'SIDE'
    ]
    
    # Look for a line with 2-5 all-caps words (operative name)
    # It should be before faction tags and after abilities
    # Usually within last 15 lines
    for i in range(len(lines) - 1, max(0, len(lines) - 20), -1):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            continue
        
        words = line.split()
        
        # Skip single words and table headers
        if len(words) < 2 or len(words) > 5:
            continue
        
        # Check if line is excluded
        if any(keyword in line for keyword in excluded_keywords):
            continue
        
        # Check if this is an all-caps line
        if all(word.isupper() or word.replace('-', '').isupper() for word in words):
            # Additional validation: operative names usually contain real words
            # not just numbers or special chars
            if all(any(c.isalpha() for c in word) for word in words):
                return line.title()
    
    # Fallback: use cleaned filename
    name = pdf_path.stem
    if '_' in name:
        parts = name.split('_')
        # Remove landscape/portrait suffix and page numbers
        name_parts = [p for p in parts if not any(x in p.lower() for x in ['page', 'card', 'landscape', 'portrait'])]
        if name_parts:
            # Remove team prefix
            name = ' '.join(name_parts[1:] if len(name_parts) > 1 else name_parts).title()
    
    return name


def extract_stats(text: str) -> Dict[str, str]:
    """Extract operative stats from text using regex patterns
    
    Stats are laid out vertically at bottom of card:
    3        <- APL value
    APL      <- APL label
    WOUNDS   <- WOUNDS label  
    SAVE     <- SAVE label
    MOVE     <- MOVE label
    6"       <- MOVE value
    3+       <- SAVE value
    15       <- WOUNDS value
    """
    stats = {
        'movement': '',
        'apl': '',
        'save': '',
        'wounds': ''
    }
    
    lines = text.split('\n')
    
    # Find stats section (usually last 10-15 lines)
    stats_section = '\n'.join(lines[-15:])
    
    # APL: Look for single digit (2 or 3) before "APL" line
    apl_pattern = r'(\d)\s*\n\s*APL'
    apl_match = re.search(apl_pattern, stats_section)
    if apl_match:
        stats['apl'] = apl_match.group(1)
    
    # MOVE: Look for number with " or □ after "MOVE" line  
    move_pattern = r'MOVE[:\s]*\n\s*(\d+[″\"]?)'
    move_match = re.search(move_pattern, stats_section)
    if move_match:
        stats['movement'] = move_match.group(1).replace('"', '″')
    
    # SAVE: Look for number+ after "SAVE" line
    save_pattern = r'SAVE[:\s]*\n.*?\n.*?(\d+\+)'
    save_match = re.search(save_pattern, stats_section, re.DOTALL)
    if save_match:
        stats['save'] = save_match.group(1)
    
    # WOUNDS: Look for number after "WOUNDS" line
    wounds_pattern = r'WOUNDS[:\s]*\n.*?\n.*?\n.*?(\d+)'
    wounds_match = re.search(wounds_pattern, stats_section, re.DOTALL)
    if wounds_match:
        stats['wounds'] = wounds_match.group(1)
    
    return stats


def extract_weapons(text: str) -> List[WeaponProfile]:
    """Extract weapon profiles from text
    
    Weapons table format:
    NAME
    ATK
    HIT DMG
    WR
    
    Plasma pistol (standard)
    4
    3+
    3/5
    Range 8 inch, Piercing 1
    """
    weapons = []
    
    lines = text.split('\n')
    
    # Find weapon table section (before abilities section)
    # Usually starts after "WR" header
    weapon_section_start = -1
    weapon_section_end = -1
    
    for i, line in enumerate(lines):
        line = line.strip()
        if line == 'WR' and i > 0:
            weapon_section_start = i + 1
        # Abilities usually start with long text blocks or all-caps keywords
        if weapon_section_start > 0 and (
            len(line) > 80 or 
            (line and line[0].isupper() and ':' in line and len(line) > 40)
        ):
            weapon_section_end = i
            break
    
    if weapon_section_start < 0:
        return weapons
    
    if weapon_section_end < 0:
        weapon_section_end = len(lines) - 10  # Stop before stats section
    
    # Parse weapons (groups of 4-5 lines: name, ATK, HIT, DMG, [special rules])
    i = weapon_section_start
    while i < weapon_section_end:
        line = lines[i].strip()
        
        # Skip empty lines and table headers
        if not line or line in ['NAME', 'ATK', 'HIT', 'DMG', 'WR', 'HIT DMG']:
            i += 1
            continue
        
        # This should be weapon name
        weapon_name = line
        
        # Skip if it looks like a header or stat
        if weapon_name.isupper() and len(weapon_name.split()) <= 2:
            i += 1
            continue
        
        # Look ahead for ATK, HIT, DMG values
        if i + 3 < weapon_section_end:
            atk = lines[i + 1].strip()
            hit = lines[i + 2].strip()
            dmg = lines[i + 3].strip()
            
            # Validate pattern: ATK should be a number, HIT should be number+, DMG should be number/number
            if (atk.isdigit() and 
                re.match(r'\d+\+', hit) and 
                re.match(r'\d+/\d+', dmg)):
                
                # Get special rules if present
                special_rules = ""
                if i + 4 < weapon_section_end:
                    special_line = lines[i + 4].strip()
                    # Special rules line is usually not empty, not a number, and not next weapon name
                    if (special_line and 
                        not special_line.isdigit() and 
                        not re.match(r'\d+\+', special_line)):
                        special_rules = special_line
                        i += 1  # Advance past special rules
                
                weapons.append(WeaponProfile(
                    name=weapon_name,
                    attacks=atk,
                    skill=hit,
                    damage=dmg,
                    special_rules=special_rules
                ))
                
                i += 4  # Move past this weapon (name + 3 stat lines)
                continue
        
        i += 1
    # This is a simplified pattern - will need refinement based on actual card layout
    weapon_pattern = r'([A-Za-z\s\-]+?)\s+(\d+)\s+(\d+\+)\s+([\d/]+)(?:\s+([A-Za-z\s,\+\-]+))?'
    
    matches = re.finditer(weapon_pattern, text)
    for match in matches:
        name = match.group(1).strip()
        attacks = match.group(2)
        skill = match.group(3)
        damage = match.group(4)
        special = match.group(5).strip() if match.group(5) else ""
        
        # Filter out false positives (too short names, etc.)
        if len(name) > 2 and not name.isupper():
            weapons.append(WeaponProfile(
                name=name,
                attacks=attacks,
                skill=skill,
                damage=damage,
                special_rules=special
            ))
    
    return weapons


# ===================================================================
# MAIN PROCESSING
# ===================================================================

def process_team_datacards(team_name: str, extracted_dir: Path) -> Optional[TeamRoster]:
    """Process all datacards for a team and extract statlines"""
    team_dir = extracted_dir / team_name / "cards"
    
    if not team_dir.exists():
        logger.warning(f"No cards directory for {team_name}")
        return None
    
    # Find all landscape PDFs (datacards)
    datacard_pdfs = [
        pdf for pdf in team_dir.glob("*.pdf")
        if is_landscape(pdf)
    ]
    
    if not datacard_pdfs:
        logger.warning(f"No landscape datacards found for {team_name}")
        return None
    
    logger.info(f"Processing {len(datacard_pdfs)} datacards for {team_name}")
    
    operatives = []
    for pdf_path in sorted(datacard_pdfs):
        # Extract text
        text = extract_text_from_pdf(pdf_path)
        if not text:
            logger.warning(f"No text extracted from {pdf_path.name}")
            continue
        
        # Extract operative name
        op_name = extract_operative_name(pdf_path, text)
        
        # Extract stats
        stats = extract_stats(text)
        
        # Extract weapons
        weapons = extract_weapons(text)
        
        # Create operative profile
        operative = OperativeProfile(
            name=op_name,
            movement=stats.get('movement', ''),
            apl=stats.get('apl', '2'),
            save=stats.get('save', ''),
            wounds=stats.get('wounds', ''),
            weapons=weapons
        )
        
        operatives.append(operative)
        logger.debug(f"  Extracted: {op_name} - M:{stats.get('movement')} APL:{stats.get('apl')} W:{stats.get('wounds')}")
    
    if not operatives:
        logger.warning(f"No operatives extracted for {team_name}")
        return None
    
    return TeamRoster(team_name=team_name, operatives=operatives)


def save_roster(roster: TeamRoster, output_dir: Path, team_name: str):
    """Save roster to JSON file"""
    statlines_dir = output_dir / team_name / "statlines"
    statlines_dir.mkdir(parents=True, exist_ok=True)
    
    roster_file = statlines_dir / "roster.json"
    with open(roster_file, 'w', encoding='utf-8') as f:
        json.dump(roster.to_dict(), f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved roster to {roster_file}")


def run(
    extracted_dir: Path,
    output_dir: Path,
    metadata_file: Path,
    teams: Optional[List[str]] = None,
    force: bool = False
):
    """
    Main execution function
    
    Args:
        extracted_dir: Path to layers/warcom/extracted/
        output_dir: Path to output/
        metadata_file: Path to .tts-metadata.json
        teams: Optional list of specific teams to process
        force: Force regeneration even if unchanged
    """
    logger.info("=" * 60)
    logger.info("Statline Extraction - Step 7")
    logger.info("=" * 60)
    
    # Initialize change detector
    detector = StatlineChangeDetector(metadata_file)
    
    # Find teams to process
    if teams:
        team_dirs = [extracted_dir / team for team in teams if (extracted_dir / team).exists()]
    else:
        team_dirs = [d for d in extracted_dir.iterdir() if d.is_dir() and d.name != "_generic"]
    
    if not team_dirs:
        logger.warning("No teams found to process")
        return
    
    logger.info(f"Processing {len(team_dirs)} team(s)")
    
    updated_count = 0
    skipped_count = 0
    
    for team_dir in sorted(team_dirs):
        team_name = team_dir.name
        logger.info(f"\nProcessing {team_name}...")
        
        # Extract statlines
        roster = process_team_datacards(team_name, extracted_dir)
        
        if not roster:
            logger.warning(f"  Skipping {team_name} - no datacards extracted")
            continue
        
        # Check if changed
        roster_data = roster.to_dict()
        changed, old_timestamp = detector.has_changed(team_name, roster_data)
        
        if not changed and not force:
            logger.info(f"  No changes detected for {team_name} (last: {old_timestamp})")
            skipped_count += 1
            continue
        
        # Update metadata and save
        timestamp = detector.update_metadata(team_name, roster_data)
        roster.last_updated = timestamp
        
        save_roster(roster, output_dir, team_name)
        updated_count += 1
        logger.info(f"  ✓ Updated {team_name} ({len(roster.operatives)} operatives)")
    
    # Save metadata
    detector.save_metadata()
    
    logger.info("=" * 60)
    logger.info("Statline Extraction Complete")
    logger.info("=" * 60)
    logger.info(f"Teams processed: {len(team_dirs)}")
    logger.info(f"Teams updated: {updated_count}")
    logger.info(f"Teams skipped (unchanged): {skipped_count}")
    logger.info(f"Metadata: {metadata_file}")


def main():
    parser = argparse.ArgumentParser(description='Extract statlines from datacards')
    parser.add_argument('--teams', nargs='+', help='Specific teams to process (default: all)')
    parser.add_argument('--force', action='store_true', help='Force regeneration even if unchanged')
    parser.add_argument('--extracted-dir', type=Path, 
                       default=Path.cwd() / 'layers/warcom/extracted',
                       help='Path to extracted cards directory')
    parser.add_argument('--output-dir', type=Path,
                       default=Path.cwd() / 'output',
                       help='Path to output directory')
    parser.add_argument('--metadata-file', type=Path,
                       default=Path.cwd() / 'output/.tts-metadata.json',
                       help='Path to TTS metadata file')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: INFO)')
    
    args = parser.parse_args()
    
    logging.basicConfig(level=getattr(logging, args.log_level), format='%(levelname)s: %(message)s')
    
    run(
        extracted_dir=args.extracted_dir,
        output_dir=args.output_dir,
        metadata_file=args.metadata_file,
        teams=args.teams,
        force=args.force
    )


if __name__ == '__main__':
    main()
