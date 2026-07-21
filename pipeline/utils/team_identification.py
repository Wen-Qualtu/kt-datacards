"""Team identification + card-type detection.

Ported from pipelines/kt-app/steps/1_process_pdfs.py (Team, TeamIdentifier,
CardType, and the content-based identification logic). Identification is by PDF
*content*, never filename — the kt-app raw inputs are GUID-named.
"""
from __future__ import annotations

import logging
import re
from enum import Enum
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
import yaml

from . import paths

logger = logging.getLogger(__name__)


class CardType(Enum):
    DATACARDS = "datacards"
    FACTION_RULES = "faction-rules"
    TOKEN_GUIDE = "token-guide"
    OPERATIVES = "operatives-selection"
    EQUIPMENT = "equipment"
    STRATEGY_PLOYS = "strategy-ploys"
    FIREFIGHT_PLOYS = "firefight-ploys"


def normalize_name(name: str) -> str:
    """Normalize a team name to slug format."""
    normalized = name.lower()
    normalized = re.sub(r"[\s_]+", "-", normalized)
    normalized = re.sub(r"[^a-z0-9\-]", "", normalized)
    normalized = re.sub(r"-+", "-", normalized)
    return normalized.strip("-")


class Team:
    def __init__(self, name: str, aliases=None, faction: str = None, metadata=None):
        self.name = name
        self.aliases = aliases or []
        self.faction = faction
        self.metadata = metadata or {}

    def matches(self, text: str) -> bool:
        normalized = normalize_name(text)
        if normalized == self.name:
            return True
        return any(normalize_name(a) == normalized for a in self.aliases)


class TeamIdentifier:
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or paths.TEAM_CONFIG
        self.teams: dict[str, Team] = {}
        self._load_teams()

    def _load_teams(self):
        if not self.config_path.exists():
            logger.warning(f"Config not found: {self.config_path}")
            return
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        for team_key, team_data in (config.get("teams", {}) or {}).items():
            key = normalize_name(team_key)
            self.teams[key] = Team(
                name=key,
                aliases=(team_data or {}).get("aliases", []),
                faction=(team_data or {}).get("faction"),
                metadata=team_data or {},
            )
        logger.info(f"Loaded {len(self.teams)} teams from config")

    def identify_team(self, text: str) -> Optional[Team]:
        if not text:
            return None
        normalized = normalize_name(text)
        if normalized in self.teams:
            return self.teams[normalized]
        for team in self.teams.values():
            if team.matches(text):
                return team
        return None
