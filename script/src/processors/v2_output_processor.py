"""V2 output processor with faction/army hierarchy and team-prefixed naming"""
import shutil
from pathlib import Path
from typing import List, Dict
import logging

from ..models.team import Team
from ..models.card_type import CardType
from ..models.datacard import Datacard


class V2OutputProcessor:
    """Processes output for V2 format with enhanced structure"""
    
    def __init__(
        self,
        v1_output_dir: Path = Path('output'),
        v2_output_dir: Path = Path('output_v2')
    ):
        """
        Initialize V2OutputProcessor
        
        Args:
            v1_output_dir: V1 output directory to copy from
            v2_output_dir: V2 output directory with faction/army structure
        """
        self.v1_output_dir = v1_output_dir
        self.v2_output_dir = v2_output_dir
        self.logger = logging.getLogger(__name__)
    
    def process_team(self, team: Team) -> Dict[str, int]:
        """
        Process a team's output from v1 to v2 format
        
        Args:
            team: Team to process
            
        Returns:
            Statistics dictionary
        """
        stats = {
            'files_processed': 0,
            'files_skipped': 0,
            'errors': 0
        }
        
        v1_team_dir = self.v1_output_dir / team.name
        if not v1_team_dir.exists():
            self.logger.warning(f"V1 team directory not found: {v1_team_dir}")
            return stats
        
        self.logger.info(f"Processing team {team.name} for v2 output")
        
        # Copy team_data.json to v2 structure
        team_data_file = v1_team_dir / 'team_data.json'
        if team_data_file.exists():
            v2_team_dir = team.get_v2_output_path(self.v2_output_dir)
            v2_team_dir.mkdir(parents=True, exist_ok=True)
            v2_team_data_path = v2_team_dir / 'team_data.json'
            
            try:
                shutil.copy2(team_data_file, v2_team_data_path)
                stats['files_processed'] += 1
                self.logger.info(f"Copied team_data.json to {v2_team_data_path}")
            except Exception as e:
                self.logger.error(f"Error copying team_data.json: {e}")
                stats['errors'] += 1
        
        # Process each card type directory
        for card_type_dir in v1_team_dir.iterdir():
            if not card_type_dir.is_dir():
                continue
            
            card_type_name = card_type_dir.name
            
            # Determine v2 folder name (operatives -> operative-selection)
            v2_folder_name = "operative-selection" if card_type_name == "operatives" else card_type_name
            
            # Get v2 output directory
            v2_type_dir = team.get_v2_output_path(self.v2_output_dir) / v2_folder_name
            v2_type_dir.mkdir(parents=True, exist_ok=True)
            
            # Process each image in the card type directory
            for image_file in card_type_dir.glob('*.jpg'):
                try:
                    # Rename operatives to operative-selection in filename
                    filename = image_file.name
                    if card_type_name == "operatives":
                        # Replace "operatives" with "operative-selection" in the filename
                        filename = filename.replace("operatives", "operative-selection")
                    
                    new_filename = self._add_team_prefix(filename, team.name)
                    v2_image_path = v2_type_dir / new_filename
                    
                    # Copy file to v2 location
                    shutil.copy2(image_file, v2_image_path)
                    stats['files_processed'] += 1
                    
                except Exception as e:
                    self.logger.error(f"Error processing {image_file}: {e}")
                    stats['errors'] += 1
        
        self.logger.info(
            f"Completed {team.name}: {stats['files_processed']} files processed, "
            f"{stats['errors']} errors"
        )
        
        return stats
    
    def process_all_teams(self, teams: List[Team]) -> Dict[str, int]:
        """
        Process all teams for v2 output
        
        Args:
            teams: List of teams to process
            
        Returns:
            Aggregated statistics
        """
        total_stats = {
            'files_processed': 0,
            'files_skipped': 0,
            'errors': 0,
            'teams_processed': 0
        }
        
        for team in teams:
            stats = self.process_team(team)
            total_stats['files_processed'] += stats['files_processed']
            total_stats['files_skipped'] += stats['files_skipped']
            total_stats['errors'] += stats['errors']
            total_stats['teams_processed'] += 1
        
        self.logger.info(
            f"V2 processing complete: {total_stats['teams_processed']} teams, "
            f"{total_stats['files_processed']} files"
        )
        
        return total_stats
    
    def _add_team_prefix(self, filename: str, team_name: str) -> str:
        """
        Add team prefix to filename if not already present
        
        Args:
            filename: Original filename
            team_name: Team name to use as prefix
            
        Returns:
            Filename with team prefix
        """
        # Check if filename already starts with team name
        filename_lower = filename.lower()
        team_prefix = team_name.lower()
        
        # Handle multi-word team names
        if filename_lower.startswith(team_prefix):
            return filename
        
        # Check if it starts with any part of the team name
        team_parts = team_prefix.split('-')
        if len(team_parts) > 1:
            # For multi-word teams, check if starts with first word
            if filename_lower.startswith(team_parts[0]):
                return filename
        
        # Add team prefix
        return f"{team_name}-{filename}"
    
    def generate_v2_urls_json(self, github_base: str = None) -> int:
        """
        Generate URLs JSON for v2 format
        
        Args:
            github_base: Base GitHub URL (if None, uses default)
            
        Returns:
            Number of URLs generated
        """
        if github_base is None:
            github_base = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2"
        
        import json
        
        entries = []
        
        if not self.v2_output_dir.exists():
            self.logger.warning(f"V2 output directory not found: {self.v2_output_dir}")
            return 0
        
        # Walk through faction/army/team structure
        for faction_dir in sorted(self.v2_output_dir.iterdir()):
            if not faction_dir.is_dir():
                continue
            
            faction_name = faction_dir.name
            
            for army_dir in sorted(faction_dir.iterdir()):
                if not army_dir.is_dir():
                    continue
                
                army_name = army_dir.name
                
                for team_dir in sorted(army_dir.iterdir()):
                    if not team_dir.is_dir():
                        continue
                    
                    team_name = team_dir.name
                    
                    # Walk through card type directories
                    for type_dir in sorted(team_dir.iterdir()):
                        if not type_dir.is_dir():
                            continue
                        
                        type_name = type_dir.name
                        
                        # Collect all JPG files
                        for jpg_file in sorted(type_dir.glob('*.jpg')):
                            file_name = jpg_file.stem  # Name without extension
                            
                            # Construct GitHub raw URL (use forward slashes)
                            url = f"{github_base}/{faction_name}/{army_name}/{team_name}/{type_name}/{jpg_file.name}"
                            
                            entries.append({
                                'faction': faction_name,
                                'army': army_name,
                                'team': team_name,
                                'type': type_name,
                                'name': file_name,
                                'url': url
                            })
        
        # Write JSON
        json_path = self.v2_output_dir / 'datacards-urls.json'
        with open(json_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(entries, jsonfile, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Generated {json_path} with {len(entries)} entries")
        
        return len(entries)
