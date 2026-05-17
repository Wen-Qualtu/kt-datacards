"""Box texture and mesh management for TTS objects"""
import shutil
from pathlib import Path
from typing import List
import logging

from ..models.team import Team


class BoxTextureProcessor:
    """Manages box texture images and mesh files for TTS objects"""
    
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
        Copy box textures and mesh files to output_v2 folder structure
        
        Args:
            teams: List of Team objects
            
        Returns:
            Number of box assets processed
        """
        processed_count = 0
        
        for team in teams:
            # Process texture
            texture_path = self._get_texture_for_team(team)
            if not texture_path:
                self.logger.warning(
                    f"No box texture found for {team.name}"
                )
                continue
            
            # Process mesh
            mesh_path = self._get_mesh_for_team(team)
            if not mesh_path:
                self.logger.warning(
                    f"No box mesh found for {team.name}"
                )
                continue
            
            # Determine output path using team's faction
            if team.faction:
                team_output_dir = self.output_v2_dir / team.faction / team.name / "tts"
            else:
                team_output_dir = self.output_v2_dir / "uncategorized" / team.name / "tts"
            team_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy texture with team name prefix
            output_texture = team_output_dir / f"{team.name}-card-box-texture.jpg"
            try:
                shutil.copy2(texture_path, output_texture)
                self.logger.info(f"Copied box texture: {output_texture}")
            except Exception as e:
                self.logger.error(
                    f"Failed to copy box texture to {output_texture}: {e}"
                )
                continue
            
            # Copy mesh with team name prefix
            output_mesh = team_output_dir / f"{team.name}-card-box.obj"
            try:
                shutil.copy2(mesh_path, output_mesh)
                processed_count += 1
                self.logger.info(f"Copied box mesh: {output_mesh}")
            except Exception as e:
                self.logger.error(
                    f"Failed to copy box mesh to {output_mesh}: {e}"
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
    
    def _get_mesh_for_team(self, team: Team) -> Path:
        """Get appropriate box mesh for team"""
        # Priority 1: Team-specific mesh
        team_mesh = (
            self.teams_dir / 
            team.name / 
            'box' /
            'card-box.obj'
        )
        if team_mesh.exists():
            return team_mesh
        
        # Priority 2: Default mesh
        default_mesh = self.default_dir / 'card-box.obj'
        if default_mesh.exists():
            return default_mesh
        
        # No mesh found
        self.logger.error(
            f"No box mesh found for team {team.name}"
        )
        return None
    
    def validate_textures(self) -> bool:
        """
        Validate that default box texture and mesh exist
        
        Returns:
            True if valid, False otherwise
        """
        default_texture = self.default_dir / 'card-box-texture.jpg'
        if not default_texture.exists():
            self.logger.error(
                f"Missing default box texture: {default_texture}"
            )
            return False
        
        default_mesh = self.default_dir / 'card-box.obj'
        if not default_mesh.exists():
            self.logger.error(
                f"Missing default box mesh: {default_mesh}"
            )
            return False
        
        return True
