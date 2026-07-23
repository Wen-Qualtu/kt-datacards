"""Check: bag.lastCardUpdate >= max(obj-urls.box.modified, obj-urls.objects[].modified).

If any team fails, TTS will perpetually flag "update available" because the
downloaded bag still carries the older lastCardUpdate. See
.github/skills/kt-datacards/SKILL-tts.md and
/memories/repo/kt-app-step7-timestamp-alignment.md.

Exits 1 if any team has loop-risk; 0 otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (
    bag_last_card_update,
    digits,
    load_object_urls,
    team_dirs,
)


def main() -> int:
    risk: list[tuple[str, int, int]] = []
    checked = 0
    for td in team_dirs():
        team = td.name
        urls = load_object_urls(team)
        lcu = bag_last_card_update(team)
        if urls is None or lcu is None:
            continue
        checked += 1
        objs = list(urls.get("objects", []))
        if urls.get("box"):
            objs.append(urls["box"])
        local = digits(lcu)
        remote = max((digits(o.get("modified", "")) for o in objs), default=0)
        if local < remote:
            risk.append((team, local, remote))

    print(f"Checked {checked} teams")
    if not risk:
        print("PASS  All teams aligned (bag.lastCardUpdate >= obj-urls max modified)")
        return 0

    print(f"FAIL  {len(risk)} team(s) have TTS update-loop risk:")
    for team, local, remote in risk:
        print(f"  {team}: local={local} remote={remote} (local < remote)")
    print()
    print("Fix (recommended): re-run the generate_tts step for the affected team(s):")
    print("  python -m pipeline.main --source warcom --step generate_tts --teams <team>")
    print("Surgical fix (no cascade churn): see /memories/repo/kt-app-step7-timestamp-alignment.md")
    return 1


if __name__ == "__main__":
    sys.exit(main())
