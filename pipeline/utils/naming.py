"""Canonical naming helpers.

Slugs are lowercase, ASCII-only, hyphen-separated. Non-ASCII letters are
transliterated to their closest ASCII form (ô→o, â→a) so accented operative
names keep their letters in filenames/URLs (``DÔZR`` → ``dozr``).
"""
from __future__ import annotations

import re
import unicodedata


def slug(value: str) -> str:
    """Normalize a name/title to a lowercase, ASCII, hyphenated slug.

    Non-ASCII letters are *transliterated* to their closest ASCII form via NFKD
    decomposition (ô→o, â→a, é→e) rather than dropped, so accented operative
    names keep their letters: ``DÔZR`` → ``dozr`` (not ``dzr``), ``LOKÂTR`` →
    ``lokatr``. Combining marks, curly quotes and other non-ASCII punctuation
    still fall away.
    """
    s = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    s = s.strip().lower()
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
