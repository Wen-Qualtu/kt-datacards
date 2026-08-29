"""Thin loader for the shared ``config/team-config.yaml`` ``teams`` map.

Several downstream steps (box texture, dice, tokens, tts) need the raw per-team
config (canonical name, token definitions, dice colours, guids). Loaded once and
cached so repeated calls within a run are cheap.
"""
from __future__ import annotations

import re
import threading
from functools import lru_cache
from typing import Dict, Iterable, Tuple

import yaml

from . import paths

# Serialises the surgical config write so parallel team workers don't clobber
# team-config.yaml (a load-modify-write of the same file).
_CONFIG_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def load_teams() -> Dict[str, dict]:
    """Return the ``teams`` mapping from config/team-config.yaml (slug -> data)."""
    with open(paths.TEAM_CONFIG, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("teams", {}) or {}


def team_data(team: str) -> dict:
    """Config data for one team (empty dict if the team is unknown)."""
    return load_teams().get(team, {}) or {}


def asset_ready(team: str, asset: str) -> bool:
    """True if this team's ``{asset}_ready`` flag is set (asset in artwork/tokens/dice).

    Default is False: a team WITHOUT the flag is (re)generated. The owning step
    sets the flag once the asset is complete, so later runs skip it. ``--force``
    bypasses the flag.
    """
    return bool(team_data(team).get(f"{asset}_ready", False))


def mark_ready(pairs: Iterable[Tuple[str, str]]) -> int:
    """Set ``{asset}_ready: true`` in each team's config block. ``pairs`` = (team, asset).

    Writes the flag directly into config/team-config.yaml with a surgical text
    edit (comments + formatting preserved) rather than a YAML round-trip. Adds the
    key right under ``  {team}:`` when absent, or updates it in place. Thread-safe;
    invalidates the cache. Returns the number of flags written.
    """
    pairs = [(t, a) for t, a in pairs]
    if not pairs:
        return 0
    with _CONFIG_LOCK:
        lines = paths.TEAM_CONFIG.read_text(encoding="utf-8").splitlines(keepends=True)
        changed = 0
        for team, asset in pairs:
            key = f"{asset}_ready"
            ti = next((i for i, ln in enumerate(lines)
                       if re.match(rf"^  {re.escape(team)}:\s*$", ln)), None)
            if ti is None:
                continue
            found = False
            j = ti + 1
            while j < len(lines) and not re.match(r"^ {0,2}[A-Za-z]", lines[j]):
                if re.match(rf"^    {re.escape(key)}:", lines[j]):
                    if lines[j].strip() != f"{key}: true":
                        lines[j] = f"    {key}: true\n"
                        changed += 1
                    found = True
                    break
                j += 1
            if not found:
                lines.insert(ti + 1, f"    {key}: true\n")
                changed += 1
        if changed:
            paths.TEAM_CONFIG.write_text("".join(lines), encoding="utf-8")
    load_teams.cache_clear()
    return changed


def canonical_name(team: str) -> str:
    """Canonical display name, falling back to a title-cased slug."""
    return team_data(team).get("canonical_name") or team.replace("-", " ").title()
