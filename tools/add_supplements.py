"""Add designed-supplement (artwork/icon) PDFs to the sandbox input.

The card PDFs come from ``layers/kt-app/processed`` (populate_input.py). The
team ICON, however, lives on the "KILL TEAM" selection page of the *designed*
supplement PDF (``eng_*_kill_team_team_rules_*.pdf`` in ``layers/archive``),
which the card set does not include. ``extract_artwork`` needs it.

This copies the best supplement per team (highest icon rank; newest on ties)
into ``new_implementation/input`` alongside the card PDFs. front_end skips these
(they carry a designed KILL TEAM page), so they never become cards.

Run:  python tools/add_supplements.py   (from new_implementation/)
"""
from __future__ import annotations

import glob
import shutil
from pathlib import Path

import fitz  # PyMuPDF

from pipeline.steps.extract_artwork import _classify_source
from pipeline.utils.team_identification import TeamIdentifier

REPO = Path(__file__).resolve().parents[1]
ARCHIVE = REPO / "layers" / "archive"
INPUT = REPO / "input"
PROCESSED = REPO / "layers" / "kt-app" / "processed"


def main() -> None:
    ident = TeamIdentifier()
    supplements = glob.glob(
        str(ARCHIVE / "**" / "eng_*.pdf"), recursive=True
    )

    best: dict[str, tuple[int, float, Path]] = {}  # slug -> (rank, mtime, path)
    for p in map(Path, supplements):
        try:
            doc = fitz.open(p)
            slug, rank = _classify_source(doc, ident)
            doc.close()
        except Exception as e:
            print(f"  ! {p.name}: {e}")
            continue
        if not slug or rank < 1:
            continue
        mtime = p.stat().st_mtime
        cur = best.get(slug)
        if cur is None or (rank, mtime) > (cur[0], cur[1]):
            best[slug] = (rank, mtime, p)

    INPUT.mkdir(parents=True, exist_ok=True)
    copied = 0
    for slug, (rank, _mtime, src) in sorted(best.items()):
        shutil.copy2(src, INPUT / src.name)
        copied += 1
        print(f"  {slug:28s} rank={rank}  <- {src.name[:48]}")

    all_teams = sorted(d.name for d in PROCESSED.iterdir() if d.is_dir())
    missing = [t for t in all_teams if t not in best]
    print(f"\nsupplements copied      : {copied}")
    print(f"teams with card set     : {len(all_teams)}")
    print(f"teams WITHOUT supplement: {len(missing)}")
    if missing:
        for t in missing:
            print(f"    - {t}")
    print(f"input/ pdf count now    : {len(list(INPUT.glob('*.pdf')))}")


if __name__ == "__main__":
    main()
