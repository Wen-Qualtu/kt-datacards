"""Check: every entry in every object-urls.json carries a `hash` field.

Without `hash`, the next step 7 run falls back to git-HEAD bootstrap detection,
which is slow and can churn URLs on partial-state working trees. Once a
baseline is committed with hashes, runs stay stable.

Exits 1 if any entry is missing `hash`; 0 otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import load_object_urls, team_dirs


def main() -> int:
    missing: list[tuple[str, str]] = []
    checked = 0
    for td in team_dirs():
        team = td.name
        urls = load_object_urls(team)
        if urls is None:
            continue
        checked += 1
        box = urls.get("box") or {}
        if "hash" not in box:
            missing.append((team, "box"))
        for o in urls.get("objects", []) or []:
            if "hash" not in o:
                missing.append((team, f"{o.get('type')}/{o.get('name')}"))

    print(f"Checked {checked} teams")
    if not missing:
        print("PASS  All object-urls entries carry a `hash` field")
        return 0

    print(f"FAIL  {len(missing)} entries missing `hash`:")
    for team, key in missing[:30]:
        print(f"  {team}: {key}")
    if len(missing) > 30:
        print(f"  ... and {len(missing) - 30} more")
    print()
    print("Fix: run step 7 for those teams to populate hashes:")
    print("  python pipelines/kt-app/steps/7_generate_tts_objects.py --teams <team>")
    return 1


if __name__ == "__main__":
    sys.exit(main())
