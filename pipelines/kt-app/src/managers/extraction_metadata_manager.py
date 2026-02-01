"""Manager for extraction metadata in metadata folder."""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List


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
        self.metadata_file = Path(f"layers/kt-app/metadata/{team_name}/extraction_metadata.json")
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
