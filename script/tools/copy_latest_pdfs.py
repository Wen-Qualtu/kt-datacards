"""
Helper script: Copy latest PDFs from archive/ to input/

Compares archive/ PDFs against processed/ to find latest versions,
then copies them to input/ for pipeline processing.
"""

import hashlib
import shutil
import sys
import re
import yaml
from pathlib import Path
from typing import Dict, Set, Tuple, Optional, List
from enum import Enum

import fitz  # PyMuPDF


# ===================================================================
# MINIMAL MODELS (from Step 1)
# ===================================================================

class CardType(Enum):
    """PDF card types"""
    DATACARDS = "datacards"
    FACTION_RULES = "faction-rules"
    OPERATIVES = "operatives"
    EQUIPMENT = "equipment"
    STRATEGY_PLOYS = "strategy-ploys"
    FIREFIGHT_PLOYS = "firefight-ploys"


class Team:
    """Team representation"""
    def __init__(self, name: str, aliases: List[str] = None):
        self.name = name
        self.aliases = aliases or []
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize team name to slug format"""
        normalized = name.lower()
        normalized = re.sub(r'[\s_]+', '-', normalized)
        normalized = re.sub(r'[^a-z0-9\-]', '', normalized)
        normalized = re.sub(r'-+', '-', normalized)
        return normalized.strip('-')
    
    def matches(self, text: str) -> bool:
        """Check if text matches this team"""
        normalized = self.normalize_name(text)
        if normalized == self.name:
            return True
        for alias in self.aliases:
            if self.normalize_name(alias) == normalized:
                return True
        return False


class TeamIdentifier:
    """Identifies teams from config"""
    def __init__(self, config_path: Path):
        self.teams: Dict[str, Team] = {}
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            for team_key, team_data in config.get('teams', {}).items():
                team_key_norm = Team.normalize_name(team_key)
                team = Team(name=team_key_norm, aliases=team_data.get('aliases', []))
                self.teams[team_key_norm] = team
    
    def identify_team(self, text: str) -> Optional[Team]:
        """Identify team from text"""
        if not text:
            return None
        normalized = Team.normalize_name(text)
        if normalized in self.teams:
            return self.teams[normalized]
        for team in self.teams.values():
            if team.matches(text):
                return team
        return None


class SimplePDFIdentifier:
    """Simple PDF identifier using filename only"""
    def __init__(self, team_identifier: TeamIdentifier):
        self.team_identifier = team_identifier
    
    def identify_from_filename(self, pdf_path: Path) -> Tuple[Optional[Team], Optional[CardType]]:
        """Identify team and type from filename"""
        filename = pdf_path.stem.lower()
        
        # Find card type
        card_type = None
        for ct in CardType:
            type_variants = [ct.value, ct.value.replace('-', ' ')]
            if any(variant in filename for variant in type_variants):
                card_type = ct
                # Extract team part (before card type)
                team_part = filename
                for variant in type_variants:
                    if variant in team_part:
                        team_part = team_part.replace(variant, '').strip('-_ ')
                        break
                if team_part:
                    team = self.team_identifier.identify_team(team_part)
                    if team:
                        return team, card_type
                break
        
        return None, None


# ===================================================================
# MAIN LOGIC
# ==================================================================

def compute_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of file"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

def find_latest_pdfs(
    archive_dir: Path,
    processed_dir: Path,
    config_path: Path
) -> Dict[str, Path]:
    """
    Find latest PDFs from archive by comparing against processed.
    
    Returns:
        Dict mapping output filename to archive PDF path
    """
    print(f"Scanning archive: {archive_dir}")
    print(f"Comparing against: {processed_dir}")
    
    # Initialize identifier
    team_identifier = TeamIdentifier(config_path)
    pdf_identifier = SimplePDFIdentifier(team_identifier)
    
    # Build hash map of processed PDFs
    processed_hashes: Dict[str, Tuple[str, str]] = {}  # hash -> (team, filename)
    
    if processed_dir.exists():
        for team_dir in processed_dir.iterdir():
            if not team_dir.is_dir():
                continue
            
            for pdf_file in team_dir.glob('*.pdf'):
                file_hash = compute_hash(pdf_file)
                processed_hashes[file_hash] = (team_dir.name, pdf_file.name)
    
    print(f"Found {len(processed_hashes)} processed PDFs")
    
    # Scan archive and identify PDFs
    latest_pdfs: Dict[str, Path] = {}  # output_filename -> archive_path
    found_hashes: Set[str] = set()
    skipped_count = 0
    identified_count = 0
    
    for team_dir in sorted(archive_dir.iterdir()):
        if not team_dir.is_dir():
            continue
        
        team_name = team_dir.name
        print(f"\nProcessing {team_name}...")
        
        for pdf_file in team_dir.glob('*.pdf'):
            # Compute hash
            file_hash = compute_hash(pdf_file)
            
            # Skip if we've already seen this file
            if file_hash in found_hashes:
                continue
            
            # Check if this matches a processed PDF
            if file_hash in processed_hashes:
                proc_team, proc_filename = processed_hashes[file_hash]
                
                # Verify team matches
                if proc_team == team_name:
                    print(f"  [OK] Found match: {proc_filename}")
                    latest_pdfs[proc_filename] = pdf_file
                    found_hashes.add(file_hash)
                    identified_count += 1
                else:
                    print(f"  [WARN] Hash match but team mismatch: {proc_team} vs {team_name}")
            else:
                # Not in processed - try to identify
                team, card_type = pdf_identifier.identify_from_filename(pdf_file)
                
                if team and card_type:
                    output_filename = f"{team.name}-{card_type.value}.pdf"
                    
                    # Only add if we don't have it yet
                    if output_filename not in latest_pdfs:
                        print(f"  + New: {output_filename}")
                        latest_pdfs[output_filename] = pdf_file
                        found_hashes.add(file_hash)
                        identified_count += 1
                    else:
                        skipped_count += 1
                else:
                    skipped_count += 1
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Identified: {identified_count}")
    print(f"  Unique files: {len(latest_pdfs)}")
    print(f"  Skipped: {skipped_count}")
    print(f"{'='*60}")
    
    return latest_pdfs

def copy_to_input(latest_pdfs: Dict[str, Path], input_dir: Path, force: bool = False):
    """Copy PDFs to input directory"""
    input_dir.mkdir(parents=True, exist_ok=True)
    
    # Clear input if force
    if force and input_dir.exists():
        for f in input_dir.glob('*.pdf'):
            f.unlink()
        print(f"Cleared {input_dir}")
    
    copied = 0
    skipped = 0
    
    for output_filename, archive_path in sorted(latest_pdfs.items()):
        dest_path = input_dir / output_filename
        
        # Skip if exists and not forcing
        if dest_path.exists() and not force:
            skipped += 1
            continue
        
        shutil.copy2(archive_path, dest_path)
        print(f"Copied: {output_filename}")
        copied += 1
    
    print(f"\nCopied {copied} files to {input_dir}")
    if skipped > 0:
        print(f"Skipped {skipped} existing files")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Copy latest PDFs from archive to input')
    parser.add_argument('--archive-dir', default='archive', help='Archive directory')
    parser.add_argument('--processed-dir', default='processed', help='Processed directory')
    parser.add_argument('--input-dir', default='input', help='Input directory')
    parser.add_argument('--config', default='config/team-config.yaml', help='Team config')
    parser.add_argument('--force', action='store_true', help='Overwrite existing files')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be copied')
    
    args = parser.parse_args()
    
    # Find latest PDFs
    latest_pdfs = find_latest_pdfs(
        archive_dir=Path(args.archive_dir),
        processed_dir=Path(args.processed_dir),
        config_path=Path(args.config)
    )
    
    if args.dry_run:
        print("\n=== DRY RUN ===")
        for filename in sorted(latest_pdfs.keys()):
            print(f"  Would copy: {filename}")
        return
    
    # Copy to input
    copy_to_input(latest_pdfs, Path(args.input_dir), force=args.force)

if __name__ == '__main__':
    main()
