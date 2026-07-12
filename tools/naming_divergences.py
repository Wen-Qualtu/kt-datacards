"""List card-name divergences between the new pipeline output and root output.

For every team + card-type folder, compare the set of card base-names (stripping
``-front``/``-back``) between ``new_implementation/output`` and root ``output``.
Emit a markdown report of names that exist only in one side — these are the
(designed) naming divergences, dominated by multi-card faction rules and ploys.

Run:  python -m tools.naming_divergences   (from new_implementation/)
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]           # new_implementation/
NEW_OUTPUT = ROOT / "output"
ROOT_OUTPUT = ROOT.parent / "output"                 # repo root output/
REPORT = ROOT / "_naming_divergences.md"


def base_names(card_type_dir: Path) -> set[str]:
    names: set[str] = set()
    if not card_type_dir.exists():
        return names
    for f in card_type_dir.glob("*.jpg"):
        n = f.stem
        if n.endswith("-front"):
            n = n[:-6]
        elif n.endswith("-back"):
            n = n[:-5]
        names.add(n)
    return names


def main() -> None:
    teams = sorted(
        d.name for d in NEW_OUTPUT.iterdir()
        if d.is_dir() and (d / "cards").exists()
    )

    lines: list[str] = [
        "# Card-name divergences: new pipeline vs root output",
        "",
        "Per team + card-type, base card names (front/back stripped) present on only one side.",
        "These are the designed slug-vs-display naming divergences (decision: keep slugs).",
        "",
    ]
    total_new_only = total_root_only = 0

    for team in teams:
        new_cards = NEW_OUTPUT / team / "cards"
        root_cards = ROOT_OUTPUT / team / "cards"
        if not root_cards.exists():
            continue
        card_types = sorted(
            {d.name for d in new_cards.iterdir() if d.is_dir()}
            | {d.name for d in root_cards.iterdir() if d.is_dir()}
        )
        team_blocks: list[str] = []
        for ct in card_types:
            n = base_names(new_cards / ct)
            r = base_names(root_cards / ct)
            new_only = sorted(n - r)
            root_only = sorted(r - n)
            if not new_only and not root_only:
                continue
            total_new_only += len(new_only)
            total_root_only += len(root_only)
            team_blocks.append(f"- **{ct}**")
            for name in new_only:
                team_blocks.append(f"  - NEW-only: `{name}`")
            for name in root_only:
                team_blocks.append(f"  - ROOT-only: `{name}`")
        if team_blocks:
            lines.append(f"## {team}")
            lines.extend(team_blocks)
            lines.append("")

    lines.insert(
        4,
        f"**Totals:** NEW-only names = {total_new_only}, ROOT-only names = {total_root_only}\n",
    )
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}")
    print(f"NEW-only={total_new_only} ROOT-only={total_root_only}")


if __name__ == "__main__":
    main()
