"""Manager for card content data in output folder."""

import json
import logging
from pathlib import Path
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
        
        # Update summary
        self.data["processing_summary"]["total_cards"] += 1
        if card_type not in self.data["processing_summary"]["by_type"]:
            self.data["processing_summary"]["by_type"][card_type] = 0
        self.data["processing_summary"]["by_type"][card_type] += 1
        
        self.logger.debug(f"Added card data: {card_type}/{card_name}")
    
    def save(self):
        """Save data to file."""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        self.logger.debug(f"Saved team data to {self.data_file}")
