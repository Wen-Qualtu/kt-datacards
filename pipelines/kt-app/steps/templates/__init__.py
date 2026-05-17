"""TTS object templates for Kill Team datacards"""

# Export template functions
from .tts_templates import (
    create_single_card,
    create_deck,
    create_bag,
    create_custom_dice,
    generate_guid,
    get_team_guid
)

__all__ = [
    'create_single_card',
    'create_deck',
    'create_bag',
    'create_custom_dice',
    'generate_guid',
    'get_team_guid'
]
