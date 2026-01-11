"""Datacard model representing an individual card"""
from pathlib import Path
from typing import Optional
from .team import Team
from .card_type import CardType


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
    
    def get_output_folder(self, base_dir: Path = Path("output")) -> Path:
        """Get the output folder for this datacard"""
        return self.team.get_output_folder(self.card_type, base_dir)
    
    def get_expected_front_filename(self) -> str:
        """Get the expected filename for the front image"""
        if self.card_name:
            return f"{self.card_name}_front.jpg"
        return f"{self.source_pdf.stem}_front.jpg"
    
    def get_expected_back_filename(self) -> str:
        """Get the expected filename for the back image"""
        if self.card_name:
            return f"{self.card_name}_back.jpg"
        return f"{self.source_pdf.stem}_back.jpg"
    
    def has_images(self) -> bool:
        """Check if both front and back images exist"""
        return (
            self._front_image is not None 
            and self._back_image is not None
            and self._front_image.exists()
            and self._back_image.exists()
        )
    
    def __str__(self) -> str:
        name = self.card_name or self.source_pdf.stem
        return f"{self.team.name}/{self.card_type.value}/{name}"
    
    def __repr__(self) -> str:
        return f"Datacard(team={self.team.name}, type={self.card_type.value}, name={self.card_name})"
