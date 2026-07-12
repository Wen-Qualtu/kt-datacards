"""Integration test: compare the classified file sets produced by both tracks.

Run after both tracks have produced their classified PDFs for a team. The goal of
the merge design is that kt-app and warcom emit the SAME {team}-{type}-{name}.pdf
filenames, so downstream is source-agnostic and you can pick whichever source GW
updated.

Usage:
    python -m tools.compare_classified --teams kasrkin
    python -m tools.compare_classified                # all teams in classified/

This compares filename SETS only (presence), not PDF contents.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.utils import paths  # noqa: E402


def classified_for_track(track: str, team: str) -> set:
    """Derive the classified filename set a track would produce, from its structure."""
    import json
    from pipeline.utils import naming

    sf = paths.structure_file(track, team)
    if not sf.exists():
        return set()
    with open(sf, "r", encoding="utf-8") as f:
        structure = json.load(f)

    type_keys = [
        "datacards", "equipment", "faction_rules", "token_guide",
        "firefight_ploys", "operatives_selection", "strategy_ploys",
    ]
    names = set()
    for key in type_keys:
        card_type = naming.STRUCTURE_KEY_TO_TYPE.get(key, key)
        for entity in structure.get(key, []):
            cards = entity.get("cards", [])
            multi = len(cards) > 1
            for card in cards:
                base = naming.classified_name(team, card_type, entity.get("name") or "unknown")
                if multi:
                    base = f"{base}-{card['card_number']}"
                names.add(f"{base}.pdf")
    return names


def main() -> None:
    p = argparse.ArgumentParser(description="Compare classified sets across tracks")
    p.add_argument("--teams", help="comma-separated team slugs")
    args = p.parse_args()

    if args.teams:
        teams = [t.strip() for t in args.teams.split(",")]
    else:
        teams = sorted({
            f.stem.replace("-structure", "")
            for track in ("kt-app", "warcom")
            for f in paths.structure_dir(track).glob("*-structure.json")
        })

    exit_code = 0
    for team in teams:
        kt = classified_for_track("kt-app", team)
        wc = classified_for_track("warcom", team)
        only_kt = sorted(kt - wc)
        only_wc = sorted(wc - kt)
        shared = kt & wc

        status = "MATCH" if not only_kt and not only_wc else "DIFF"
        print(f"\n=== {team}: {status} (shared={len(shared)} kt={len(kt)} warcom={len(wc)}) ===")
        if only_kt:
            print(f"  only in kt-app ({len(only_kt)}):")
            for n in only_kt:
                print(f"    - {n}")
        if only_wc:
            print(f"  only in warcom ({len(only_wc)}):")
            for n in only_wc:
                print(f"    + {n}")
        if status == "DIFF":
            exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
