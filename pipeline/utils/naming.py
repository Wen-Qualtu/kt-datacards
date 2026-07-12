"""Canonical naming helpers.

Slugs are lowercase, ASCII-only, hyphen-separated. Matches the production
convention (``roster_slug`` strips non-ASCII, see copilot-instructions).
Card ``type`` vocabulary is still being locked — see design open questions.
"""
from __future__ import annotations

import re


def slug(value: str) -> str:
    """Normalize a name/title to a lowercase, ASCII, hyphenated slug."""
    s = value.strip().lower()
    s = re.sub(r"[^\x00-\x7f]", "", s)   # strip non-ASCII (ô, â, ', non-breaking hyphen…)
    s = re.sub(r"['.]", "", s)           # drop apostrophes/periods (emperor's→emperors, C.A.T.→cat)
    s = re.sub(r"[^a-z0-9]+", "-", s)    # collapse runs of non-alphanumerics to a hyphen
    return s.strip("-")


# Canonical card-type vocabulary (hyphen + singular). LOCKING IN DESIGN — placeholder.
CARD_TYPES = (
    "datacard",
    "equipment",
    "faction-rule",
    "strategy-ploy",
    "firefight-ploy",
    "operatives-selection",
    "token-guide",
)

# Map structure-manifest type keys (plural, underscore) to the canonical
# classified card-type slug (singular, hyphen).
STRUCTURE_KEY_TO_TYPE = {
    "datacards": "datacard",
    "equipment": "equipment",
    "faction_rules": "faction-rule",
    "token_guide": "token-guide",
    "firefight_ploys": "firefight-ploy",
    "operatives_selection": "operatives-selection",
    "strategy_ploys": "strategy-ploy",
}


def classified_name(team: str, card_type: str, name: str) -> str:
    """{team}-{type}-{name} (no .pdf, no front/back postfix)."""
    return f"{slug(team)}-{slug(card_type)}-{slug(name)}"
