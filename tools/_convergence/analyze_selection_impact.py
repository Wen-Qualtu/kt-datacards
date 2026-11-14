"""Ad-hoc analysis: which teams/operatives are affected by the two selection fixes.

1. exclusive-sets: `_derive_exclusive_sets` now also matches the
   "Or one option from each of the following:" phrasing.
2. nested-or expansion: `_build_selection_for_gmnotes` splits a " or " sub-choice
   inside a ';'/'and' option into separate radio options.

Reads every output/*/data/*-team-data.json and reports operatives that gain
exclusive_sets and/or nested-or expansion. Does NOT modify any artifact.
"""
import json
import re
from pathlib import Path

from pipeline.steps.tts_impl import (
    _derive_exclusive_sets,
    _build_selection_for_gmnotes,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "output"


def has_nested_or(selection_groups) -> list:
    """Return option labels that expand (a ' or ' inside a ';'/'and' part)."""
    hits = []
    for group in selection_groups:
        for label in group:
            parts = [p.strip() for p in re.split(r"\s*;\s*|\s+and\s+", label) if p.strip()]
            multi = [p for p in parts if re.search(r"\s+or\s+", p)]
            # A nested-or only matters when it sits beside a required part
            # (';'/'and') OR when the part itself has both an 'or' and would have
            # been kept whole before (because the whole label had a ';').
            if multi and (len(parts) > 1 or ";" in label):
                hits.append(label)
    return hits


def main():
    excl_hits = []
    nested_hits = []
    for data_file in sorted(OUTPUT.glob("*/data/*-team-data.json")):
        team = data_file.parent.parent.name
        try:
            team_data = json.loads(data_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"!! {team}: unreadable ({e})")
            continue
        osel = team_data.get("operatives_selection") or []
        if not osel:
            continue
        sel_text = osel[0].get("text", "") or ""
        selection = osel[0].get("selection", {}) or {}
        # weapons per datacard name for matching
        weapons_by_name = {
            (dc.get("name", "") or "").upper(): dc.get("weapons", [])
            for dc in team_data.get("datacards", [])
        }
        for op_name, groups in selection.items():
            if not groups or not isinstance(groups, list):
                continue
            # exclusive sets (new phrasing included)
            es = _derive_exclusive_sets(op_name, sel_text, len(groups))
            if es:
                excl_hits.append((team, op_name, es, len(groups)))
            # nested-or expansion
            labels = has_nested_or(groups)
            if labels:
                nested_hits.append((team, op_name, labels))

    print("=" * 70)
    print("EXCLUSIVE-SETS (operatives that now get a mutually-exclusive split)")
    print("=" * 70)
    if not excl_hits:
        print("  (none)")
    for team, op, es, n in excl_hits:
        print(f"  {team:24} {op:32} sets={es} groups={n}")

    print()
    print("=" * 70)
    print("NESTED-OR EXPANSION (options that split into multiple radio choices)")
    print("=" * 70)
    if not nested_hits:
        print("  (none)")
    for team, op, labels in nested_hits:
        print(f"  {team:24} {op}")
        for lb in labels:
            print(f"        - {lb}")


if __name__ == "__main__":
    main()
