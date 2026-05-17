"""Team identification and management"""
import yaml
from pathlib import Path
from typing import Dict, List, Optional
import logging

from ..models.team import Team


class TeamIdentifier:
    """Manages team identification and mapping"""
    
    def __init__(self, mapping_file: Path = Path('config/team-config.yaml')):
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
                teams_config = config.get('teams', {})
                
                # Create Team objects from the teams configuration
                for team_key, team_data in teams_config.items():
                    team_key_norm = Team.normalize_name(team_key)
                    
                    # Get aliases list (may be empty)
                    aliases = team_data.get('aliases', [])
                    
                    team = Team(
                        name=team_key_norm,
                        aliases=aliases,
                        faction=team_data.get('faction'),
                        army=team_data.get('army'),
                        metadata=team_data
                    )
                    self.teams[team_key_norm] = team
                    
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
        
        # If no match found in mapping, fail explicitly
        self.logger.error(
            f"FAILED: Team '{text}' (normalized: '{normalized}') not found in config. "
            f"Add team to config/team-config.yaml before processing."
        )
        return None
    
    def get_or_create_team(self, name: str) -> Optional[Team]:
        """
        Get existing team (no longer creates teams)
        
        Args:
            name: Team name
            
        Returns:
            Team object if found, None otherwise
        """
        team = self.identify_team(name)
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
