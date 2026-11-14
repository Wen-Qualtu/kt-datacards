"""Check serialized card GMNotes against a pre-refactor hash baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pipeline.steps import extract_stats, tts_impl

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tests" / "fixtures" / "gmnotes-preprocessing-baseline.json"


def gmnotes_manifest(*, prepared: bool) -> dict:
    rules = json.loads((ROOT / "config" / "weapon_rules.json").read_text(encoding="utf-8"))
    teams = {}
    for path in sorted((ROOT / "output").glob("*/data/*-team-data.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if prepared:
            data = extract_stats.prepare_team_data(data, rules)
        selections = data.get("operatives_selection") or []
        groups = selections[0].get("selection", {}) if selections else {}
        operatives = {}
        for operative in data.get("datacards") or []:
            model = tts_impl._sanitize_ampersands(tts_impl._build_gm_notes(
                operative, data, rules, selection_groups=groups.get(operative["name"].upper()) or [],
            ))
            text = json.dumps(model, separators=(",", ":"), ensure_ascii=False)
            operatives[operative["name"]] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        teams[data["team"]] = operatives
    return {"format": "sha256 of exact UTF-8 compact GMNotes JSON", "teams": teams}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record-baseline", action="store_true")
    args = parser.parse_args()
    actual = gmnotes_manifest(prepared=not args.record_baseline)
    if args.record_baseline:
        if BASELINE.exists():
            parser.error("baseline already exists; do not overwrite a compatibility baseline")
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        expected = json.loads(BASELINE.read_text(encoding="utf-8"))
        if actual != expected:
            raise SystemExit("GMNotes compatibility check failed: serialized output changed")
    count = sum(len(operatives) for operatives in actual["teams"].values())
    print(f"{'Recorded' if args.record_baseline else 'Verified'} exact GMNotes baseline: "
          f"{len(actual['teams'])} teams, {count} operatives")


if __name__ == "__main__":
    main()