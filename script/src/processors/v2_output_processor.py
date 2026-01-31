"""V2 output processor with faction/army hierarchy and team-prefixed naming"""
import shutil
from pathlib import Path
from typing import List, Dict
import logging

from ..models.team import Team
from ..models.card_type import CardType
from ..models.datacard import Datacard


class V2OutputProcessor:
    """Generates URLs for V2 output format"""
    
    def __init__(
        self,
        v2_output_dir: Path = Path('output_v2')
    ):
        """
        Initialize V2OutputProcessor
        
        Args:
            v2_output_dir: V2 output directory with faction/army structure
        """
        self.v2_output_dir = v2_output_dir
        self.logger = logging.getLogger(__name__)
    
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
        
        # Walk through faction/team structure
        for faction_dir in sorted(self.v2_output_dir.iterdir()):
            if not faction_dir.is_dir():
                continue
            
            faction_name = faction_dir.name
            
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
                        url = f"{github_base}/{faction_name}/{team_name}/{type_name}/{jpg_file.name}"
                        
                        entries.append({
                            'faction': faction_name,
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
