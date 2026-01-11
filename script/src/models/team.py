"""Team model representing a Kill Team faction"""
from pathlib import Path
from typing import List, Optional, Dict, Any
from .card_type import CardType


class Team:
    """Represents a Kill Team faction with its metadata and paths"""
    
    def __init__(
        self,
        name: str,
        aliases: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        faction: Optional[str] = None,
        army: Optional[str] = None
    ):
        """
        Initialize a Team
        
        Args:
            name: Canonical team name (normalized, lowercase with hyphens)
            aliases: List of alternative names for this team
            metadata: Additional team metadata
            faction: Faction (imperium, chaos, xenos)
            army: Army within faction (e.g., space-marines, orks)
        """
        self.name = name
        self.aliases = aliases or []
        self.metadata = metadata or {}
        self.faction = faction
        self.army = army
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize a team name to canonical format"""
        return name.lower().replace(" ", "-").replace("_", "-")
    
    def matches(self, text: str) -> bool:
        """Check if text matches this team's name or aliases"""
        normalized = self.normalize_name(text)
        if normalized == self.name:
            return True
        return any(normalized == self.normalize_name(alias) for alias in self.aliases)
    
    def get_processed_path(self, base_dir: Path = Path("processed")) -> Path:
        """Get the path for processed PDFs for this team"""
        return base_dir / self.name
    
    def get_output_path(self, base_dir: Path = Path("output")) -> Path:
        """Get the base output path for this team"""
        return base_dir / self.name
    
    def get_output_folder(self, card_type: CardType, base_dir: Path = Path("output")) -> Path:
        """Get the output folder for a specific card type"""
        return self.get_output_path(base_dir) / card_type.value
    
    def get_v2_output_path(self, base_dir: Path = Path("output_v2")) -> Path:
        """Get the v2 output path with faction/army hierarchy"""
        if self.faction and self.army:
            return base_dir / self.faction / self.army / self.name
        else:
            # Fallback to uncategorized if metadata missing
            return base_dir / "uncategorized" / self.name
    
    def get_v2_output_folder(self, card_type: CardType, base_dir: Path = Path("output_v2")) -> Path:
        """Get the v2 output folder for a specific card type"""
        # Convert 'operatives' to 'operative-selection' for v2
        folder_name = "operative-selection" if card_type.value == "operatives" else card_type.value
        return self.get_v2_output_path(base_dir) / folder_name
    
    def get_archive_path(self, base_dir: Path = Path("archive")) -> Path:
        """Get the archive path for this team"""
        return base_dir / self.name
    
    def __str__(self) -> str:
        return self.name
    
    def __repr__(self) -> str:
        return f"Team(name='{self.name}', aliases={self.aliases})"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Team):
            return False
        return self.name == other.name
    
    def __hash__(self) -> int:
        return hash(self.name)
