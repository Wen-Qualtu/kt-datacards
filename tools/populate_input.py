"""Populate new_implementation/input/ with the full latest PDF set.

Strategy (preferred): for each latest file in ``layers/kt-app/processed``
(real names, ~327 files across 47 teams), find its byte-identical twin in
``layers/archive`` (GUID-named) and copy that GUID-named file into ``input/`` —
simulating the real production GUID-named inputs so we exercise the
content-based (filename-agnostic) identification path.

Fallback: when a processed file has no byte-identical archive twin (content is
newer than any archived version), copy the processed file itself (real name) so
we still get full team coverage.

Run:  python -m tools.populate_input        (from new_implementation/)
  or  python tools/populate_input.py
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]      # C:\git\kt-datacards
ARCHIVE = REPO / "layers" / "archive"
PROCESSED = REPO / "layers" / "kt-app" / "processed"
INPUT = REPO / "input"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if not PROCESSED.exists():
        raise SystemExit(f"processed source missing: {PROCESSED}")

    # Index every archived PDF by content hash (may hold duplicate versions).
    archive_by_hash: dict[str, list[Path]] = {}
    for p in ARCHIVE.rglob("*.pdf"):
        archive_by_hash.setdefault(sha(p), []).append(p)

    processed_files = sorted(PROCESSED.rglob("*.pdf"))

    INPUT.mkdir(parents=True, exist_ok=True)
    for f in INPUT.glob("*.pdf"):
        f.unlink()

    guid_hits = fallbacks = 0
    used_names: set[str] = set()
    fallback_files: list[str] = []

    for pf in processed_files:
        h = sha(pf)
        twins = archive_by_hash.get(h)
        if twins:
            src = sorted(twins)[0]   # GUID-named production twin
            guid_hits += 1
        else:
            src = pf                 # real-name fallback (newer content)
            fallbacks += 1
            fallback_files.append(pf.relative_to(PROCESSED).as_posix())

        dest_name = src.name
        if dest_name in used_names:
            dest_name = f"{src.stem}__{h[:8]}{src.suffix}"
        used_names.add(dest_name)
        shutil.copy2(src, INPUT / dest_name)

    final = len(list(INPUT.glob("*.pdf")))
    print(f"processed source files : {len(processed_files)}")
    print(f"GUID-name matches       : {guid_hits}")
    print(f"real-name fallbacks     : {fallbacks}")
    if fallback_files:
        print("  fallback (no archive twin):")
        for name in fallback_files:
            print(f"    - {name}")
    print(f"input/ pdf count now    : {final}")


if __name__ == "__main__":
    main()
