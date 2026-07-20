"""
Step 1: Process PDFs

Identifies and organizes raw PDFs from input/, then splits them into single-page PDFs.

Input:  input/*.pdf (raw PDFs, searched recursively)
Output: layers/kt-app/processed/{team}/{team}-{type}.pdf (organized PDFs)
        layers/kt-app/extracted/{team}/cards/{team}-{type}-page_N.pdf (single-page PDFs)
        layers/kt-app/metadata.json (hash tracking)

Architecture:
- Self-contained module with no external dependencies
- Hash-based change detection for incremental updates
- Single-page PDF extraction for easier downstream processing

Usage:
    python pipelines/kt-app/steps/1_process_pdfs.py
    python pipelines/kt-app/steps/1_process_pdfs.py --teams kasrkin,blooded
    python pipelines/kt-app/steps/1_process_pdfs.py --force
"""

import argparse
import json
import hashlib
import logging
import re
import shutil
import yaml
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

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


# ===================================================================
# MODELS
# ===================================================================

class CardType(Enum):
    """PDF card types"""
    DATACARDS = "datacards"
    FACTION_RULES = "faction-rules"
    TOKEN_GUIDE = "token-guide"
    OPERATIVES = "operatives-selection"
    EQUIPMENT = "equipment"
    STRATEGY_PLOYS = "strategy-ploys"
    FIREFIGHT_PLOYS = "firefight-ploys"


class Team:
    """Team representation"""
    def __init__(self, name: str, aliases: List[str] = None, faction: str = None, metadata: Dict = None):
        self.name = name
        self.aliases = aliases or []
        self.faction = faction
        self.metadata = metadata or {}
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize team name to slug format"""
        # Convert to lowercase
        normalized = name.lower()
        # Replace spaces and underscores with hyphens
        normalized = re.sub(r'[\s_]+', '-', normalized)
        # Remove non-alphanumeric except hyphens
        normalized = re.sub(r'[^a-z0-9\-]', '', normalized)
        # Remove multiple consecutive hyphens
        normalized = re.sub(r'-+', '-', normalized)
        # Strip leading/trailing hyphens
        normalized = normalized.strip('-')
        return normalized
    
    def matches(self, text: str) -> bool:
        """Check if text matches this team"""
        normalized = self.normalize_name(text)
        if normalized == self.name:
            return True
        for alias in self.aliases:
            if self.normalize_name(alias) == normalized:
                return True
        return False


# ===================================================================
# METADATA & CHANGE DETECTION
# ===================================================================

class MetadataManager:
    """Manages pipeline metadata with hash-based change detection"""
    
    def __init__(self, metadata_file: Path):
        self.metadata_file = metadata_file
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load existing metadata"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "pipeline_version": "2.0",
            "last_full_run": None,
            "teams": {}
        }
    
    def save_metadata(self):
        """Save metadata to file"""
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
    
    def compute_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def has_changed(self, team: str, step: str, file_key: str, file_path: Path) -> bool:
        """Check if file has changed since last run"""
        if team not in self.metadata["teams"]:
            return True
        if "steps" not in self.metadata["teams"][team]:
            return True
        if step not in self.metadata["teams"][team]["steps"]:
            return True
        if "outputs" not in self.metadata["teams"][team]["steps"][step]:
            return True
        if file_key not in self.metadata["teams"][team]["steps"][step]["outputs"]:
            return True
        
        stored_hash = self.metadata["teams"][team]["steps"][step]["outputs"][file_key].get("hash")
        if not stored_hash:
            return True
        
        current_hash = self.compute_hash(file_path)
        return current_hash != stored_hash
    
    def update_file(self, team: str, step: str, file_key: str, file_path: Path):
        """Update metadata for a file"""
        if team not in self.metadata["teams"]:
            self.metadata["teams"][team] = {"steps": {}}
        if "steps" not in self.metadata["teams"][team]:
            self.metadata["teams"][team]["steps"] = {}
        if step not in self.metadata["teams"][team]["steps"]:
            self.metadata["teams"][team]["steps"][step] = {"outputs": {}}
        if "outputs" not in self.metadata["teams"][team]["steps"][step]:
            self.metadata["teams"][team]["steps"][step]["outputs"] = {}
        
        file_hash = self.compute_hash(file_path)
        timestamp = datetime.now(timezone.utc).isoformat()
        
        self.metadata["teams"][team]["steps"][step]["outputs"][file_key] = {
            "path": str(file_path),
            "hash": file_hash,
            "modified": timestamp
        }
    
    def mark_step_complete(self, team: str, step: str):
        """Mark step as completed"""
        if team not in self.metadata["teams"]:
            self.metadata["teams"][team] = {"steps": {}}
        if "steps" not in self.metadata["teams"][team]:
            self.metadata["teams"][team]["steps"] = {}
        if step not in self.metadata["teams"][team]["steps"]:
            self.metadata["teams"][team]["steps"][step] = {}
        
        self.metadata["teams"][team]["steps"][step]["completed"] = datetime.now(timezone.utc).isoformat()


# ===================================================================
# TEAM IDENTIFICATION
# ===================================================================

class TeamIdentifier:
    """Identifies teams from config"""
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.teams: Dict[str, Team] = {}
        self._load_teams()
    
    def _load_teams(self):
        """Load teams from config"""
        if not self.config_path.exists():
            logger.warning(f"Config not found: {self.config_path}")
            return
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            teams_config = config.get('teams', {})
            
            for team_key, team_data in teams_config.items():
                team_key_norm = Team.normalize_name(team_key)
                team = Team(
                    name=team_key_norm,
                    aliases=team_data.get('aliases', []),
                    faction=team_data.get('faction'),
                    metadata=team_data
                )
                self.teams[team_key_norm] = team
        
        logger.info(f"Loaded {len(self.teams)} teams from config")
    
    def identify_team(self, text: str) -> Optional[Team]:
        """Identify team from text"""
        if not text:
            return None
        
        normalized = Team.normalize_name(text)
        
        # Direct match
        if normalized in self.teams:
            return self.teams[normalized]
        
        # Alias match
        for team in self.teams.values():
            if team.matches(text):
                return team
        
        logger.error(f"Team '{text}' (normalized: '{normalized}') not found in config")
        return None
    
    def get_all_teams(self) -> List[Team]:
        """Get all teams"""
        return list(self.teams.values())


# ===================================================================
# PDF PROCESSING
# ===================================================================

class PDFProcessor:
    """Processes PDFs: identification and splitting"""
    
    def __init__(self, team_identifier: TeamIdentifier):
        self.team_identifier = team_identifier
    
    def identify_pdf(self, pdf_path: Path) -> Tuple[Optional[Team], Optional[CardType]]:
        """
        Identify team and card type from PDF content.
        
        IMPORTANT: Uses content analysis only, NOT filename.
        Filename may optionally be used for verification in debug mode.
        """
        try:
            # Open PDF and analyze content
            pdf = fitz.open(pdf_path)
            page = pdf[0]
            
            # Identify card type from content
            card_type = self._identify_card_type(page)
            
            # Identify team name from content
            team_name = self._identify_team_name(page, card_type)
            
            pdf.close()
            
            if not team_name or not card_type:
                logger.warning(f"Could not identify {pdf_path.name}: team={team_name}, type={card_type}")
                return None, None
            
            # Resolve team from content
            team = self.team_identifier.identify_team(team_name)
            if not team:
                logger.error(f"Team '{team_name}' not in config for {pdf_path.name}")
                return None, None
            
            # Optional: Verify against filename in debug mode (development only)
            if logger.level <= logging.DEBUG:
                filename = pdf_path.stem.lower()
                team_slug = team.name.lower()
                type_slug = card_type.value.lower()
                if team_slug in filename and type_slug in filename:
                    logger.debug(f"Filename verification: {pdf_path.name} matches {team.name}/{card_type.value}")
                elif team_slug in filename or type_slug in filename:
                    logger.debug(f"Partial filename match: {pdf_path.name} → {team.name}/{card_type.value}")
            
            return team, card_type
        
        except Exception as e:
            logger.error(f"Error identifying {pdf_path}: {e}")
            return None, None
    
    def _identify_card_type(self, page) -> Optional[CardType]:
        """Identify card type from page content"""
        all_text = page.get_text()
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
        
        # Check for datacard indicators
        stat_keywords = ['APL', 'WS', 'BS', 'STR', 'DF', 'GA', 'SV', 'WOUNDS', 'SAVE', 'MOVE']
        stats_found = []
        for line in lines[-15:]:
            line_upper = line.upper().strip()
            if line_upper in stat_keywords:
                stats_found.append(line_upper)
            else:
                for keyword in ['APL', 'WS', 'BS', 'STR', 'DF', 'GA', 'SV']:
                    if f' {keyword} ' in f' {line_upper} ' or f' {keyword}:' in f' {line_upper} ':
                        stats_found.append(keyword)
            if 'RULES CONTINUE' in line_upper:
                return CardType.DATACARDS
        
        if len(set(stats_found)) >= 2:
            return CardType.DATACARDS
        
        # Check headers
        text_dict = page.get_text("dict")
        text_by_size = []
        for block in text_dict["blocks"]:
            if block["type"] == 0:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        size = span["size"]
                        if text and len(text) > 3:
                            text_by_size.append((size, text.upper()))
        
        text_by_size.sort(reverse=True, key=lambda x: x[0])
        
        for size, text in text_by_size[:30]:
            text_lower = text.lower()
            if 'operatives' == text_lower.strip():
                return CardType.OPERATIVES
            elif 'faction equipment' in text_lower or 'equipment' == text_lower.strip():
                return CardType.EQUIPMENT
            elif 'strategy ploy' in text_lower or 'strategic ploy' in text_lower:
                return CardType.STRATEGY_PLOYS
            elif 'firefight ploy' in text_lower:
                return CardType.FIREFIGHT_PLOYS
            # Check for token guide BEFORE faction rules (more specific pattern)
            elif 'marker/token guide' in text_lower:
                return CardType.TOKEN_GUIDE
            elif 'faction rule' in text_lower:
                return CardType.FACTION_RULES
        
        return None
    
    def _identify_team_name(self, page, card_type: Optional[CardType]) -> Optional[str]:
        """
        Identify team name from page content.
        
        Logic based on card type and orientation:
        - Datacards (landscape): Team name is first part of keyword line at bottom
        - Other types (portrait): Team name in top lines
        """
        # Get orientation
        rect = page.rect
        is_landscape = rect.width > rect.height
        
        # Get all text
        all_text = page.get_text()
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
        
        # DATACARDS (landscape operative cards): Team name in keyword line at bottom
        if card_type == CardType.DATACARDS and is_landscape:
            # Look in bottom portion for keyword line (format: "TEAM, FACTION, SUBFACTION, ROLE, ...")
            for line in lines[-30:]:  # Check last 30 lines
                # Skip stat keywords
                if line.upper() in ['APL', 'WOUNDS', 'SAVE', 'MOVE', 'HIT', 'DMG', 'WR', 'ATK', 'NAME']:
                    continue
                
                # Skip numbers and short lines
                if line.isdigit() or len(line) < 5:
                    continue
                
                # Check for comma-separated keyword line (3+ parts)
                if ',' in line and line.count(',') >= 2:
                    # Extract first part (team name)
                    parts = [p.strip() for p in line.split(',')]
                    team_candidate = parts[0]
                    
                    # Try to match
                    team = self.team_identifier.identify_team(team_candidate)
                    if team:
                        return team_candidate
        
        # TEAM DATACARDS (portrait): "{TEAMNAME} TEAM" pattern in top lines
        elif card_type == CardType.DATACARDS and not is_landscape:
            # Look in top lines for "{TEAMNAME} TEAM" pattern
            for line in lines[:10]:
                line_upper = line.upper()
                if ' TEAM' in line_upper or line_upper.endswith('TEAM'):
                    # Remove "TEAM" to get team name
                    team_candidate = line_upper.replace(' TEAM', '').strip()
                    team = self.team_identifier.identify_team(team_candidate)
                    if team:
                        return team_candidate
        
        # OTHER CARD TYPES: Standard structure (top lines)
        # Try largest text by font size
        text_dict = page.get_text("dict")
        text_by_size = []
        for block in text_dict["blocks"]:
            if block["type"] == 0:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        size = span["size"]
                        if text and len(text) > 3:
                            text_by_size.append((size, text))
        
        text_by_size.sort(reverse=True, key=lambda x: x[0])
        
        # Try top lines (team name typically in largest text)
        for size, text in text_by_size[:20]:  # Check more items
            if len(text) > 5:
                # Try exact match
                team = self.team_identifier.identify_team(text)
                if team:
                    return text
                
                # Try splitting on commas
                if ',' in text:
                    for part in text.split(','):
                        part = part.strip()
                        if len(part) > 3:
                            team = self.team_identifier.identify_team(part)
                            if team:
                                return part
                
                # Try splitting on spaces
                if ' ' in text:
                    for word in text.split():
                        word = word.strip()
                        if len(word) > 3:
                            team = self.team_identifier.identify_team(word)
                            if team:
                                return word
        
        # Fallback: scan all lines
        for line in lines:
            if len(line) > 5:
                team = self.team_identifier.identify_team(line)
                if team:
                    return line
                
                # Try words in line
                for word in line.split():
                    word = word.strip(',.;:')
                    if len(word) > 3:
                        team = self.team_identifier.identify_team(word)
                        if team:
                            return word
        
        return None
    
    def split_pdf_to_pages(self, pdf_path: Path, output_dir: Path, prefix: str, card_type: str) -> List[Path]:
        """Split PDF into single-page PDFs in type-specific subdirectory"""
        # Create type subdirectory
        type_dir = output_dir / card_type
        type_dir.mkdir(parents=True, exist_ok=True)
        
        pdf = fitz.open(pdf_path)
        page_files = []
        
        for page_num in range(len(pdf)):
            # Create new PDF with single page
            single_page_pdf = fitz.open()
            single_page_pdf.insert_pdf(pdf, from_page=page_num, to_page=page_num)
            
            # Save with prefix
            output_path = type_dir / f"{prefix}-page_{page_num}.pdf"
            single_page_pdf.save(output_path)
            single_page_pdf.close()
            
            page_files.append(output_path)
        
        pdf.close()
        return page_files


# ===================================================================
# MAIN STEP LOGIC
# ===================================================================

def _archive_input_pdf(pdf_path: Path, archive_root: Path, team_name: str) -> None:
    """Move a successfully identified input PDF into layers/archive/{team}/."""
    team_archive_dir = archive_root / team_name
    team_archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = team_archive_dir / pdf_path.name
    try:
        if archive_path.exists():
            archive_path.unlink()
        shutil.move(str(pdf_path), str(archive_path))
        logger.info(f"  Archived input -> {archive_path}")
    except Exception as exc:
        logger.warning(f"  Could not archive input {pdf_path.name}: {exc}")


def run(
    input_dir: Path = Path('input'),
    layers_dir: Path = Path('layers/kt-app'),
    config_path: Path = Path('config/team-config.yaml'),
    teams_filter: Optional[List[str]] = None,
    force: bool = False,
    archive_inputs: bool = True,
) -> Dict:
    """
    Run Step 1: Process PDFs
    
    Args:
        input_dir: Directory with raw PDFs
        layers_dir: Base layers directory
        config_path: Team config file
        teams_filter: Optional list of teams to process
        force: Force reprocessing even if unchanged
        archive_inputs: Move identified PDFs from input/ to layers/archive/{team}/
    
    Returns:
        Statistics dictionary
    """
    logger.info("=" * 80)
    logger.info("Step 1: Process PDFs")
    logger.info("=" * 80)
    
    # Setup paths
    processed_dir = layers_dir / 'processed'
    extracted_dir = layers_dir / 'extracted'
    archive_dir = Path('layers/archive')
    metadata_file = layers_dir / 'metadata.json'
    
    # Initialize
    team_identifier = TeamIdentifier(config_path)
    pdf_processor = PDFProcessor(team_identifier)
    metadata_manager = MetadataManager(metadata_file)
    
    # Find all PDFs
    pdf_files = list(input_dir.rglob('*.pdf'))
    logger.info(f"Found {len(pdf_files)} PDFs in {input_dir}")
    
    stats = {
        'scanned': len(pdf_files),
        'identified': 0,
        'processed': 0,
        'pages_extracted': 0,
        'skipped': 0,
        'failed': 0
    }
    
    for pdf_path in sorted(pdf_files):
        logger.info(f"Processing: {pdf_path.name}")
        
        # Identify
        team, card_type = pdf_processor.identify_pdf(pdf_path)
        if not team or not card_type:
            logger.warning(f"  Skipped: Could not identify")
            stats['failed'] += 1
            continue
        
        stats['identified'] += 1
        
        # Filter by team
        if teams_filter and team.name not in teams_filter:
            logger.debug(f"  Skipped: Team {team.name} not in filter")
            stats['skipped'] += 1
            continue
        
        logger.info(f"  Team: {team.name}")
        logger.info(f"  Type: {card_type.value}")
        
        # Setup output paths
        team_processed_dir = processed_dir / team.name
        team_extracted_dir = extracted_dir / team.name / 'cards'
        team_processed_dir.mkdir(parents=True, exist_ok=True)
        
        # Output filename
        output_filename = f"{team.name}-{card_type.value}.pdf"
        output_path = team_processed_dir / output_filename
        
        # Check if changed
        if not force and output_path.exists():
            if not metadata_manager.has_changed(team.name, "1_process", output_filename, pdf_path):
                logger.info(f"  Skipped: No changes detected")
                stats['skipped'] += 1
                if archive_inputs:
                    _archive_input_pdf(pdf_path, archive_dir, team.name)
                continue
        
        # Copy to processed/
        shutil.copy2(pdf_path, output_path)
        logger.info(f"  Copied to: {output_path}")
        
        # Update metadata
        metadata_manager.update_file(team.name, "1_process", output_filename, output_path)
        
        # Split into single pages
        prefix = f"{team.name}-{card_type.value}"
        page_files = pdf_processor.split_pdf_to_pages(output_path, team_extracted_dir, prefix, card_type.value)
        
        logger.info(f"  Extracted {len(page_files)} pages to: {team_extracted_dir / card_type.value}")
        
        # Update metadata for each page
        for page_file in page_files:
            metadata_manager.update_file(team.name, "1_process", page_file.name, page_file)
        
        stats['processed'] += 1
        stats['pages_extracted'] += len(page_files)

        if archive_inputs:
            _archive_input_pdf(pdf_path, archive_dir, team.name)
    
    # Mark step complete
    metadata_manager.metadata["last_full_run"] = datetime.now(timezone.utc).isoformat()
    metadata_manager.save_metadata()
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("Step 1 Complete!")
    logger.info(f"  Scanned: {stats['scanned']}")
    logger.info(f"  Identified: {stats['identified']}")
    logger.info(f"  Processed: {stats['processed']}")
    logger.info(f"  Pages extracted: {stats['pages_extracted']}")
    logger.info(f"  Skipped: {stats['skipped']}")
    logger.info(f"  Failed: {stats['failed']}")
    logger.info("=" * 80)
    
    return stats


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description='Step 1: Process PDFs')
    parser.add_argument('--input-dir', default='input', help='Input directory with raw PDFs')
    parser.add_argument('--layers-dir', default='layers/kt-app', help='Layers directory')
    parser.add_argument('--config', default='config/team-config.yaml', help='Team config file')
    parser.add_argument('--teams', help='Comma-separated list of teams to process')
    parser.add_argument('--force', action='store_true', help='Force reprocessing')
    parser.add_argument('--no-archive', action='store_true', help='Do not move input PDFs to layers/archive after processing')
    
    args = parser.parse_args()
    
    teams_filter = None
    if args.teams:
        teams_filter = [t.strip() for t in args.teams.split(',')]
    
    run(
        input_dir=Path(args.input_dir),
        layers_dir=Path(args.layers_dir),
        config_path=Path(args.config),
        teams_filter=teams_filter,
        force=args.force,
        archive_inputs=not args.no_archive,
    )


if __name__ == '__main__':
    main()
