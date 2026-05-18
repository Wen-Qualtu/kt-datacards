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
    output/{team}/tts/{team}-card-box.obj
    output/{team}/tts/{team}-card-box-texture.jpg
    output/{team}/tts/{team}-token-bag.obj (for tokens_ready teams)
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
        config_dir: Path,
        output_v2_dir: Optional[Path] = None
    ):
        self.output_dir = output_dir
        self.output_v2_dir = output_v2_dir or (PROJECT_ROOT / 'output_v2')
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
        
        # Create output directories
        team_cardbox_dir = self.output_dir / team / "cardbox"
        team_tokens_dir = self.output_dir / team / "tokens"
        team_cardbox_dir.mkdir(parents=True, exist_ok=True)
        team_tokens_dir.mkdir(parents=True, exist_ok=True)
        
        # Get cardbox assets
        mesh_source = self._get_mesh_for_team(team)
        texture_source = self._get_texture_for_team(team)
        
        if not mesh_source or not texture_source:
            logger.error(f"  Missing cardbox assets for {team}")
            return False
        
        # Copy cardbox assets to cardbox/ folder
        mesh_dest    = team_cardbox_dir / f"{team}-card-box.obj"
        texture_dest = team_cardbox_dir / f"{team}-card-box-texture.jpg"

        try:
            # Mesh: always copy (same file for all teams)
            shutil.copy2(mesh_source, mesh_dest)
            # Texture: skip copy when step 5c already placed it at the destination
            if texture_source != texture_dest:
                shutil.copy2(texture_source, texture_dest)
            else:
                logger.info(f"  Texture already generated (step 5c)")
            logger.info(f"  Copied cardbox assets")
        except Exception as e:
            logger.error(f"  Failed to copy cardbox assets: {e}")
            return False
        
        # Generate token bag mesh if team has tokens
        tokens_ready = team_config.get('tokens_ready', False)
        if tokens_ready:
            token_bag_source = self._get_token_bag_mesh()
            if token_bag_source:
                # Put token bag in tokens/tokenbag/ folder
                token_bag_dir = team_tokens_dir / "tokenbag"
                token_bag_dir.mkdir(parents=True, exist_ok=True)
                token_bag_dest = token_bag_dir / f"{team}-token-bag.obj"
                try:
                    shutil.copy2(token_bag_source, token_bag_dest)
                    logger.info(f"  Copied token bag mesh")
                except Exception as e:
                    logger.error(f"  Failed to copy token bag mesh: {e}")
                
                # Copy token bag icon/texture
                token_bag_icon_source = self._get_token_bag_icon(team)
                if token_bag_icon_source:
                    token_bag_icon_dest = token_bag_dir / f"{team}-token-bag-icon.png"
                    try:
                        shutil.copy2(token_bag_icon_source, token_bag_icon_dest)
                        logger.info(f"  Copied token bag icon")
                    except Exception as e:
                        logger.error(f"  Failed to copy token bag icon: {e}")
            
            # Copy individual token meshes and textures from v2 to tokens/ folder
            faction = team_config.get('faction', '')
            if faction:
                v2_token_dir = self.output_v2_dir / faction / team / 'tts' / 'token'
                if v2_token_dir.exists():
                    copied_obj_count = 0
                    copied_png_count = 0
                    
                    # Copy OBJ files
                    for obj_file in v2_token_dir.glob(f'{team}-*.obj'):
                        if obj_file.name != f'{team}-token-mesh.obj':  # Skip generic mesh
                            dest_file = team_tokens_dir / obj_file.name
                            try:
                                shutil.copy2(obj_file, dest_file)
                                copied_obj_count += 1
                            except Exception as e:
                                logger.error(f"  Failed to copy {obj_file.name}: {e}")
                    
                    # Copy PNG texture files
                    for png_file in v2_token_dir.glob(f'{team}-*.png'):
                        dest_file = team_tokens_dir / png_file.name
                        try:
                            shutil.copy2(png_file, dest_file)
                            copied_png_count += 1
                        except Exception as e:
                            logger.error(f"  Failed to copy {png_file.name}: {e}")
                    
                    if copied_obj_count > 0:
                        logger.info(f"  Copied {copied_obj_count} token meshes from v2")
                    if copied_png_count > 0:
                        logger.info(f"  Copied {copied_png_count} token textures from v2")
        
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
        """Get cardbox texture source for team.

        Priority:
          1. config/teams/{team}/box/card-box-texture.jpg  — manual override
          2. output/{team}/cardbox/{team}-card-box-texture.jpg — generated by step 5c
          3. config/defaults/box/card-box-texture.jpg       — generic fallback
        """
        # Priority 1: manual override
        team_texture = self.teams_dir / team / "box" / "card-box-texture.jpg"
        if team_texture.exists():
            return team_texture

        # Priority 2: already generated by step 5c
        generated = self.output_dir / team / "cardbox" / f"{team}-card-box-texture.jpg"
        if generated.exists():
            return generated   # source == destination → caller skips the copy

        # Priority 3: generic default
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
    
    def _get_token_bag_icon(self, team: Optional[str] = None) -> Optional[Path]:
        """Get token bag icon (team-specific or default)."""
        # Priority 1: Team-specific icon
        if team:
            team_icon = self.teams_dir / team / "tts-image" / f"{team}-icon.png"
            if team_icon.exists():
                return team_icon
        
        # Priority 2: Default token bag icon
        token_bag_icon = PROJECT_ROOT / "config" / "defaults" / "tts-token" / "token-bg-sample.png"
        if token_bag_icon.exists():
            return token_bag_icon
        
        logger.warning("  No token bag icon found")
        return None


def main():
    """Generate TTS assets for teams."""
    parser = argparse.ArgumentParser(
        description='Step 6: Generate TTS Assets'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=PROJECT_ROOT / 'output',
        help='Output directory'
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
        config_dir=args.config_dir,
        output_v2_dir=PROJECT_ROOT / 'output_v2'
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
