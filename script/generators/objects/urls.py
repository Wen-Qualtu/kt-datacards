"""URL generation for GitHub raw access"""
import json
from pathlib import Path
from typing import List, Dict
import logging

from config import get_github_url, GITHUB_BRANCH


class URLGenerator:
    """Generates JSON file with URLs for card images"""
    
    def __init__(
        self,
        output_dir: Path = Path('output'),
        tts_objects_dir: Path = Path('tts_objects'),
        branch: str = None
    ):
        """
        Initialize URLGenerator
        
        Args:
            output_dir: Base output directory containing team folders
            tts_objects_dir: Directory containing TTS saved object files
            branch: GitHub branch for URLs (default: from config/env)
        """
        self.output_dir = output_dir
        self.tts_objects_dir = tts_objects_dir
        self.branch = branch or GITHUB_BRANCH
        self.logger = logging.getLogger(__name__)
        
        self.logger.debug(f"URLGenerator init: output_dir={output_dir}, exists={output_dir.exists()}")
        self.logger.debug(f"URLGenerator init: tts_objects_dir={tts_objects_dir}, exists={tts_objects_dir.exists()}")
        self.logger.debug(f"URLGenerator init: branch={self.branch}")
    
    def generate_json(self, output_path: Path = Path('output/datacards-urls.json')) -> int:
        """
        Generate JSON file with all card image URLs
        
        Args:
            output_path: Path to output JSON file
            
        Returns:
            Number of entries written
        """
        entries = self._collect_entries()
        self.logger.debug(f"Collected {len(entries)} entries from output_v2")
        
        # Add TTS object entries
        tts_entries = self._collect_tts_objects()
        self.logger.debug(f"Collected {len(tts_entries)} TTS entries")
        entries.extend(tts_entries)
        self.logger.debug(f"Total entries: {len(entries)}")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
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
        
        self.logger.debug(f"_collect_entries: output_dir={self.output_dir}, exists={self.output_dir.exists()}")
        
        if not self.output_dir.exists():
            self.logger.warning(f"Output directory not found: {self.output_dir}")
            return entries
        
        # Walk through faction directories, then team directories
        faction_dirs = list(self.output_dir.iterdir())
        self.logger.debug(f"_collect_entries: Found {len(faction_dirs)} items in output_dir")
        
        for faction_dir in sorted(faction_dirs):
            self.logger.debug(f"_collect_entries: Checking {faction_dir.name}, is_dir={faction_dir.is_dir()}")
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
                        
                        # Construct GitHub raw URL using branch-aware helper
                        relative_path = f"output_v2/{faction_name}/{team_name}/{type_name}/{jpg_file.name}"
                        url = get_github_url(relative_path, branch=self.branch)
                        
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
                        
                        # Construct GitHub raw URL using branch-aware helper
                        relative_path = f"output_v2/{faction_name}/{team_name}/{type_name}/{obj_file.name}"
                        url = get_github_url(relative_path, branch=self.branch)
                        
                        entries.append({
                            'faction': faction_name,
                            'team': team_name,
                            'type': type_name,
                            'name': file_name,
                            'url': url
                        })
        
        return entries
    
    def _collect_tts_objects(self) -> List[Dict[str, str]]:
        """Collect TTS saved object files from tts_objects directory"""
        entries = []
        
        print(f"DEBUG: Looking for TTS objects in: {self.tts_objects_dir}")
        print(f"DEBUG: TTS objects directory exists: {self.tts_objects_dir.exists()}")
        
        if not self.tts_objects_dir.exists():
            print(f"DEBUG: TTS objects directory not found!")
            self.logger.warning(f"TTS objects directory not found: {self.tts_objects_dir}")
            return entries
        
        # Find all *Cards.json files
        json_files = list(self.tts_objects_dir.glob('*Cards.json'))
        print(f"DEBUG: Found {len(json_files)} *Cards.json files")
        
        for json_file in sorted(json_files):
            print(f"DEBUG: Processing: {json_file.name}")
            # Extract team name from filename (e.g., "Farstalker Kinband Cards.json" -> "farstalker-kinband")
            team_display_name = json_file.stem.replace(' Cards', '')
            team_id = team_display_name.lower().replace(' ', '-')
            
            # Construct GitHub raw URL using branch-aware helper
            relative_path = f"tts_objects/{json_file.name}"
            url = get_github_url(relative_path, branch=self.branch).replace(' ', '%20')
            
            entries.append({
                'faction': '',  # Not applicable for TTS objects
                'team': team_id,
                'type': 'tts_card_box_object',
                'name': team_display_name,
                'url': url
            })
            
            self.logger.debug(f"Added TTS object: {team_display_name}")
        
        self.logger.info(f"Collected {len(entries)} TTS object files")
        return entries
    
    def _count_by_team(self, entries: List[Dict[str, str]]) -> Dict[str, int]:
        """Count entries by team"""
        team_counts = {}
        for entry in entries:
            team = entry['team']
            team_counts[team] = team_counts.get(team, 0) + 1
        return team_counts
