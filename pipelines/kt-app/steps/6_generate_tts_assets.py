"""
Step 6: Generate TTS Assets

Generates 3D assets needed for Tabletop Simulator cardbox objects:
- Cardbox mesh (.obj) and texture (.jpg) for each team
- Token bag mesh (.obj) for teams with tokens
- Preview/icon images

Input:
    config/team-config.yaml - Team configuration
    config/defaults/box/ - Default cardbox mesh and texture
    config/teams/{team}/box/ - Team-specific overrides (optional)
    
Output:
    output_v3/{team}/tts/{team}-card-box.obj
    output_v3/{team}/tts/{team}-card-box-texture.jpg
    output_v3/{team}/tts/{team}-token-bag.obj (for tokens_ready teams)
"""

import argparse
import logging
import shutil
import yaml
from pathlib import Path
from typing import Dict, Optional

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class TTSAssetGenerator:
    """Generates TTS 3D assets for teams."""
    
    def __init__(
        self,
        output_dir: Path,
        config_file: Path,
        config_dir: Path
    ):
        self.output_dir = output_dir
        self.config_file = config_file
        self.config_dir = config_dir
        self.default_box_dir = config_dir / "defaults" / "box"
        self.teams_dir = config_dir / "teams"
        
        # Load team config
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            self.teams = config.get('teams', {})
    
    def process_team(self, team: str) -> bool:
        """
        Generate TTS assets for a single team.
        
        Args:
            team: Team slug
            
        Returns:
            True if successful
        """
        logger.info(f"Generating TTS assets for {team}...")
        
        team_config = self.teams.get(team)
        if not team_config:
            logger.error(f"  Team not found in config: {team}")
            return False
        
        # Create output directory
        team_tts_dir = self.output_dir / team / "tts"
        team_tts_dir.mkdir(parents=True, exist_ok=True)
        
        # Get cardbox assets
        mesh_source = self._get_mesh_for_team(team)
        texture_source = self._get_texture_for_team(team)
        
        if not mesh_source or not texture_source:
            logger.error(f"  Missing cardbox assets for {team}")
            return False
        
        # Copy cardbox assets
        mesh_dest = team_tts_dir / f"{team}-card-box.obj"
        texture_dest = team_tts_dir / f"{team}-card-box-texture.jpg"
        
        try:
            shutil.copy2(mesh_source, mesh_dest)
            shutil.copy2(texture_source, texture_dest)
            logger.info(f"  Copied cardbox assets")
        except Exception as e:
            logger.error(f"  Failed to copy cardbox assets: {e}")
            return False
        
        # Generate token bag mesh if team has tokens
        tokens_ready = team_config.get('tokens_ready', False)
        if tokens_ready:
            token_bag_source = self._get_token_bag_mesh()
            if token_bag_source:
                token_bag_dest = team_tts_dir / f"{team}-token-bag.obj"
                try:
                    shutil.copy2(token_bag_source, token_bag_dest)
                    logger.info(f"  Copied token bag mesh")
                except Exception as e:
                    logger.error(f"  Failed to copy token bag mesh: {e}")
        
        return True
    
    def _get_mesh_for_team(self, team: str) -> Optional[Path]:
        """Get cardbox mesh for team (team-specific or default)."""
        # Priority 1: Team-specific mesh
        team_mesh = self.teams_dir / team / "box" / "card-box.obj"
        if team_mesh.exists():
            return team_mesh
        
        # Priority 2: Default mesh
        default_mesh = self.default_box_dir / "card-box.obj"
        if default_mesh.exists():
            return default_mesh
        
        logger.error(f"  No cardbox mesh found for {team}")
        return None
    
    def _get_texture_for_team(self, team: str) -> Optional[Path]:
        """Get cardbox texture for team (team-specific or default)."""
        # Priority 1: Team-specific texture
        team_texture = self.teams_dir / team / "box" / "card-box-texture.jpg"
        if team_texture.exists():
            return team_texture
        
        # Priority 2: Default texture
        default_texture = self.default_box_dir / "card-box-texture.jpg"
        if default_texture.exists():
            return default_texture
        
        logger.error(f"  No cardbox texture found for {team}")
        return None
    
    def _get_token_bag_mesh(self) -> Optional[Path]:
        """Get default token bag mesh."""
        token_bag_mesh = self.default_box_dir / "token-bag.obj"
        if token_bag_mesh.exists():
            return token_bag_mesh
        
        logger.warning("  No default token bag mesh found")
        return None


def main():
    """Generate TTS assets for teams."""
    parser = argparse.ArgumentParser(
        description='Step 6: Generate TTS Assets'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=PROJECT_ROOT / 'output_v3',
        help='Output V3 directory'
    )
    parser.add_argument(
        '--config',
        type=Path,
        default=PROJECT_ROOT / 'config' / 'team-config.yaml',
        help='Team config file'
    )
    parser.add_argument(
        '--config-dir',
        type=Path,
        default=PROJECT_ROOT / 'config',
        help='Config directory'
    )
    parser.add_argument(
        '--teams',
        type=str,
        help='Comma-separated list of teams to process (default: all)'
    )
    
    args = parser.parse_args()
    
    # Initialize generator
    generator = TTSAssetGenerator(
        output_dir=args.output_dir,
        config_file=args.config,
        config_dir=args.config_dir
    )
    
    # Get teams to process
    if args.teams:
        teams = [t.strip() for t in args.teams.split(',')]
    else:
        # Get all teams from config
        teams = sorted(generator.teams.keys())
    
    logger.info(f"Processing {len(teams)} teams...")
    
    # Process teams
    success_count = 0
    for team in teams:
        try:
            if generator.process_team(team):
                success_count += 1
        except Exception as e:
            logger.error(f"  Error processing {team}: {e}")
    
    logger.info(f"Successfully generated TTS assets for {success_count}/{len(teams)} teams")


if __name__ == "__main__":
    main()
