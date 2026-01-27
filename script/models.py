"""Core data models for Kill Team datacard processing"""
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any


class CardType(Enum):
    """Enumeration of Kill Team card types"""
    DATACARDS = "datacards"
    EQUIPMENT = "equipment"
    FACTION_RULES = "faction-rules"
    FIREFIGHT_PLOYS = "firefight-ploys"
    OPERATIVES = "operative-selection"
    STRATEGY_PLOYS = "strategy-ploys"
    
    @classmethod
    def from_string(cls, value: str) -> 'CardType':
        """Convert string to CardType, handling common variations"""
        # Normalize the input
        normalized = value.lower().replace(" ", "-").replace("_", "-")
        
        # Handle plural variations
        if normalized.endswith("s") and not any(normalized == ct.value for ct in cls):
            normalized = normalized[:-1]
        
        # Map common variations
        variations = {
            "datacard": cls.DATACARDS,
            "firefight-ploy": cls.FIREFIGHT_PLOYS,
            "strategy-ploy": cls.STRATEGY_PLOYS,
            "operative": cls.OPERATIVES,
            "faction-rule": cls.FACTION_RULES,
        }
        
        if normalized in variations:
            return variations[normalized]
        
        # Try direct match
        for card_type in cls:
            if card_type.value == normalized:
                return card_type
        
        raise ValueError(f"Unknown card type: {value}")
    
    def __str__(self) -> str:
        return self.value


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
    
    def get_archive_path(self, base_dir: Path = Path("archive")) -> Path:
        """Get the path for archived PDFs for this team"""
        return base_dir / self.name
    
    def get_output_path(self, base_dir: Path = Path("output_v2")) -> Path:
        """Get the path for output images for this team"""
        if self.faction:
            return base_dir / self.faction / self.name
        return base_dir / self.name
    
    def __str__(self) -> str:
        return self.name
    
    def __repr__(self) -> str:
        return f"Team(name='{self.name}', aliases={self.aliases})"
    
    def __eq__(self, other):
        if not isinstance(other, Team):
            return False
        return self.name == other.name
    
    def __hash__(self):
        return hash(self.name)


class Datacard:
    """Represents an individual datacard with its source and output information"""
    
    def __init__(
        self,
        source_pdf: Path,
        team: Team,
        card_type: CardType,
        card_name: Optional[str] = None,
        description: Optional[str] = None
    ):
        """
        Initialize a Datacard
        
        Args:
            source_pdf: Path to the source PDF file
            team: The team this card belongs to
            card_type: Type of card (datacard, equipment, etc.)
            card_name: Optional name of the card (extracted from PDF)
            description: Optional description text extracted from the card
        """
        self.source_pdf = source_pdf
        self.team = team
        self.card_type = card_type
        self.card_name = card_name
        self.description = description
        self._front_image: Optional[Path] = None
        self._back_image: Optional[Path] = None
    
    @property
    def front_image(self) -> Optional[Path]:
        """Get the path to the front image"""
        return self._front_image
    
    @front_image.setter
    def front_image(self, path: Path):
        """Set the path to the front image"""
        self._front_image = path
    
    @property
    def back_image(self) -> Optional[Path]:
        """Get the path to the back image"""
        return self._back_image
    
    @back_image.setter
    def back_image(self, path: Path):
        """Set the path to the back image"""
        self._back_image = path
    
    def get_image_stem(self) -> str:
        """Generate a filename stem for this card's images"""
        stem_parts = [
            self.team.name,
            self.card_type.value
        ]
        
        if self.card_name:
            # Clean the card name for use in filename
            clean_name = self.card_name.lower().replace(" ", "-")
            stem_parts.append(clean_name)
        
        return "_".join(stem_parts)
    
    def get_output_folder(self) -> Path:
        """Get the output folder for this card's images"""
        from config import OUTPUT_V2_DIR
        if self.team.faction:
            return OUTPUT_V2_DIR / self.team.faction / self.team.name / self.card_type.value
        return OUTPUT_V2_DIR / self.team.name / self.card_type.value
    
    def get_expected_front_filename(self) -> str:
        """Get the expected front image filename"""
        if not self.card_name:
            raise ValueError(
                f"Cannot generate filename: card_name is missing for {self.source_pdf}. "
                f"Card name extraction failed - check PDF or extraction logic."
            )
        # Use the extracted card name
        clean_name = self.card_name.lower().replace(" ", "-")
        return f"{self.team.name}-{clean_name}_front.jpg"
    
    def get_expected_back_filename(self) -> str:
        """Get the expected back image filename"""
        if not self.card_name:
            raise ValueError(
                f"Cannot generate filename: card_name is missing for {self.source_pdf}. "
                f"Card name extraction failed - check PDF or extraction logic."
            )
        # Use the extracted card name
        clean_name = self.card_name.lower().replace(" ", "-")
        return f"{self.team.name}-{clean_name}_back.jpg"
    
    def __str__(self) -> str:
        return f"{self.team.name}/{self.card_type.value}"
    
    def __repr__(self) -> str:
        return f"Datacard(team={self.team.name}, type={self.card_type.value}, name={self.card_name})"
