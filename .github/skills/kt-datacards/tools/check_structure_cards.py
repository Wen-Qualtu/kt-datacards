"""Check: every datacards operative in structure.json has a corresponding front/back image.

Catches step-2 vs. step-4 drift (operative classified but image not generated, or
vice versa). For paired entries (type='both'), both front and back must exist.

Slugs are matched by stripping common punctuation and lowercasing both sides,
so unicode-bearing names (Hearthkyn DÔZR, SHAS'UI PATHFINDER, etc.) compare
equal to their generated filenames without depending on an exact slug formula.

Exits 1 on drift; 0 otherwise.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import CLASSIFIED_DIR, OUTPUT_DIR, load_json


def normalize(s: str) -> str:
    """Lowercase + drop accents + collapse all non-alphanumerics into nothing.

    `HEARTHKYN DÔZR` and `hearthkyn-dôzr` both normalize to `hearthkyndozr`,
    so we can match an entity name against a filename stem regardless of which
    slugification step 4 picked.
    """
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def main() -> int:
    drift: list[tuple[str, str, str]] = []
    checked_teams = 0
    for team_dir in sorted(CLASSIFIED_DIR.iterdir()):
        if not team_dir.is_dir():
            continue
        team = team_dir.name
        data = load_json(team_dir / "structure.json")
        if not data:
            continue
        checked_teams += 1
        cards_dir = OUTPUT_DIR / team / "cards" / "datacards"
        if not cards_dir.exists():
            for entity in data.get("datacards", []) or []:
                drift.append((team, entity.get("name", ""), "no datacards directory"))
            continue

        # Index available card files by normalized stem (without -front/-back suffix)
        available: dict[str, set[str]] = {}
        for f in cards_dir.glob("*.jpg"):
            stem = f.stem
            for side in ("-front", "-back"):
                if stem.endswith(side):
                    base = stem[: -len(side)]
                    available.setdefault(normalize(base), set()).add(side[1:])
                    break

        for entity in data.get("datacards", []) or []:
            name = entity.get("name", "")
            key = normalize(name)
            subcards = entity.get("cards", []) or []
            multi = len(subcards) > 1
            for idx, sub in enumerate(subcards, start=1):
                t = sub.get("type")
                want = []
                if t in ("front", "both"):
                    want.append("front")
                if t in ("back", "both"):
                    want.append("back")
                # Own-cards groups produce per-subcard slugs `{name}-card{N}`;
                # single-card entities use the bare `{name}` slug.
                lookup_key = f"{key}card{idx}" if multi else key
                sides_present = available.get(lookup_key, set())
                for side in want:
                    if side not in sides_present:
                        drift.append((team, name, f"missing {side}.jpg (looked up key `{lookup_key}`)"))

    print(f"Checked {checked_teams} teams")
    if not drift:
        print("PASS  Every structure.json datacard entity has its expected card image(s)")
        return 0

    print(f"FAIL  {len(drift)} drift(s):")
    for team, name, why in drift[:30]:
        print(f"  {team} / {name}: {why}")
    if len(drift) > 30:
        print(f"  ... and {len(drift) - 30} more")
    print()
    print("Fix: re-run step 4 for the affected team(s):")
    print("  python pipelines/kt-app/steps/4_extract_card_images.py --teams <team> --force")
    return 1


if __name__ == "__main__":
    sys.exit(main())
