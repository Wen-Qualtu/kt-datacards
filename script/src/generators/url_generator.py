"""URL generation for GitHub raw access"""
import json
from pathlib import Path
from typing import List, Dict
import logging


class URLGenerator:
    """Generates JSON file with URLs for card images"""
    
    def __init__(
        self,
        output_dir: Path = Path('output'),
        github_base: str = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output"
    ):
        """
        Initialize URLGenerator
        
        Args:
            output_dir: Base output directory containing team folders
            github_base: Base GitHub raw URL
        """
        self.output_dir = output_dir
        self.github_base = github_base
        self.logger = logging.getLogger(__name__)
    
    def generate_json(self, output_path: Path = Path('output/datacards-urls.json')) -> int:
        """
        Generate JSON file with all card image URLs
        
        Args:
            output_path: Path to output JSON file
            
        Returns:
            Number of entries written
        """
        entries = self._collect_entries()
        
        # Write JSON
        with open(output_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(entries, jsonfile, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Generated {output_path} with {len(entries)} entries")
        
        # Log breakdown by team
        team_counts = self._count_by_team(entries)
        self.logger.info(f"Breakdown by team:")
        for team, count in sorted(team_counts.items()):
            self.logger.info(f"  {team}: {count} files")
        
        return len(entries)
    
    def _collect_entries(self) -> List[Dict[str, str]]:
        """Collect all entries from output directory"""
        entries = []
        
        if not self.output_dir.exists():
            self.logger.warning(f"Output directory not found: {self.output_dir}")
            return entries
        
        # Walk through faction directories, then team directories
        for faction_dir in sorted(self.output_dir.iterdir()):
            if not faction_dir.is_dir():
                continue
            
            faction_name = faction_dir.name
            
            # Walk through team directories within faction
            for team_dir in sorted(faction_dir.iterdir()):
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
                        url = f"{self.github_base}/{faction_name}/{team_name}/{type_name}/{jpg_file.name}"
                        
                        entries.append({
                            'faction': faction_name,
                            'team': team_name,
                            'type': type_name,
                            'name': file_name,
                            'url': url
                        })
                    
                    # Also collect .obj mesh files from tts directories
                    for obj_file in sorted(type_dir.glob('*.obj')):
                        file_name = obj_file.name  # Keep full name with extension for .obj files
                        
                        # Construct GitHub raw URL (use forward slashes)
                        url = f"{self.github_base}/{faction_name}/{team_name}/{type_name}/{obj_file.name}"
                        
                        entries.append({
                            'faction': faction_name,
                            'team': team_name,
                            'type': type_name,
                            'name': file_name,
                            'url': url
                        })
        
        return entries
    
    def _count_by_team(self, entries: List[Dict[str, str]]) -> Dict[str, int]:
        """Count entries by team"""
        team_counts = {}
        for entry in entries:
            team = entry['team']
            team_counts[team] = team_counts.get(team, 0) + 1
        return team_counts
