"""Backside image management for cards"""
import shutil
from pathlib import Path
from typing import List, Optional
import logging

from ..models.team import Team
from ..models.card_type import CardType
from ..models.datacard import Datacard


class BacksideProcessor:
    """Manages backside images for cards"""
    
    def __init__(
        self,
        config_dir: Path = Path('config/card-backside')
    ):
        """
        Initialize BacksideProcessor
        
        Args:
            config_dir: Directory containing backside images
        """
        self.config_dir = config_dir
        self.default_dir = config_dir / 'default'
        self.team_dir = config_dir / 'team'
        self.logger = logging.getLogger(__name__)
        
        # Cache for backside paths
        self._backside_cache = {}
    
    def add_backsides(self, datacards: List[Datacard]) -> int:
        """
        Add backside images to cards that need them
        
        Args:
            datacards: List of Datacard objects
            
        Returns:
            Number of backsides added
        """
        added_count = 0
        
        for datacard in datacards:
            # Skip if card already has backside
            if datacard.back_image and datacard.back_image.exists():
                continue
            
            # Skip if no front image
            if not datacard.front_image or not datacard.front_image.exists():
                continue
            
            # Get appropriate backside
            backside_path = self._get_backside_for_card(datacard)
            if not backside_path:
                self.logger.warning(
                    f"No backside found for {datacard.card_name}"
                )
                continue
            
            # Copy backside
            back_output = (
                datacard.get_output_folder() / 
                datacard.get_expected_back_filename()
            )
            
            try:
                back_output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backside_path, back_output)
                datacard.back_image = back_output
                added_count += 1
                self.logger.info(f"Added backside: {back_output}")
            except Exception as e:
                self.logger.error(
                    f"Failed to copy backside to {back_output}: {e}"
                )
        
        return added_count
    
    def _get_backside_for_card(self, datacard: Datacard) -> Optional[Path]:
        """Get appropriate backside image for card"""
        # Determine orientation
        orientation = self._get_orientation(datacard.card_type)
        
        # Check cache
        cache_key = (datacard.team.name, orientation)
        if cache_key in self._backside_cache:
            return self._backside_cache[cache_key]
        
        # Priority 1: Team-specific backside
        team_backside = (
            self.team_dir / 
            datacard.team.name / 
            f'{datacard.team.name}-backside-{orientation}.jpg'
        )
        if team_backside.exists():
            self._backside_cache[cache_key] = team_backside
            return team_backside
        
        # Priority 2: Default backside
        default_backside = (
            self.default_dir / 
            f'default-backside-{orientation}.jpg'
        )
        if default_backside.exists():
            self._backside_cache[cache_key] = default_backside
            return default_backside
        
        # No backside found
        self.logger.error(
            f"No {orientation} backside found for team {datacard.team.name}"
        )
        return None
    
    def _get_orientation(self, card_type: CardType) -> str:
        """Determine orientation for card type"""
        # Datacards use landscape, others use portrait
        if card_type == CardType.DATACARDS:
            return 'landscape'
        return 'portrait'
    
    def validate_backsides(self) -> bool:
        """
        Validate that required backside images exist
        
        Returns:
            True if valid, False otherwise
        """
        valid = True
        
        # Check default backsides
        for orientation in ['portrait', 'landscape']:
            default_path = (
                self.default_dir / 
                f'default-backside-{orientation}.jpg'
            )
            if not default_path.exists():
                self.logger.error(
                    f"Missing default backside: {default_path}"
                )
                valid = False
        
        return valid
    
    def list_team_backsides(self) -> dict:
        """
        List all team-specific backsides
        
        Returns:
            Dict mapping team names to list of orientations
        """
        team_backsides = {}
        
        if not self.team_dir.exists():
            return team_backsides
        
        for team_folder in self.team_dir.iterdir():
            if not team_folder.is_dir():
                continue
            
            team_name = team_folder.name
            orientations = []
            
            for orientation in ['portrait', 'landscape']:
                backside_path = team_folder / f'{team_name}-backside-{orientation}.jpg'
                if backside_path.exists():
                    orientations.append(orientation)
            
            if orientations:
                team_backsides[team_name] = orientations
        
        return team_backsides
