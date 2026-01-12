"""Box texture management for TTS objects"""
import shutil
from pathlib import Path
from typing import List
import logging

from ..models.team import Team


class BoxTextureProcessor:
    """Manages box texture images for TTS objects"""
    
    def __init__(
        self,
        config_dir: Path = Path('config'),
        output_v2_dir: Path = Path('output_v2')
    ):
        """
        Initialize BoxTextureProcessor
        
        Args:
            config_dir: Directory containing config files
            output_v2_dir: Directory for output files
        """
        self.config_dir = config_dir
        self.output_v2_dir = output_v2_dir
        self.default_dir = config_dir / 'defaults' / 'box'
        self.teams_dir = config_dir / 'teams'
        self.logger = logging.getLogger(__name__)
    
    def process_box_textures(self, teams: List[Team]) -> int:
        """
        Copy box textures to output_v2 folder structure
        
        Args:
            teams: List of Team objects
            
        Returns:
            Number of box textures processed
        """
        processed_count = 0
        
        for team in teams:
            texture_path = self._get_texture_for_team(team)
            if not texture_path:
                self.logger.warning(
                    f"No box texture found for {team.name}"
                )
                continue
            
            # Determine output path using team's faction and army
            team_output_dir = self.output_v2_dir / team.faction / team.army / team.name / "tts"
            team_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy texture with team name prefix
            output_file = team_output_dir / f"{team.name}-card-box-texture.jpg"
            
            try:
                shutil.copy2(texture_path, output_file)
                processed_count += 1
                self.logger.info(f"Copied box texture: {output_file}")
            except Exception as e:
                self.logger.error(
                    f"Failed to copy box texture to {output_file}: {e}"
                )
        
        return processed_count
    
    def _get_texture_for_team(self, team: Team) -> Path:
        """Get appropriate box texture for team"""
        # Priority 1: Team-specific texture
        team_texture = (
            self.teams_dir / 
            team.name / 
            'box' /
            'card-box-texture.jpg'
        )
        if team_texture.exists():
            return team_texture
        
        # Priority 2: Default texture
        default_texture = self.default_dir / 'card-box-texture.jpg'
        if default_texture.exists():
            return default_texture
        
        # No texture found
        self.logger.error(
            f"No box texture found for team {team.name}"
        )
        return None
    
    def validate_textures(self) -> bool:
        """
        Validate that default box texture exists
        
        Returns:
            True if valid, False otherwise
        """
        default_path = self.default_dir / 'card-box-texture.jpg'
        if not default_path.exists():
            self.logger.error(
                f"Missing default box texture: {default_path}"
            )
            return False
        
        return True
