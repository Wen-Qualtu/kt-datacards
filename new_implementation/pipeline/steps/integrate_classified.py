"""Integration — shared merge point. Copy + rename extracted PDFs into one folder.

layers/{track}/extracted + layers/{track}/structure/{team}-structure.json
   ->  layers/shared/integration/{team}-{type}-{name}.pdf   (no -front/-back postfix)

Both tracks emit the IDENTICAL file set here. This is the dedup/merge point: run
whichever source GW updated and downstream is source-agnostic.

Uses the structure manifest to map each track's (differently named) extracted PDF
to its canonical classified filename. Each card becomes ONE classified PDF: a
front-only card is a 1-page PDF; a front+back card is a 2-page PDF (front, back).

When an entity has more than one physical card (e.g. a datacard whose actions are
on their own cards, or a multi-card faction rule), the card number is appended to
keep filenames unique: {team}-{type}-{name}-{card_number}.pdf.

SOURCE-DECISION: source only selects which track's structure/extracted to read.
OPEN: conflict policy when both tracks ran a team (currently last-run-wins —
files are simply overwritten).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF

from ..utils import naming, paths

logger = logging.getLogger(__name__)

# Type keys in deterministic order (matches build_structure output).
TYPE_KEYS = [
    "datacards",
    "equipment",
    "faction_rules",
    "token_guide",
    "firefight_ploys",
    "operatives_selection",
    "strategy_ploys",
]


def _merge_card(front: Path, back: Optional[Path], out_path: Path) -> None:
    """Write a classified PDF: front page first, optional back page second."""
    doc = fitz.open(front)
    if back is not None:
        with fitz.open(back) as back_doc:
            doc.insert_pdf(back_doc)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    doc.close()


def _integrate_team(team: str, structure: Dict, force: bool) -> Dict:
    stats = {"written": 0, "missing": 0}

    for key in TYPE_KEYS:
        entities = structure.get(key, [])
        card_type = naming.STRUCTURE_KEY_TO_TYPE.get(key, key)

        for entity in entities:
            name = entity.get("name") or "unknown"
            cards = entity.get("cards", [])
            multi = len(cards) > 1

            for card in cards:
                base = naming.classified_name(team, card_type, name)
                if multi:
                    base = f"{base}-{card['card_number']}"
                out_path = paths.INTEGRATION / f"{base}.pdf"

                front_rel = card.get("front")
                back_rel = card.get("back")
                if not front_rel:
                    logger.warning(f"  {base}: no front path, skipping")
                    stats["missing"] += 1
                    continue

                front = paths.ROOT / front_rel
                back = paths.ROOT / back_rel if back_rel else None
                if not front.exists():
                    logger.warning(f"  {base}: front missing on disk: {front}")
                    stats["missing"] += 1
                    continue
                if back is not None and not back.exists():
                    logger.warning(f"  {base}: back missing on disk: {back}")
                    back = None

                if out_path.exists() and not force:
                    # Overwrite is cheap and deterministic; only skip when not forcing
                    # and the file already exists from a prior run of the same track.
                    pass

                _merge_card(front, back, out_path)
                stats["written"] += 1

    return stats


def run(teams=None, source=None, force=False):
    if source not in ("kt-app", "warcom"):
        raise SystemExit("integrate_classified requires --source kt-app|warcom")

    import json

    structure_dir = paths.structure_dir(source)
    if not structure_dir.exists():
        logger.error(f"No structure directory: {structure_dir}")
        return {"teams": 0, "written": 0}

    if teams:
        structure_files = [structure_dir / f"{t}-structure.json" for t in teams]
        structure_files = [f for f in structure_files if f.exists()]
    else:
        structure_files = sorted(structure_dir.glob("*-structure.json"))

    paths.INTEGRATION.mkdir(parents=True, exist_ok=True)

    totals = {"teams": 0, "written": 0, "missing": 0}
    for sf in structure_files:
        with open(sf, "r", encoding="utf-8") as f:
            structure = json.load(f)
        team = structure.get("team") or sf.stem.replace("-structure", "")
        logger.info(f"Integrating: {team} (source={source})")
        stats = _integrate_team(team, structure, force)
        # Emit a source-agnostic manifest so downstream shared steps (content
        # analysis, etc.) can group entities without knowing which track ran.
        manifest_path = paths.integration_manifest_file(team)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as mf:
            json.dump(structure, mf, indent=2, ensure_ascii=False)
        logger.info(f"  wrote {stats['written']} classified PDFs (missing {stats['missing']})")
        totals["teams"] += 1
        totals["written"] += stats["written"]
        totals["missing"] += stats["missing"]

    logger.info(
        f"integrate_classified done: teams={totals['teams']} "
        f"written={totals['written']} missing={totals['missing']}"
    )
    return totals
