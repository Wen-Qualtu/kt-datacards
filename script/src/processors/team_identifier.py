"""Team identification and management"""
import yaml
from pathlib import Path
from typing import Dict, List, Optional
import logging

from ..models.team import Team


class TeamIdentifier:
    """Manages team identification and mapping"""
    
    def __init__(self, mapping_file: Path = Path('input/config/team-name-mapping.yaml')):
        """
        Initialize TeamIdentifier
        
        Args:
            mapping_file: Path to team name mapping YAML file
        """
        self.mapping_file = mapping_file
        self.teams: Dict[str, Team] = {}
        self.logger = logging.getLogger(__name__)
        self._load_teams()
    
    def _load_teams(self):
        """Load teams from mapping file"""
        if not self.mapping_file.exists():
            self.logger.warning(f"Team mapping file not found: {self.mapping_file}")
            return
        
        try:
            with open(self.mapping_file, 'r') as f:
                config = yaml.safe_load(f)
                team_names = config.get('team_names', {})
                
                # team_names format: {canonical: variant}
                # We need to build Team objects with aliases
                canonical_to_variants: Dict[str, List[str]] = {}
                
                for canonical, variant in team_names.items():
                    canonical_norm = Team.normalize_name(canonical)
                    if canonical_norm not in canonical_to_variants:
                        canonical_to_variants[canonical_norm] = []
                    canonical_to_variants[canonical_norm].append(variant)
                
                # Create Team objects
                for canonical, aliases in canonical_to_variants.items():
                    team = Team(name=canonical, aliases=aliases)
                    self.teams[canonical] = team
                    
                self.logger.info(f"Loaded {len(self.teams)} teams from {self.mapping_file}")
        
        except Exception as e:
            self.logger.error(f"Error loading team mapping: {e}")
    
    def identify_team(self, text: str) -> Optional[Team]:
        """
        Identify a team from text
        
        Args:
            text: Text containing team name
            
        Returns:
            Team object if identified, None otherwise
        """
        if not text:
            return None
        
        normalized = Team.normalize_name(text)
        
        # Check direct match first
        if normalized in self.teams:
            return self.teams[normalized]
        
        # Check all teams for alias match
        for team in self.teams.values():
            if team.matches(text):
                return team
        
        return None
    
    def get_or_create_team(self, name: str) -> Team:
        """
        Get existing team or create a new one
        
        Args:
            name: Team name
            
        Returns:
            Team object
        """
        team = self.identify_team(name)
        if team:
            return team
        
        # Create new team
        normalized = Team.normalize_name(name)
        team = Team(name=normalized)
        self.teams[normalized] = team
        self.logger.info(f"Created new team: {normalized}")
        return team
    
    def get_all_teams(self) -> List[Team]:
        """Get all known teams"""
        return list(self.teams.values())
    
    def __len__(self) -> int:
        return len(self.teams)
