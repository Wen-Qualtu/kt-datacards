"""Shared helpers for kt-datacards pre-merge check tools."""
from __future__ import annotations

import json
import re
from pathlib import Path

# This file lives at .github/skills/kt-datacards/tools/_common.py
PROJECT_ROOT = Path(__file__).resolve().parents[4]
OUTPUT_DIR = PROJECT_ROOT / "output"
CLASSIFIED_DIR = PROJECT_ROOT / "layers" / "kt-app" / "classified"


def team_dirs() -> list[Path]:
    """Team subdirectories under output/, excluding shared content."""
    return [
        d for d in sorted(OUTPUT_DIR.iterdir())
        if d.is_dir() and d.name != "_generic-tts-objects"
    ]


def team_display(slug: str) -> str:
    return slug.replace("-", " ").title()


def digits(s: str | None, n: int = 14) -> int:
    """Truncate a timestamp string to its first 14 digits (YYYYMMDDHHMMSS)
    and return as int. Matches the comparison logic in the TTS update Lua."""
    return int(re.sub(r"[^\d]", "", s or "")[:n] or "0")


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_object_urls(team: str) -> dict | None:
    return load_json(OUTPUT_DIR / team / f"{team}-object-urls.json")


def load_bag(team: str) -> dict | None:
    return load_json(OUTPUT_DIR / team / "tts_objects" / f"{team_display(team)}.json")


def bag_last_card_update(team: str) -> str | None:
    bag = load_bag(team)
    if not bag:
        return None
    state_str = bag.get("LuaScriptState", "")
    if not state_str:
        return None
    m = re.search(r'"lastCardUpdate":\s*"([^"]+)"', state_str)
    return m.group(1) if m else None


def iter_output_files(suffixes: tuple[str, ...] = (".json",)) -> list[Path]:
    """All committed output files matching the given suffixes."""
    return sorted(p for p in OUTPUT_DIR.rglob("*") if p.suffix in suffixes)
