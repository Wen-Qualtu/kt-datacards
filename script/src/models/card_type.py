"""CardType enumeration for different types of Kill Team cards"""
from enum import Enum


class CardType(Enum):
    """Enumeration of Kill Team card types"""
    DATACARDS = "datacards"
    EQUIPMENT = "equipment"
    FACTION_RULES = "faction-rules"
    FIREFIGHT_PLOYS = "firefight-ploys"
    OPERATIVES = "operatives"
    STRATEGY_PLOYS = "strategy-ploys"
    
    @classmethod
    def from_string(card_type_class, value: str) -> 'CardType':
        """Convert string to CardType, handling common variations"""
        # Normalize the input
        normalized = value.lower().replace(" ", "-").replace("_", "-")
        
        # Handle plural variations
        if normalized.endswith("s") and not any(normalized == ct.value for ct in card_type_class):
            normalized = normalized[:-1]
        
        # Map common variations
        variations = {
            "datacard": card_type_class.DATACARDS,
            "firefight-ploy": card_type_class.FIREFIGHT_PLOYS,
            "strategy-ploy": card_type_class.STRATEGY_PLOYS,
            "operative": card_type_class.OPERATIVES,
            "faction-rule": card_type_class.FACTION_RULES,
        }
        
        if normalized in variations:
            return variations[normalized]
        
        # Try direct match
        for card_type in card_type_class:
            if card_type.value == normalized:
                return card_type
        
        raise ValueError(f"Unknown card type: {value}")
    
    def __str__(self) -> str:
        return self.value
