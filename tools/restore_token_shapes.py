"""Restore authoritative token SHAPE metadata into the sandbox team-config.

The earlier strip (tools/strip_token_config.py) removed both the ``tokens_ready``
skip flag AND the ``tokens`` list. Token *names* are regenerated from the PDF, but
token *shape* (operative vs round vs octagon/diamond) is design metadata that
cannot be reliably auto-derived from contour circularity -- auto-detection
misclassifies ~22 tokens (operative<->round). ``_get_token_shape`` looks the shape
up from config ``tokens[].shape`` by name, so restoring the list (name/shape/type
only) makes shape classification authoritative again.

This does NOT re-add ``tokens_ready`` -- extraction still runs from scratch; the
list only feeds shape lookup.

Operates ONLY on the sandbox copy: new_implementation/config/team-config.yaml,
sourcing shapes from the repo-root config/team-config.yaml.

Run:  python tools/restore_token_shapes.py   (from new_implementation/)
"""
from __future__ import annotations

from pathlib import Path

import yaml

SANDBOX = Path(__file__).resolve().parents[1] / "config" / "team-config.yaml"
ROOT = Path(__file__).resolve().parents[2] / "config" / "team-config.yaml"


def _clean_tokens(tokens: list) -> list:
    """Keep only design fields (name/shape/type); drop any baked extras."""
    cleaned = []
    for tok in tokens:
        if not isinstance(tok, dict):
            continue
        entry = {}
        for key in ("name", "shape", "type"):
            if key in tok:
                entry[key] = tok[key]
        if entry:
            cleaned.append(entry)
    return cleaned


def main() -> None:
    sand = yaml.safe_load(SANDBOX.read_text(encoding="utf-8"))
    root = yaml.safe_load(ROOT.read_text(encoding="utf-8"))
    sand_teams = sand.get("teams", {})
    root_teams = root.get("teams", {})

    restored = 0
    total_tokens = 0
    for team, rcfg in root_teams.items():
        if not isinstance(rcfg, dict):
            continue
        rtokens = rcfg.get("tokens")
        if not rtokens:
            continue
        scfg = sand_teams.get(team)
        if not isinstance(scfg, dict):
            print(f"  ! sandbox missing team {team}; skipped")
            continue
        cleaned = _clean_tokens(rtokens)
        scfg["tokens"] = cleaned
        scfg.pop("tokens_ready", None)  # ensure the skip flag stays gone
        restored += 1
        total_tokens += len(cleaned)

    SANDBOX.write_text(
        yaml.safe_dump(sand, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )

    check = SANDBOX.read_text(encoding="utf-8")
    print(f"teams restored (tokens)  : {restored}")
    print(f"token entries written    : {total_tokens}")
    print(f"remaining 'tokens_ready' : {check.count('tokens_ready')}")


if __name__ == "__main__":
    main()
