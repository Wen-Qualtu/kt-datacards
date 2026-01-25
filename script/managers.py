"""Data and metadata managers for card processing."""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


class TeamDataManager:
    """Manages card content data in output folder (team_data.json)."""
    
    def __init__(self, team_name: str, team_display_name: Optional[str] = None, 
                 faction: Optional[str] = None, army: Optional[str] = None):
        """
        Initialize TeamDataManager.
        
        Args:
            team_name: Team slug/identifier
            team_display_name: Human-readable team name
            faction: Faction name
            army: Army name (kept for backwards compatibility but not used in path)
        """
        self.team_name = team_name
        # Use V2 structure: output_v2/faction/team_name/team_data.json
        if faction:
            self.data_file = Path(f"output_v2/{faction}/{team_name}/team_data.json")
        else:
            # Fallback for when faction not provided during init
            self.data_file = Path(f"output_v2/{team_name}/team_data.json")
        self.logger = logging.getLogger(__name__)
        self.data = self._load_or_create()
        
        # Update team metadata if provided
        if team_display_name:
            self.data["team"]["display_name"] = team_display_name
        if faction:
            self.data["team"]["faction"] = faction
        if army:
            self.data["team"]["army"] = army
    
    def _load_or_create(self) -> Dict[str, Any]:
        """Load existing data or create new structure."""
        if self.data_file.exists():
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "team": {
                "name": self.team_name
            },
            "card_types": {},
            "processing_summary": {
                "total_cards": 0,
                "by_type": {}
            }
        }
    
    def add_card(self, card_type: str, card_name: str, has_back: bool, content: Dict[str, Any]):
        """
        Add card content data.
        
        Args:
            card_type: Type of card (datacards, strategy-ploys, etc.)
            card_name: Card identifier
            has_back: Whether card has a back side
            content: Card content dict (description, full_text, stats, etc.)
        """
        if card_type not in self.data["card_types"]:
            self.data["card_types"][card_type] = {}
        
        display_name = card_name.replace('-', ' ').title()
        
        self.data["card_types"][card_type][card_name] = {
            "card_name": card_name,
            "display_name": display_name,
            "has_back": has_back,
            "content": content
        }
        
        self.logger.debug(f"Added card data: {card_type}/{card_name}")
    
    def save(self):
        """Save data to file."""
        # Calculate processing_summary from actual card data
        self.data["processing_summary"] = {
            "total_cards": sum(len(cards) for cards in self.data["card_types"].values()),
            "by_type": {card_type: len(cards) for card_type, cards in self.data["card_types"].items()}
        }
        
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        self.logger.debug(f"Saved team data to {self.data_file}")


class ExtractionMetadataManager:
    """Manages ETL metadata in metadata folder (extraction_metadata.json)."""
    
    def __init__(self, team_name: str, team_display_name: Optional[str] = None):
        """
        Initialize ExtractionMetadataManager.
        
        Args:
            team_name: Team slug/identifier
            team_display_name: Human-readable team name
        """
        self.team_name = team_name
        self.metadata_file = Path(f"metadata/{team_name}/extraction_metadata.json")
        self.logger = logging.getLogger(__name__)
        self.metadata = self._load_or_create()
        
        # Track current run stats
        self._pdfs_processed = set()
        self._total_pages = 0
        self._errors = 0
        self._warnings = set()
        
        # Update team metadata if provided
        if team_display_name:
            self.metadata["team"]["display_name"] = team_display_name
        
        # Update extraction date
        self.metadata["team"]["extraction_date"] = datetime.now().isoformat()
    
    def _load_or_create(self) -> Dict[str, Any]:
        """Load existing metadata or create new structure."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "team": {
                "name": self.team_name,
                "extraction_date": datetime.now().isoformat()
            },
            "card_types": {},
            "processing_summary": {
                "pdfs_processed": 0,
                "total_pages_processed": 0,
                "cards_extracted": 0,
                "extraction_errors": 0,
                "warnings": []
            }
        }
    
    def add_card_metadata(self, card_type: str, card_name: str, page_num: int,
                          extraction: Dict[str, Any], output: Dict[str, Any]):
        """
        Add card extraction and output metadata.
        
        Args:
            card_type: Type of card (datacards, strategy-ploys, etc.)
            card_name: Card identifier
            page_num: Page number in source PDF
            extraction: Extraction details (source_pdf, extracted_at, etc.)
            output: Output file paths (front_image, back_image, etc.)
        """
        if card_type not in self.metadata["card_types"]:
            self.metadata["card_types"][card_type] = {}
        
        self.metadata["card_types"][card_type][card_name] = {
            "card_name": card_name,
            "page_num": page_num,
            "extraction": extraction,
            "output": output
        }
        
        self.logger.debug(f"Added extraction metadata: {card_type}/{card_name}")
    
    def add_pdf_processed(self, pdf_path: str, pages_processed: int):
        """
        Track that a PDF was processed.
        
        Args:
            pdf_path: Path to the processed PDF
            pages_processed: Number of pages processed
        """
        self._pdfs_processed.add(pdf_path)
        self._total_pages += pages_processed
        self.logger.debug(f"PDF processed: {pdf_path} ({pages_processed} pages)")
    
    def add_warning(self, warning: str):
        """
        Add a warning message.
        
        Args:
            warning: Warning message
        """
        self._warnings.add(warning)
        self.logger.debug(f"Warning added: {warning}")
    
    def add_error(self):
        """Increment error count."""
        self._errors += 1
    
    def save(self):
        """Save metadata to file."""
        # Calculate processing_summary from actual data and tracked stats
        self.metadata["processing_summary"] = {
            "pdfs_processed": len(self._pdfs_processed),
            "total_pages_processed": self._total_pages,
            "cards_extracted": sum(len(cards) for cards in self.metadata["card_types"].values()),
            "extraction_errors": self._errors,
            "warnings": sorted(list(self._warnings))
        }
        
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
        self.logger.debug(f"Saved extraction metadata to {self.metadata_file}")
