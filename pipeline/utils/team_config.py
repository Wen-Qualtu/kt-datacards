"""Thin loader for the shared ``config/team-config.yaml`` ``teams`` map.

Several downstream steps (box texture, dice, tokens, tts) need the raw per-team
config (canonical name, token definitions, dice colours, guids). Loaded once and
cached so repeated calls within a run are cheap.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict

import yaml

from . import paths


@lru_cache(maxsize=1)
def load_teams() -> Dict[str, dict]:
    """Return the ``teams`` mapping from config/team-config.yaml (slug -> data)."""
    with open(paths.TEAM_CONFIG, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("teams", {}) or {}


def team_data(team: str) -> dict:
    """Config data for one team (empty dict if the team is unknown)."""
    return load_teams().get(team, {}) or {}


def canonical_name(team: str) -> str:
    """Canonical display name, falling back to a title-cased slug."""
    return team_data(team).get("canonical_name") or team.replace("-", " ").title()
